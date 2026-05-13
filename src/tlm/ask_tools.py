"""Ask-mode optional tools: ```tlm-exec``` shell argv, ```tlm-mem``` search, ```tlm-web``` Lightpanda fetch."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field

from tlm.memory import (
    format_ready_for_prompt,
    format_search_results_for_prompt,
    prune_ready_to_budget,
    search_longterm,
)
from tlm.providers.base import LLMProvider
from tlm.safety import check_argv
from tlm.session import Session, append_assistant, append_user
from tlm.settings import UserSettings
from tlm.web.lightpanda import (
    build_fetch_argv,
    detect_fetch_capabilities,
    normalize_search_provider,
    resolve_binary,
    search_url_for_query,
    validate_url,
)
from tlm.web.runner import FetchJob, FetchResult, format_web_feedback, run_web_batch

TLM_EXEC_PATTERN = re.compile(r"```tlm-exec\s*\n(\[[\s\S]*?\])\s*\n```", re.IGNORECASE)
TLM_MEM_PATTERN = re.compile(r"```tlm-mem\s*\n(\{[\s\S]*?\})\s*\n```", re.IGNORECASE)
TLM_WEB_PATTERN = re.compile(
    r"```tlm-web\s*\n(\[[\s\S]*?\]|\{[\s\S]*?\})\s*\n```",
    re.IGNORECASE,
)
TLM_MEM_PROPOSE_PATTERN = re.compile(
    r"```tlm-mem-propose\s*\n(\{[\s\S]*?\})\s*\n```", re.IGNORECASE
)
TLM_WRITE_PATTERN = re.compile(
    r"```tlm-write\s*\n(\[[\s\S]*?\]|\{[\s\S]*?\})\s*\n```", re.IGNORECASE
)

# Default cap for `tlm ask` tool loop; overridden by `ask_max_tool_rounds` in config (clamped 2–32).
DEFAULT_ASK_MAX_TOOL_ROUNDS = 12

from tlm.prompts import load_prompt

SYSTEM_PLAIN = load_prompt("ask", "system_plain")
SYSTEM_TOOLS = load_prompt("ask", "system_tools")
MEM_BLOCK_HELP = load_prompt("memory", "block_help")
MEM_PROPOSE_HELP = load_prompt("memory", "propose_help")
WEB_BLOCK_HELP = load_prompt("web", "block_help")
WEB_PREREQ_DISABLED = load_prompt("web", "prereq_disabled")
WEB_PREREQ_NO_LIGHTPANDA = load_prompt("web", "prereq_no_lightpanda")


def split_reply_tools(
    content: str,
) -> tuple[
    str,
    list[list[str]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    """Remove well-formed ```tlm-exec```, ```tlm-mem```, ```tlm-web```, ```tlm-mem-propose```, ```tlm-write``` blocks from visible text."""
    matches: list[tuple[str, int, int, str]] = []
    for m in TLM_EXEC_PATTERN.finditer(content):
        matches.append(("exec", m.start(), m.end(), m.group(1)))
    for m in TLM_MEM_PATTERN.finditer(content):
        matches.append(("mem", m.start(), m.end(), m.group(1)))
    for m in TLM_WEB_PATTERN.finditer(content):
        matches.append(("web", m.start(), m.end(), m.group(1)))
    for m in TLM_MEM_PROPOSE_PATTERN.finditer(content):
        matches.append(("mem-propose", m.start(), m.end(), m.group(1)))
    for m in TLM_WRITE_PATTERN.finditer(content):
        matches.append(("write", m.start(), m.end(), m.group(1)))
    matches.sort(key=lambda x: x[1])

    argvs: list[list[str]] = []
    mem_ops: list[dict[str, object]] = []
    web_ops: list[dict[str, object]] = []
    mem_proposals: list[dict[str, object]] = []
    write_ops: list[dict[str, object]] = []
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
            elif kind == "mem-propose":
                if isinstance(data, dict):
                    mem_proposals.append(data)
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
            elif kind == "write":
                if isinstance(data, dict):
                    write_ops.append(data)
                elif isinstance(data, list) and all(isinstance(x, dict) for x in data):
                    write_ops.extend(data)
                else:
                    out_chunks.append(content[start:end])
            else:
                out_chunks.append(content[start:end])
    out_chunks.append(content[pos:])
    visible = "".join(out_chunks).strip()
    return visible, argvs, mem_ops, web_ops, mem_proposals, write_ops


def split_reply_and_execs(content: str) -> tuple[str, list[list[str]]]:
    """Backward-compatible: visible text + argv lists only."""
    v, a, _, _, _, _ = split_reply_tools(content)
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


def _mem_propose_feedback(proposals: list[dict[str, object]]) -> str:
    from tlm.memory_rules import MemoryRule, load_memory_rules, save_memory_rules
    import uuid

    parts: list[str] = []
    for p in proposals:
        text = str(p.get("text", "")).strip()
        rtype = str(p.get("type", "store")).lower()
        if rtype not in ("store", "never"):
            rtype = "store"

        if not text:
            parts.append("(tlm-mem-propose missing text)")
            continue

        print(f"\n[Proposed Memory Rule ({rtype})]: {text}")
        try:
            c = input("Accept this rule? [y/N]: ").strip().lower()
        except EOFError:
            parts.append("(rule proposal cancelled)")
            continue

        if c in ("y", "yes"):
            rules = load_memory_rules()
            # Check for duplicates
            if any(r.text.lower() == text.lower() for r in rules):
                parts.append(f"(rule already exists: {text})")
                continue
            
            new_id = f"rule_{uuid.uuid4().hex[:8]}"
            rules.append(MemoryRule(id=new_id, text=text, type=rtype))
            save_memory_rules(rules)
            parts.append(f"(rule accepted and saved: {text})")
        else:
            parts.append("(rule proposal rejected by user)")
    
    return "\n\n".join(parts).strip()


def _write_feedback(
    write_ops: list[dict[str, object]],
    *,
    pcon,
    RichPanel,
    RichConfirm,
    use_rich: bool,
    settings: UserSettings,
) -> str:
    from pathlib import Path
    from tlm.modes.write import _under_base, _diff_text
    from tlm.safety import interactive_gate_string
    from tlm.safety.profiles import SafetyProfile, normalize_profile
    from tlm.safety.snapshot import create_snapshot
    from tlm.safety.transaction import AtomicTransaction
    import sys

    parts: list[str] = []
    base_dir = Path.cwd()

    for op in write_ops:
        rel = str(op.get("path", "")).strip()
        contents = str(op.get("contents", ""))
        ex = bool(op.get("executable", False))

        if not rel:
            parts.append("(tlm-write missing path)")
            continue

        target = (base_dir / rel).resolve()
        if not _under_base(target, base_dir):
            parts.append(f"(tlm-write error: path escapes base dir: {rel!r})")
            continue

        old = ""
        current_mode = 0o644
        if target.is_file():
            old = target.read_text(encoding="utf-8")
            current_mode = target.stat().st_mode & 0o777
        elif target.exists():
            parts.append(f"(tlm-write error: exists but is not a file: {rel!r})")
            continue
        else:
            if ex:
                current_mode = 0o755

        diff = (
            _diff_text(rel, old, contents)
            if old
            else f"(new file {rel}, {len(contents)} bytes)\n"
        )

        body = f"--- proposed write: {rel} ---\n{diff}"
        
        # Interactive prompt using gate
        dec, _, extra_mode = interactive_gate_string(
            body,
            allow_edit=False,
            dry_run=False,
            auto_yes=False,
            can_auto_yes=False,
            extra_prompt=f"Target octal permissions for {rel} (default {oct(current_mode)[2:]})",
        )

        if dec == "cancel":
            parts.append(f"(User declined writing to {rel})")
            continue

        profile = normalize_profile(settings.safety_profile)
        if profile in (SafetyProfile.standard, SafetyProfile.strict):
            sid = create_snapshot(base_dir)
            if sid:
                print(f"snapshot created: {sid}", flush=True)

        final_mode = current_mode
        if extra_mode:
            try:
                final_mode = int(extra_mode, 8)
            except ValueError:
                print(f"error: invalid octal mode {extra_mode!r}, using default.", file=sys.stderr)

        with AtomicTransaction(base_dir) as txn:
            try:
                txn.stage(target, contents, final_mode)
                txn.commit()
                print(f"wrote {rel} (mode {oct(final_mode)})", flush=True)
                parts.append(f"(File {rel} written successfully)")
            except Exception as e:
                print(f"error: transaction failed: {e}", flush=True)
                parts.append(f"(tlm-write error: failed to write {rel}: {e})")

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


def _run_argv(
    argv: list[str], *, timeout: float, env: dict[str, str] | None = None
) -> tuple[int, str]:
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


@dataclass
class WebConsent:
    """Per-`tlm ask` / `tlm ?` run: which ```tlm-web``` ops are approved; optional one-shot trust for the whole run."""

    approved_keys: set[str] = field(default_factory=set)
    trust_run: bool = False


def _next_hint_for_web(visible: str) -> str:
    """One-line hint for the progress footer: first non-fence line of the assistant text."""
    for line in (visible or "").splitlines():
        t = line.strip()
        if t and not t.startswith("```"):
            return t[:400]
    return "synthesize a final answer from the page content in the tool feedback"


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


def _confirm_single_web(
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


def _prompt_web_batch_consent(
    pending: list[dict],
    web_consent: WebConsent,
    *,
    pcon,
    RichPanel,
    RichConfirm,
    use_rich: bool,
) -> None:
    if not pending or web_consent.trust_run:
        return
    pre_list = "\n\n".join(
        f"{i}. {s['label']}\n   {s['preview']}" for i, s in enumerate(pending, start=1)
    )
    title = f"tlm-web: {len(pending)} Lightpanda request(s)"
    if use_rich and pcon is not None and RichPanel is not None:
        pcon.print(RichPanel(pre_list, title=title, border_style="cyan"))
        pcon.print(
            "  [1] This batch only   [2] Trust this tlm run (no more web prompts)   [3] Per-item (y/n each)\n"
        )
    else:
        print(f"\n{title}\n{pre_list}", file=sys.stderr, flush=True)
        print(
            "  [1] This batch   [2] Trust this tlm run   [3] Per-item",
            file=sys.stderr,
            flush=True,
        )
    try:
        choice = (input("Choice [1/2/3] (default 1): ").strip() or "1").lower()
    except EOFError:
        choice = "3"
    if choice in ("2", "trust", "t"):
        web_consent.trust_run = True
    elif choice in ("3", "p", "n", "per", "per-item", "i"):
        for s in pending:
            ok = _confirm_single_web(
                title=f"Proposed web: {s['label']}",
                preview=str(s["preview"]),
                question="Run this with Lightpanda?",
                pcon=pcon,
                RichPanel=RichPanel,
                RichConfirm=RichConfirm,
                use_rich=use_rich,
            )
            if ok:
                web_consent.approved_keys.add(str(s["key"]))
    else:
        for s in pending:
            web_consent.approved_keys.add(str(s["key"]))


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
    web_consent: WebConsent,
    assistant_visible: str = "",
) -> list[str]:
    parts: list[str] = []
    dump = settings.web_dump if settings.web_dump in ("markdown", "html") else "markdown"
    allow_http = bool(settings.web_allow_http)
    max_chars = int(settings.web_max_output_chars)
    lp_env = _lightpanda_env(settings)
    next_hint = _next_hint_for_web(assistant_visible)
    caps = (
        detect_fetch_capabilities(str(bin_path))
        if bin_path
        else {"user_agent": False, "user_agent_suffix": False}
    )
    ua = (settings.web_user_agent or "").strip()
    ua_suffix = (settings.web_user_agent_suffix or "").strip()
    if ua and not bool(caps.get("user_agent")):
        parts.append(
            "(tlm-web: configured `web_user_agent`, but this Lightpanda build lacks `--user-agent`; ignoring.)"
        )
    if (not ua) and ua_suffix and not bool(caps.get("user_agent_suffix")):
        parts.append(
            "(tlm-web: configured `web_user_agent_suffix`, but this Lightpanda build lacks "
            "`--user-agent-suffix`; ignoring.)"
        )

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
                str(bin_path),
                url,
                dump=dump,
                obey_robots=bool(settings.web_obey_robots),
                user_agent=ua,
                user_agent_suffix=ua_suffix,
                supports_user_agent=bool(caps.get("user_agent")),
                supports_user_agent_suffix=bool(caps.get("user_agent_suffix")),
            )
            preview = " ".join(argv)
            key = _web_op_session_key(op, settings)
            if not key:
                parts.append("(tlm-web fetch missing url)")
                continue
            kind = "fetch"
            steps.append(
                {
                    "key": key,
                    "label": label,
                    "preview": preview,
                    "argv": argv,
                    "url": url,
                    "kind": kind,
                }
            )
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
                str(bin_path),
                target,
                dump=dump,
                obey_robots=bool(settings.web_search_obey_robots),
                user_agent=ua,
                user_agent_suffix=ua_suffix,
                supports_user_agent=bool(caps.get("user_agent")),
                supports_user_agent_suffix=bool(caps.get("user_agent_suffix")),
            )
            preview = " ".join(argv)
            key = _web_op_session_key(op, settings)
            if not key:
                parts.append("(tlm-web search missing q)")
                continue
            steps.append(
                {
                    "key": key,
                    "label": label,
                    "preview": preview,
                    "argv": argv,
                    "url": target,
                    "kind": "search",
                }
            )
            continue

        parts.append(f"(unknown tlm-web op: {op.get('op')!r})")

    pending = [
        s
        for s in steps
        if str(s["key"]) not in web_consent.approved_keys and not web_consent.trust_run
    ]
    _prompt_web_batch_consent(
        pending,
        web_consent,
        pcon=pcon,
        RichPanel=RichPanel,
        RichConfirm=RichConfirm,
        use_rich=use_rich,
    )

    if not steps:
        return [p for p in parts if p] or ["(no web fetches to run)"]

    def _lp_run(argv: list[str]) -> tuple[int, str]:
        try:
            return _run_argv(argv, timeout=timeout, env=lp_env)
        except subprocess.TimeoutExpired as e:
            return -1, f"stderr:\n{str(e)}\n"

    jobs: list[FetchJob] = []
    for s in steps:
        key = str(s["key"])
        if web_consent.trust_run or key in web_consent.approved_keys:
            jobs.append(
                FetchJob(
                    key=key,
                    label=str(s["label"]),
                    url=str(s["url"]),
                    argv=list(s["argv"]),
                    preview=str(s["preview"]),
                    kind=str(s["kind"]),
                )
            )

    batch: list[FetchResult] = []
    if jobs:
        batch = run_web_batch(
            jobs,
            run_argv=_lp_run,
            timeout=timeout,
            env=lp_env,
            concurrency=_clamp_web_conc(settings),
            dump=dump,
            max_output_chars=max_chars,
            pcon=pcon,
            use_rich=use_rich,
            next_hint=next_hint,
        )
    by_key: dict[str, FetchResult] = {r.job.key: r for r in batch}

    out_order: list[FetchResult] = []
    for s in steps:
        key = str(s["key"])
        if key in by_key:
            out_order.append(by_key[key])
        else:
            out_order.append(
                FetchResult(
                    FetchJob(
                        key=key,
                        label=str(s["label"]),
                        url=str(s["url"]),
                        argv=list(s["argv"]),
                        preview=str(s["preview"]),
                        kind=str(s["kind"]),
                    ),
                    status="declined",
                )
            )

    out_lines: list[str] = [p for p in parts if p]
    if out_order:
        out_lines.append(format_web_feedback(out_order, max_chars=max_chars))
    if not out_lines:
        return ["(no web fetches run)"]
    return out_lines


def _clamp_web_conc(settings: UserSettings) -> int:
    n = int(getattr(settings, "web_concurrency", 3))
    return max(1, min(8, n))


def estimate_ask_tokens(prov: LLMProvider, sys_prompt: str, sess: Session) -> tuple[int, int]:
    """Rough input/output token totals for telemetry."""
    in_t = prov.count_tokens(sys_prompt) + sum(
        prov.count_tokens(str(m.get("content", "")))
        for m in sess.messages
        if m.get("role") == "user"
    )
    out_t = sum(
        prov.count_tokens(str(m.get("content", "")))
        for m in sess.messages
        if m.get("role") == "assistant"
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
        ready_block = load_prompt("ask", "memory_ready_hint") + "\n" + format_ready_for_prompt(pruned) + "\n"
    base = SYSTEM_TOOLS if tools else SYSTEM_PLAIN
    mem_help = (MEM_BLOCK_HELP + "\n") if memory_enabled else ""
    propose_help = (MEM_PROPOSE_HELP + "\n") if memory_enabled else ""
    web_help = ""
    if web_prerequisite.strip():
        web_help += web_prerequisite.strip() + "\n"
    if web_prompt:
        web_help += WEB_BLOCK_HELP.rstrip() + "\n"
    if web_note.strip():
        web_help += web_note.strip() + "\n"
    return f"{ready_block}{base}\n{mem_help}{propose_help}{web_help}".strip() + "\n"


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
        effective_user_message = f"{user_message}\n\n{load_prompt('web', 'web_focus_note')}"
    elif web and settings.web_enabled:
        # Nudge live-web behavior for clearly time-sensitive prompts.
        if re.search(
            r"\b(current|latest|today|now|price|stock|rate|web|internet|online)\b",
            user_message,
            flags=re.IGNORECASE,
        ):
            effective_user_message = f"{user_message}\n\n{load_prompt('web', 'time_sensitive_note')}"

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
        web_note = load_prompt("web", "session_note")

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

    # Web approval: [1] batch, [2] trust rest of this run, [3] per-item; or `web_auto_approve_run` in config.
    web_consent = WebConsent(
        approved_keys=set(), trust_run=bool(getattr(settings, "web_auto_approve_run", False))
    )
    max_tool_rounds = max(2, min(32, int(settings.ask_max_tool_rounds)))

    try:
        while rounds < max_tool_rounds:
            try:
                reply = prov.chat(msgs, system=sys_prompt)
            except RuntimeError as e:
                print(f"error: {e}", file=sys.stderr)
                in_t, out_t = estimate_ask_tokens(prov, sys_prompt, sess)
                return 3, in_t, out_t, int((time.perf_counter() - t_all) * 1000)

            append_assistant(sess, reply)
            msgs.append({"role": "assistant", "content": reply})

            visible, argvs, mem_ops, web_ops, mem_proposals, write_ops = split_reply_tools(reply)
            mem_fb = _mem_feedback(mem_ops) if (memory_on and mem_ops) else ""
            propose_fb = (
                _mem_propose_feedback(mem_proposals)
                if (memory_on and mem_proposals)
                else ""
            )

            tty = sys.stdin.isatty()
            exec_wanted = bool(tools and argvs)
            web_wanted = bool(web and web_ops)
            write_wanted = bool(write_ops)

            pcon, RichPanel, RichConfirm = _rich_prompt_kit()
            use_rich = pcon is not None and RichPanel is not None and RichConfirm is not None

            write_fb = ""
            if write_wanted and tty:
                write_fb = _write_feedback(
                    write_ops,
                    pcon=pcon,
                    RichPanel=RichPanel,
                    RichConfirm=RichConfirm,
                    use_rich=use_rich,
                    settings=settings,
                )

            feedback_parts: list[str] = []
            if mem_fb:
                feedback_parts.append(mem_fb)
            if propose_fb:
                feedback_parts.append(propose_fb)
            if write_fb:
                feedback_parts.append(write_fb)

            write_skip_note = (
                "*(File writing tools were skipped: stdin is not a TTY. "
                "Run in a real terminal to approve file creation.)*"
            )

            non_tty_blocks = (exec_wanted or web_wanted or write_wanted) and not tty
            if non_tty_blocks and not mem_fb and not write_fb:
                notes: list[str] = []
                if exec_wanted:
                    notes.append(shell_skip_note)
                if web_wanted:
                    notes.append(web_skip_note)
                if write_wanted:
                    notes.append(write_skip_note)
                note = "\n\n".join(notes)
                print_markdown(
                    (visible if visible.strip() else reply) + ("\n\n" + note if note else "")
                )
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
                        pcon.print(
                            RichPanel(cmd_line, title="Proposed command", border_style="yellow")
                        )
                        run = RichConfirm.ask(
                            "Execute on your machine?", default=False, console=pcon
                        )
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

                feedback_parts.append(
                    "\n\n".join(exec_parts) if exec_parts else "(no commands run)"
                )

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
                        web_consent=web_consent,
                        assistant_visible=visible,
                    )
                    feedback_parts.append(
                        "\n\n".join(web_parts) if web_parts else "(no web fetches run)"
                    )

            if feedback_parts:
                combined = "\n\n".join(p for p in feedback_parts if p)
                append_user(sess, combined)
                msgs.append({"role": "user", "content": combined})
                rounds += 1
                continue

            print_markdown(visible if visible.strip() else reply)
            in_t, out_t = estimate_ask_tokens(prov, sys_prompt, sess)
            return 0, in_t, out_t, int((time.perf_counter() - t_all) * 1000)
    except KeyboardInterrupt:
        print("\ninterrupted.", file=sys.stderr)
        in_t, out_t = estimate_ask_tokens(prov, sys_prompt, sess)
        return 1, in_t, out_t, int((time.perf_counter() - t_all) * 1000)

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
