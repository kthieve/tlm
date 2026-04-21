"""Ask-mode optional tools: ```tlm-exec``` shell argv, ```tlm-mem``` search, ```tlm-web``` Lightpanda fetch."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

from tlm.memory import format_ready_for_prompt, format_search_results_for_prompt, prune_ready_to_budget, search_longterm
from tlm.providers.base import LLMProvider
from tlm.safety import check_argv
from tlm.session import Session, append_assistant, append_user
from tlm.settings import UserSettings
from tlm.web.lightpanda import (
    build_fetch_argv,
    normalize_search_provider,
    resolve_binary,
    search_url_for_query,
    validate_url,
)

TLM_EXEC_PATTERN = re.compile(r"```tlm-exec\s*\n(\[[\s\S]*?\])\s*\n```", re.IGNORECASE)
TLM_MEM_PATTERN = re.compile(r"```tlm-mem\s*\n(\{[\s\S]*?\})\s*\n```", re.IGNORECASE)
TLM_WEB_PATTERN = re.compile(
    r"```tlm-web\s*\n(\[[\s\S]*?\]|\{[\s\S]*?\})\s*\n```",
    re.IGNORECASE,
)

# Default cap for `tlm ask` tool loop; overridden by `ask_max_tool_rounds` in config (clamped 2–32).
DEFAULT_ASK_MAX_TOOL_ROUNDS = 12

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
- Only use `tlm-exec` when the question needs live local machine facts. For general knowledge/web/content questions, answer directly and avoid shell diagnostics.
- After the user provides command output, answer concisely. Avoid new `tlm-exec` blocks unless you still lack critical facts (keep rounds minimal).
"""

MEM_BLOCK_HELP = """
You may query stored **long-term memory** (read-only) with a fenced block:

```tlm-mem
{"op": "search", "q": "short search query"}
```

Use this when recalling stable facts the user may have stored earlier. Keep queries short.
"""

WEB_BLOCK_HELP = (
    """
You may fetch **public web pages** (read-only) when the user needs current facts from the internet. Use fenced blocks:

```tlm-web
{"op": "fetch", "url": "https://example.com/article"}
```

```tlm-web
{"op": "search", "q": "short search query"}
```

Optional search provider override:

```tlm-web
{"op": "search", "q": "short search query", "provider": "duckduckgo"}
```

**Batch (preferred)** — one fence, one user confirmation for the whole list:

```tlm-web
[
  {"op": "search", "q": "topic"},
  {"op": "fetch", "url": "https://example.com/page"}
]
```

`provider` supports `duckduckgo` or `brave` (both are **HTML search URLs** fetched only via **Lightpanda** — the live search page, not a separate HTTP API). If omitted, tlm uses `web_search_provider` from config (default: `duckduckgo`).

**`tlm-web` always uses Lightpanda** for both `search` and `fetch`: install the `lightpanda` binary (or set `lightpanda_path`). There is no alternate backend inside `tlm-web`.

**Also use `tlm-web`** whenever the user needs real web pages or search results — prefer **`search`** to discover URLs, then **`fetch`** on the best links. Do **not** substitute `tlm-exec` + `curl` for search-result pages or multi-page research; reserve **`tlm-exec` + curl/wget** for tiny one-off GETs (single known URL, small static/JSON) when that is clearly enough.

Prefer **https** URLs. **Group** `search` + all `fetch` ops **in one** ```tlm-web``` block (array) when you can — the CLI confirms once and reuses approval for the same URL/search if the model retries. Keep tool rounds minimal; use `tlm-exec` for local machine diagnostics or the occasional minimal HTTP GET only.

If web tools are unavailable (`web_enabled` false, Lightpanda missing, or network blocked), do **not** loop forever: answer offline, say what is missing, suggest enabling `web_enabled`, installing Lightpanda, or pasting URLs/text.
"""
    + f"Each **tool feedback** cycle counts toward `ask_max_tool_rounds` in config.toml "
    f"(default **{DEFAULT_ASK_MAX_TOOL_ROUNDS}**). After **search + fetches**, prefer **one** final answer "
    "without new ```tlm-web``` blocks unless essential.\n\n"
    "For **time-sensitive** questions (prices, “today”, breaking news), use **`tlm-web` `search`** then **`fetch`** on sources; use `curl` only as a rare supplement for a single simple URL.\n"
)

