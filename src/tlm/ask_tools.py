"""Ask-mode optional shell tools: model requests ```tlm-exec``` blocks; user confirms each run."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time

from tlm.providers.base import LLMProvider
from tlm.safety import check_argv
from tlm.session import Session, append_assistant, append_user
from tlm.settings import UserSettings

TLM_EXEC_PATTERN = re.compile(r"```tlm-exec\s*\n(\[[\s\S]*?\])\s*\n```", re.IGNORECASE)

MAX_TOOL_ROUNDS = 6

SYSTEM_PLAIN = "You are tlm, a helpful Linux-oriented assistant."

SYSTEM_TOOLS = """You are tlm, a helpful Linux-oriented assistant.

When you need live facts from the user's machine (OS version, CPU, memory, etc.), you may ask them to run **read-only** shell commands by including one or more fenced blocks exactly like:

```tlm-exec
["lsb_release", "-a"]
```

Rules:
- Each block is valid JSON: a JSON array of strings — one argv list (no shell, no pipes in a single block).
- Prefer short diagnostics: `uname`, `lsb_release`, `cat /proc/version`, `nproc`, `lscpu`, `free`, `sensors`, etc.
- Never suggest destructive or privileged commands (no rm, dd, mkfs, curl|bash, sudo, writes under /etc).
- After the user provides command output, answer concisely. Avoid new `tlm-exec` blocks unless you still lack critical facts (keep rounds minimal).
"""


def split_reply_and_execs(content: str) -> tuple[str, list[list[str]]]:
    """Remove only well-formed ```tlm-exec``` blocks from visible text; parse argv lists."""
    argvs: list[list[str]] = []
    out_chunks: list[str] = []
    pos = 0
    for m in TLM_EXEC_PATTERN.finditer(content):
        out_chunks.append(content[pos : m.start()])
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            out_chunks.append(m.group(0))
            pos = m.end()
            continue
        if isinstance(data, list) and data and all(isinstance(x, str) for x in data):
            argvs.append(list(data))
        else:
            out_chunks.append(m.group(0))
        pos = m.end()
    out_chunks.append(content[pos:])
    visible = "".join(out_chunks).strip()
    return visible, argvs


def _stdout_console():
    from rich.console import Console

    return Console(highlight=False, stderr=False)


def _rich_prompt_kit():
    try:
        from rich.console import Console
        from rich.panel import Panel as RichPanel
        from rich.prompt import Confirm as RichConfirm

        return Console(stderr=True, highlight=False), RichPanel, RichConfirm
    except Exception:
        return None, None, None


def print_markdown(text: str) -> None:
    if not text.strip():
        return
    try:
        from rich.markdown import Markdown

        _stdout_console().print(Markdown(text))
    except Exception:
        print(text)


def _run_argv(argv: list[str], *, timeout: float) -> tuple[int, str]:
    proc = subprocess.run(  # noqa: S603
        argv,
        shell=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    body = ""
    if out:
        body += f"stdout:\n{out}\n"
    if err:
        body += f"stderr:\n{err}\n"
    if not body:
        body = f"(exit {proc.returncode}, no output)\n"
    else:
        body += f"exit_code: {proc.returncode}\n"
    return proc.returncode, body


def estimate_ask_tokens(prov: LLMProvider, sys_prompt: str, sess: Session) -> tuple[int, int]:
    """Rough input/output token totals for telemetry."""
    in_t = prov.count_tokens(sys_prompt) + sum(
        prov.count_tokens(str(m.get("content", ""))) for m in sess.messages if m.get("role") == "user"
    )
    out_t = sum(
        prov.count_tokens(str(m.get("content", ""))) for m in sess.messages if m.get("role") == "assistant"
    )
    return in_t, out_t


def run_interactive_ask(
    prov: LLMProvider,
    sess: Session,
    user_message: str,
    *,
    tools: bool,
    settings: UserSettings,
) -> tuple[int, int, int, int]:
    """
    Append user message, chat (optionally tool loop), print final markdown.
    Returns (exit_code, in_tokens_est, out_tokens_est, duration_ms).
    """
    append_user(sess, user_message)
    msgs: list[dict[str, str]] = [
        {"role": str(m["role"]), "content": str(m["content"])} for m in sess.messages
    ]
    sys_prompt = SYSTEM_TOOLS if tools else SYSTEM_PLAIN
    timeout = min(float(settings.timeout), 120.0)
    t_all = time.perf_counter()
    rounds = 0

    while rounds < MAX_TOOL_ROUNDS:
        try:
            reply = prov.chat(msgs, system=sys_prompt)
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            in_t, out_t = estimate_ask_tokens(prov, sys_prompt, sess)
            return 3, in_t, out_t, int((time.perf_counter() - t_all) * 1000)

        append_assistant(sess, reply)
        msgs.append({"role": "assistant", "content": reply})

        visible, argvs = split_reply_and_execs(reply)
        can_prompt = tools and bool(argvs) and sys.stdin.isatty()

        if not can_prompt:
            if tools and argvs and not sys.stdin.isatty():
                note = (
                    "\n\n*(Shell tools were skipped: stdin is not a TTY. "
                    "Run in a real terminal to approve commands, or use `tlm ask --no-tools`.)*"
                )
                print_markdown((visible if visible.strip() else reply) + note)
            else:
                print_markdown(visible if visible.strip() else reply)
            in_t, out_t = estimate_ask_tokens(prov, sys_prompt, sess)
            return 0, in_t, out_t, int((time.perf_counter() - t_all) * 1000)

        if visible.strip():
            print_markdown(visible)

        pcon, RichPanel, RichConfirm = _rich_prompt_kit()
        use_rich_prompts = pcon is not None and RichPanel is not None and RichConfirm is not None

        feedback_parts: list[str] = []
        for argv in argvs:
            ok, reason = check_argv(argv)
            if not ok:
                feedback_parts.append(f"Blocked {argv!r}: {reason}")
                continue
            cmd_line = " ".join(argv)
            if use_rich_prompts:
                pcon.print(RichPanel(cmd_line, title="Proposed command", border_style="yellow"))
                run = RichConfirm.ask("Execute on your machine?", default=False, console=pcon)
            else:
                print(f"\nProposed: {cmd_line}", file=sys.stderr, flush=True)
                run = input("Execute? [y/N]: ").strip().lower() in ("y", "yes")
            if not run:
                feedback_parts.append(f"User declined: {cmd_line}")
                continue
            try:
                _code, body = _run_argv(argv, timeout=timeout)
                feedback_parts.append(f"$ {cmd_line}\n{body}")
            except subprocess.TimeoutExpired:
                feedback_parts.append(f"$ {cmd_line}\n(error: timeout after {timeout}s)")
            except OSError as e:
                feedback_parts.append(f"$ {cmd_line}\n(error: {e})")

        feedback = "\n\n".join(feedback_parts) if feedback_parts else "(no commands run)"
        append_user(sess, feedback)
        msgs.append({"role": "user", "content": feedback})
        rounds += 1

    print("error: too many tool rounds (limit reached)", file=sys.stderr)
    in_t, out_t = estimate_ask_tokens(prov, sys_prompt, sess)
    return 2, in_t, out_t, int((time.perf_counter() - t_all) * 1000)