# Shown in the system prompt when ask runs with web=True but setup prevents ```tlm-web``` from running.
WEB_PREREQ_DISABLED = """\
**Web tools requested**, but `web_enabled` is **false** in config.toml. Tell the user to set `web_enabled = true`, install the **lightpanda** binary (or set `lightpanda_path`), then retry. Do **not** say you have no “live web” in general — explain this configuration step.
"""

WEB_PREREQ_NO_LIGHTPANDA = """\
`web_enabled` is **true**, but the **lightpanda** binary was **not** found (install it or set `lightpanda_path` in config). ```tlm-web``` will not run until then: https://github.com/lightpanda-io/browser — Do **not** claim a generic lack of web access; explain that Lightpanda must be installed for `tlm-web`.
"""


def split_reply_tools(
    content: str,
) -> tuple[str, list[list[str]], list[dict[str, object]], list[dict[str, object]]]:
    """Remove well-formed ```tlm-exec```, ```tlm-mem```, ```tlm-web``` blocks from visible text."""
    matches: list[tuple[str, int, int, str]] = []
    for m in TLM_EXEC_PATTERN.finditer(content):
        matches.append(("exec", m.start(), m.end(), m.group(1)))
    for m in TLM_MEM_PATTERN.finditer(content):
        matches.append(("mem", m.start(), m.end(), m.group(1)))
    for m in TLM_WEB_PATTERN.finditer(content):
        matches.append(("web", m.start(), m.end(), m.group(1)))
    matches.sort(key=lambda x: x[1])

    argvs: list[list[str]] = []
    mem_ops: list[dict[str, object]] = []
    web_ops: list[dict[str, object]] = []
    out_chunks: list[str] = []
    pos = 0
    for kind, start, end, body in matches:
        out_chunks.append(content[pos:start])
        pos = end
        raw = body.strip()
        if kind == "exec":
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                out_chunks.append(content[start:end])
                continue
            if isinstance(data, list) and data and all(isinstance(x, str) for x in data):
                argvs.append(list(data))
            else:
                out_chunks.append(content[start:end])
        else:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                out_chunks.append(content[start:end])
                continue
            if kind == "mem":
                if isinstance(data, dict):
                    mem_ops.append(data)
                else:
                    out_chunks.append(content[start:end])
            elif isinstance(data, dict):
                web_ops.append(data)
            elif (
                kind == "web"
                and isinstance(data, list)
                and data
                and all(isinstance(x, dict) for x in data)
            ):
                web_ops.extend(data)
            else:
                out_chunks.append(content[start:end])
    out_chunks.append(content[pos:])
    visible = "".join(out_chunks).strip()
    return visible, argvs, mem_ops, web_ops


def split_reply_and_execs(content: str) -> tuple[str, list[list[str]]]:
    """Backward-compatible: visible text + argv lists only."""
    v, a, _, _ = split_reply_tools(content)
    return v, a


def _mem_feedback(mem_ops: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for op in mem_ops:
        if str(op.get("op", "")).lower() != "search":
            parts.append(f"(unknown tlm-mem op: {op.get('op')!r})")
            continue
        q = str(op.get("q", "")).strip()
        if not q:
            parts.append("(tlm-mem search missing q)")
            continue
        hits = search_longterm(q, k=5)
        parts.append(format_search_results_for_prompt(hits))
    return "\n\n".join(parts).strip()


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


def _run_argv(argv: list[str], *, timeout: float, env: dict[str, str] | None = None) -> tuple[int, str]:
    proc = subprocess.run(  # noqa: S603
        argv,
        shell=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
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


def _truncate_for_model(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n… (truncated for context limit)\n"


def _extract_ran_commands(sess: Session) -> set[str]:
    """Best-effort extraction of previously executed command lines from tool feedback."""
    ran: set[str] = set()
    for m in sess.messages:
        if str(m.get("role", "")) != "user":
            continue
        content = str(m.get("content", ""))
        for line in content.splitlines():
            raw = line.strip()
            if raw.startswith("$ ") and len(raw) > 2:
                ran.add(raw[2:].strip())
    return ran


def _needs_machine_diagnostics(user_message: str) -> bool:
    text = (user_message or "").lower()
    return bool(
        re.search(
            r"\b(cpu|gpu|ram|memory|os|kernel|ubuntu|debian|arch|disk|ssd|hdd|hostname|ip|network|driver|temperature|system|machine|hardware|nproc|lscpu|free)\b",
            text,
        )
    )


def _lightpanda_env(settings: UserSettings) -> dict[str, str]:
    env = os.environ.copy()
    if settings.web_disable_lightpanda_telemetry:
        env["LIGHTPANDA_DISABLE_TELEMETRY"] = "true"
    return env


def _web_op_session_key(op: dict[str, object], settings: UserSettings) -> str | None:
    """Stable id for consent: same URL/search reuses approval within one `tlm ask` run."""
    op_name = str(op.get("op", "")).lower()
    if op_name == "fetch":
        u = str(op.get("url", "")).strip()
        return f"fetch:{u}" if u else None
    if op_name == "search":
        q = str(op.get("q", "")).strip()
        if not q:
            return None
        provider = normalize_search_provider(
            str(op.get("provider", "")).strip() or settings.web_search_provider
        )
        return f"search:{provider}:{q}"
    return None


def _confirm_web(
    *,
    title: str,
    preview: str,
    question: str,
    pcon,
    RichPanel,
    RichConfirm,
    use_rich: bool,
) -> bool:
    if use_rich and pcon is not None and RichPanel is not None and RichConfirm is not None:
        pcon.print(RichPanel(preview, title=title, border_style="cyan"))
        return bool(RichConfirm.ask(question, default=False, console=pcon))
    print(f"\n{title}: {preview}", file=sys.stderr, flush=True)
    return input(f"{question} [y/N]: ").strip().lower() in ("y", "yes")


def _run_web_ops_interactive(
    web_ops: list[dict[str, object]],
    *,
    settings: UserSettings,
    bin_path: str | None,
    timeout: float,
    pcon,
    RichPanel,
    RichConfirm,
    use_rich: bool,
    session_approved: set[str],
) -> list[str]:
    parts: list[str] = []
    dump = settings.web_dump if settings.web_dump in ("markdown", "html") else "markdown"
    allow_http = bool(settings.web_allow_http)
    max_chars = int(settings.web_max_output_chars)
    lp_env = _lightpanda_env(settings)

    steps: list[dict[str, object]] = []

    for op in web_ops:
        op_name = str(op.get("op", "")).lower()
        if op_name == "fetch":
            url = str(op.get("url", "")).strip()
            label = f"fetch {url!r}"
            ok, reason = validate_url(url, allow_http=allow_http)
            if not ok:
                parts.append(f"(tlm-web fetch blocked: {reason})")
                continue
            if not bin_path:
                parts.append(
                    "(tlm-web fetch needs Lightpanda; install `lightpanda` or use a simple `tlm-exec` curl GET.)"
                )
                continue
            argv = build_fetch_argv(
                bin_path,
                url,
                dump=dump,
                obey_robots=bool(settings.web_obey_robots),
            )
            preview = " ".join(argv)
            key = _web_op_session_key(op, settings)
            if not key:
                parts.append("(tlm-web fetch missing url)")
                continue
            steps.append({"key": key, "label": label, "preview": preview, "argv": argv})
            continue

        if op_name == "search":
            q = str(op.get("q", "")).strip()
            if not q:
                parts.append("(tlm-web search missing q)")
                continue
            provider = normalize_search_provider(
                str(op.get("provider", "")).strip() or settings.web_search_provider
            )
            target = search_url_for_query(q, provider=provider)
            label = f"search[{provider}] {q!r} → {target}"
            ok, reason = validate_url(target, allow_http=allow_http)
            if not ok:
                parts.append(f"(tlm-web search blocked: {reason})")
                continue

            if not bin_path:
                parts.append(
                    "(tlm-web search requires the Lightpanda binary; set `lightpanda_path` or install "
                    "`lightpanda` — https://github.com/lightpanda-io/browser )"
                )
                continue

            argv = build_fetch_argv(
                bin_path,
                target,
                dump=dump,
                obey_robots=bool(settings.web_obey_robots),
            )
            preview = " ".join(argv)
            key = _web_op_session_key(op, settings)
            if not key:
                parts.append("(tlm-web search missing q)")
                continue
            steps.append({"key": key, "label": label, "preview": preview, "argv": argv})
            continue

        parts.append(f"(unknown tlm-web op: {op.get('op')!r})")

    pending = [s for s in steps if str(s["key"]) not in session_approved]
    if pending:
        if len(pending) == 1:
            s0 = pending[0]
            run = _confirm_web(
                title=f"Proposed web: {s0['label']}",
                preview=str(s0["preview"]),
                question="Run this with Lightpanda?",
                pcon=pcon,
                RichPanel=RichPanel,
                RichConfirm=RichConfirm,
                use_rich=use_rich,
            )
            if run:
                session_approved.add(str(s0["key"]))
        else:
            batch_preview = "\n\n".join(
                f"{i}. {s['label']}\n   {s['preview']}" for i, s in enumerate(pending, start=1)
            )
            run = _confirm_web(
                title=f"Proposed web: {len(pending)} Lightpanda requests",
                preview=batch_preview,
                question=f"Approve all {len(pending)} requests?",
                pcon=pcon,
                RichPanel=RichPanel,
                RichConfirm=RichConfirm,
                use_rich=use_rich,
            )
            if run:
                for s in pending:
                    session_approved.add(str(s["key"]))
            else:
                for s in pending:
                    run_one = _confirm_web(
                        title=f"Proposed web: {s['label']}",
                        preview=str(s["preview"]),
                        question="Run this with Lightpanda?",
                        pcon=pcon,
                        RichPanel=RichPanel,
                        RichConfirm=RichConfirm,
                        use_rich=use_rich,
                    )
                    if run_one:
                        session_approved.add(str(s["key"]))

    for s in steps:
        key = str(s["key"])
        label = str(s["label"])
        preview = str(s["preview"])
        argv = s["argv"]
        if key not in session_approved:
            parts.append(f"User declined web: {label}")
            continue
        try:
            _code, body = _run_argv(argv, timeout=timeout, env=lp_env)
            body = _truncate_for_model(body, max_chars)
            parts.append(f"$ {preview}\n{body}")
        except subprocess.TimeoutExpired:
            parts.append(f"$ {preview}\n(error: timeout after {timeout}s)")
        except OSError as e:
            parts.append(f"$ {preview}\n(error: {e})")

    return parts


def estimate_ask_tokens(prov: LLMProvider, sys_prompt: str, sess: Session) -> tuple[int, int]:
    """Rough input/output token totals for telemetry."""
    in_t = prov.count_tokens(sys_prompt) + sum(
        prov.count_tokens(str(m.get("content", ""))) for m in sess.messages if m.get("role") == "user"
    )
    out_t = sum(
        prov.count_tokens(str(m.get("content", ""))) for m in sess.messages if m.get("role") == "assistant"
    )
    return in_t, out_t


def _build_system_prompt(
    tools: bool,
    *,
    memory_enabled: bool,
    web_prompt: bool,
    web_prerequisite: str = "",
    web_note: str = "",
    clear_context: bool,
    ready_items: list[str],
    ready_budget: int,
) -> str:
    ready_block = ""
    if memory_enabled and not clear_context and ready_items:
        pruned = prune_ready_to_budget(ready_items, ready_budget)
        ready_block = format_ready_for_prompt(pruned) + "\n"
    base = SYSTEM_TOOLS if tools else SYSTEM_PLAIN
    mem_help = (MEM_BLOCK_HELP + "\n") if memory_enabled else ""
    web_help = ""
    if web_prerequisite.strip():
        web_help += web_prerequisite.strip() + "\n"
    if web_prompt:
        web_help += WEB_BLOCK_HELP.rstrip() + "\n"
    if web_note.strip():
        web_help += web_note.strip() + "\n"
    return f"{ready_block}{base}\n{mem_help}{web_help}".strip() + "\n"


def run_interactive_ask(
    prov: LLMProvider,
    sess: Session,
    user_message: str,
    *,
    tools: bool,
    web: bool,
    settings: UserSettings,
    clear_context: bool = False,
    web_focus: bool = False,
) -> tuple[int, int, int, int]:
    """
    Append user message, chat (optionally tool loop), print final markdown.
    Returns (exit_code, in_tokens_est, out_tokens_est, duration_ms).
    """
    effective_user_message = user_message
    if web_focus:
        effective_user_message = (
            f"{user_message}\n\n"
            "Note: Invoked as **`tlm web`** — answer with ```tlm-web``` (`search` then `fetch` on result URLs) "
            "when Lightpanda is available; do not refuse live web without checking tool availability."
        )
    elif web and settings.web_enabled:
        # Nudge live-web behavior for clearly time-sensitive prompts.
        if re.search(
            r"\b(current|latest|today|now|price|stock|rate|web|internet|online)\b",
            user_message,
            flags=re.IGNORECASE,
        ):
            effective_user_message = (
                f"{user_message}\n\n"
                "Note: Time-sensitive — use `tlm-web` (`search` then `fetch`) via **Lightpanda** for web pages; "
                "avoid curl for search results; `tlm-exec` curl only for a trivial single-URL GET if enough."
            )

    append_user(sess, effective_user_message)
    msgs: list[dict[str, str]] = [
        {"role": str(m["role"]), "content": str(m["content"])} for m in sess.messages
    ]
    memory_on = bool(settings.memory_enabled)
    ready_items: list[str] = []
    if memory_on:
        from tlm.memory import load_ready

        ready_items = load_ready()

    lp_bin = resolve_binary(settings) if settings.web_enabled else None
    web_prompt = bool(web and settings.web_enabled and lp_bin)
    web_prerequisite = ""
    if web and not settings.web_enabled:
        web_prerequisite = WEB_PREREQ_DISABLED
    elif web and settings.web_enabled and not lp_bin:
        web_prerequisite = WEB_PREREQ_NO_LIGHTPANDA

    web_note = ""
    if web_prompt:
        web_note = "Session: **`tlm-web` is Lightpanda-only** — use it for `search` and `fetch`; do not use HTTP search APIs or curl for search-result pages here."
        if web_focus:
            web_note += " User ran **`tlm web`** — emit ```tlm-web``` `search` first for this question, then `fetch` the best URLs."

    sys_prompt = _build_system_prompt(
        tools,
        memory_enabled=memory_on,
        web_prompt=web_prompt,
        web_prerequisite=web_prerequisite,
        web_note=web_note,
        clear_context=clear_context,
        ready_items=ready_items,
        ready_budget=int(settings.memory_ready_budget_chars),
    )
    timeout = min(float(settings.timeout), 120.0)
    t_all = time.perf_counter()
    rounds = 0
    machine_diag_needed = _needs_machine_diagnostics(user_message)
    previously_ran_cmds = _extract_ran_commands(sess)

    shell_skip_note = (
        "*(Shell tools were skipped: stdin is not a TTY. "
        "Run in a real terminal to approve commands, or use `tlm ask --no-tools`.)*"
    )
    web_skip_note = (
        "*(Web tools were skipped: stdin is not a TTY. "
        "Run in a real terminal to approve fetches, or use `tlm ask --no-web` to hide web tools.)*"
    )

    # One confirmation per distinct URL/search per `tlm ask` run; batch new ops together.
    web_approved_keys: set[str] = set()
    max_tool_rounds = max(2, min(32, int(settings.ask_max_tool_rounds)))

    while rounds < max_tool_rounds:
        try:
            reply = prov.chat(msgs, system=sys_prompt)
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            in_t, out_t = estimate_ask_tokens(prov, sys_prompt, sess)
            return 3, in_t, out_t, int((time.perf_counter() - t_all) * 1000)

        append_assistant(sess, reply)
        msgs.append({"role": "assistant", "content": reply})

        visible, argvs, mem_ops, web_ops = split_reply_tools(reply)
        mem_fb = _mem_feedback(mem_ops) if (memory_on and mem_ops) else ""

        tty = sys.stdin.isatty()
        exec_wanted = bool(tools and argvs)
        web_wanted = bool(web and web_ops)

        feedback_parts: list[str] = []
        if mem_fb:
            feedback_parts.append(mem_fb)

        non_tty_blocks = (exec_wanted or web_wanted) and not tty
        if non_tty_blocks and not mem_fb:
            notes: list[str] = []
            if exec_wanted:
                notes.append(shell_skip_note)
            if web_wanted:
                notes.append(web_skip_note)
            note = "\n\n".join(notes)
            print_markdown((visible if visible.strip() else reply) + ("\n\n" + note if note else ""))
            in_t, out_t = estimate_ask_tokens(prov, sys_prompt, sess)
            return 0, in_t, out_t, int((time.perf_counter() - t_all) * 1000)

        if exec_wanted and not tty:
            feedback_parts.append(shell_skip_note)
        if web_wanted and not tty:
            feedback_parts.append(web_skip_note)

        pcon, RichPanel, RichConfirm = _rich_prompt_kit()
        use_rich = pcon is not None and RichPanel is not None and RichConfirm is not None

        printed_visible_for_tools = False
        if tty and exec_wanted and visible.strip():
            print_markdown(visible)
            printed_visible_for_tools = True

        if tty and exec_wanted:
            exec_parts: list[str] = []
            for argv in argvs:
                ok, reason = check_argv(argv)
                if not ok:
                    exec_parts.append(f"Blocked {argv!r}: {reason}")
                    continue
                cmd_line = " ".join(argv)
                if cmd_line in previously_ran_cmds and not machine_diag_needed:
                    exec_parts.append(
                        f"Skipped repeated command from older topic: {cmd_line} "
                        "(use `tlm clear` / `tlm new` for a fresh context)"
                    )
                    continue
                if use_rich:
                    pcon.print(RichPanel(cmd_line, title="Proposed command", border_style="yellow"))
                    run = RichConfirm.ask("Execute on your machine?", default=False, console=pcon)
                else:
                    print(f"\nProposed: {cmd_line}", file=sys.stderr, flush=True)
                    run = input("Execute? [y/N]: ").strip().lower() in ("y", "yes")
                if not run:
                    exec_parts.append(f"User declined: {cmd_line}")
                    continue
                try:
                    _code, body = _run_argv(argv, timeout=timeout)
                    exec_parts.append(f"$ {cmd_line}\n{body}")
                    previously_ran_cmds.add(cmd_line)
                except subprocess.TimeoutExpired:
                    exec_parts.append(f"$ {cmd_line}\n(error: timeout after {timeout}s)")
                except OSError as e:
                    exec_parts.append(f"$ {cmd_line}\n(error: {e})")

            feedback_parts.append("\n\n".join(exec_parts) if exec_parts else "(no commands run)")

        if tty and web_wanted:
            if not printed_visible_for_tools and visible.strip():
                print_markdown(visible)
            if not web:
                feedback_parts.append("*(tlm-web: disabled for this run via `--no-web`.)*")
            elif not settings.web_enabled:
                feedback_parts.append(
                    "*(tlm-web: set `web_enabled = true` in config.toml and install Lightpanda "
                    "(https://github.com/lightpanda-io/browser).)*"
                )
            elif not lp_bin:
                feedback_parts.append(
                    "*(tlm-web: install `lightpanda` or set `lightpanda_path` in config.toml "
                    "(https://github.com/lightpanda-io/browser).)*"
                )
            else:
                web_parts = _run_web_ops_interactive(
                    web_ops,
                    settings=settings,
                    bin_path=lp_bin,
                    timeout=timeout,
                    pcon=pcon,
                    RichPanel=RichPanel,
                    RichConfirm=RichConfirm,
                    use_rich=use_rich,
                    session_approved=web_approved_keys,
                )
                feedback_parts.append("\n\n".join(web_parts) if web_parts else "(no web fetches run)")

        if feedback_parts:
            combined = "\n\n".join(p for p in feedback_parts if p)
            append_user(sess, combined)
            msgs.append({"role": "user", "content": combined})
            rounds += 1
            continue

        print_markdown(visible if visible.strip() else reply)
        in_t, out_t = estimate_ask_tokens(prov, sys_prompt, sess)
        return 0, in_t, out_t, int((time.perf_counter() - t_all) * 1000)

    print(
        f"error: too many tool rounds (limit {max_tool_rounds}; set `ask_max_tool_rounds` in config.toml, max 32)",
        file=sys.stderr,
    )
    for m in reversed(sess.messages):
        if str(m.get("role")) == "assistant":
            vis, _, _, _ = split_reply_tools(str(m.get("content", "")))
            if vis.strip():
                print_markdown(vis)
            break
    in_t, out_t = estimate_ask_tokens(prov, sys_prompt, sess)
    return 2, in_t, out_t, int((time.perf_counter() - t_all) * 1000)
