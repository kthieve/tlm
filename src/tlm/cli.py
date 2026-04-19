"""CLI entry: `tlm ? …`, `tlm write …`, `tlm do …`, `tlm gui`, etc."""

from __future__ import annotations

import argparse
import select
import sys
from datetime import datetime, timezone
from pathlib import Path

from tlm import __version__
from tlm.completion import emit as emit_completion
from tlm.modes.do import run_do
from tlm.modes.write import run_write
from tlm.providers.registry import describe_providers, get_provider
from tlm.harvest import auto_harvest_session_if_due
from tlm.session import (
    Session,
    delete_session,
    list_sessions,
    load_session,
    new_session,
    pick_keyword_for,
    read_last_session_id,
    rename_session,
    resolve_session,
    save_session,
    trim_session_to_budget,
    write_last_session_id,
)
from tlm.settings import UserSettings, config_file_path, config_dir, load_settings, save_settings
from tlm.telemetry import log_event, summarize_usage

# First argv token must be one of these to use structured subcommands (else → natural-language ask).
KNOWN_SUBCOMMANDS = frozenset(
    {
        "?",
        "gui",
        "ask",
        "write",
        "do",
        "providers",
        "sessions",
        "usage",
        "completion",
        "init",
        "config",
        "new",
        "harvest",
        "help",
    }
)

def read_stdin_blob(max_chars: int = 256_000) -> str:
    """Append stdin to the prompt when it is a pipe/redirect with data ready (no hang on empty non-tty)."""
    if sys.stdin.isatty():
        return ""
    # Non-tty stdin (e.g. CI, IDE) may have no data; never block waiting for EOF.
    if hasattr(select, "select"):
        try:
            ready, _, _ = select.select([sys.stdin], [], [], 0.0)
            if not ready:
                return ""
        except (ValueError, OSError):
            return ""
    data = sys.stdin.read(max_chars)
    return data.strip()


def merge_prompt(user: str, blob: str) -> str:
    if not blob:
        return user
    if not user:
        return blob
    return f"{user}\n\n--- stdin ---\n{blob}"


def parse_ask_tokens(tokens: list[str]) -> tuple[dict, str]:
    """Parse flags for `tlm ? …` form."""
    i = 0
    opts: dict = {
        "session": None,
        "provider": None,
        "new": False,
        "last": False,
        "budget": 8000,
        "tools": True,
        "clear_context": False,
        "keyword": None,
    }
    while i < len(tokens):
        t = tokens[i]
        if t == "--session" and i + 1 < len(tokens):
            opts["session"] = tokens[i + 1]
            i += 2
            continue
        if t == "--provider" and i + 1 < len(tokens):
            opts["provider"] = tokens[i + 1]
            i += 2
            continue
        if t == "--keyword" and i + 1 < len(tokens):
            opts["keyword"] = tokens[i + 1]
            i += 2
            continue
        if t == "--new":
            opts["new"] = True
            i += 1
            continue
        if t == "--last":
            opts["last"] = True
            i += 1
            continue
        if t in ("--clear-context", "--fresh"):
            opts["clear_context"] = True
            i += 1
            continue
        if t == "--budget" and i + 1 < len(tokens):
            opts["budget"] = int(tokens[i + 1])
            i += 2
            continue
        if t == "--no-tools":
            opts["tools"] = False
            i += 1
            continue
        break
    rest = " ".join(tokens[i:]).strip()
    return opts, rest


def parse_since_days(s: str) -> int | None:
    s = s.strip().lower()
    if not s:
        return None
    if s.endswith("d"):
        return int(s[:-1])
    return int(s)


def cmd_ask(
    text: str,
    *,
    session_spec: str | None,
    provider: str | None,
    new: bool,
    last: bool,
    budget: int,
    tools: bool = True,
    clear_context: bool = False,
    new_keyword: str | None = None,
) -> int:
    blob = read_stdin_blob()
    text = merge_prompt(text, blob)
    if not text.strip():
        print("error: empty question", file=sys.stderr)
        return 2
    settings = load_settings()
    try:
        prov = get_provider(provider, settings=settings)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    prev_last = read_last_session_id()
    sess: Session | None = None

    if new:
        if settings.memory_enabled and settings.memory_harvest_on_switch and prev_last:
            old = load_session(prev_last)
            if old:
                auto_harvest_session_if_due(old, prov, settings, min_delta=1)
        kw = (new_keyword or "").strip()
        if not kw:
            try:
                kw = input("Name for this session (one word): ").strip()
            except EOFError:
                print("error: need a session name (non-interactive stdin)", file=sys.stderr)
                return 2
        sess = new_session(keyword=kw)
    elif session_spec:
        sess = resolve_session(session_spec)
        if sess is None:
            print(f"error: unknown session {session_spec!r}", file=sys.stderr)
            return 2
        if (
            settings.memory_enabled
            and settings.memory_harvest_on_switch
            and prev_last
            and sess.id != prev_last
        ):
            old = load_session(prev_last)
            if old:
                auto_harvest_session_if_due(old, prov, settings, min_delta=1)
    else:
        _ = last  # --last is legacy; default is always “continue last session”
        lid = read_last_session_id()
        sess = load_session(lid) if lid else None
        if sess is None:
            base = pick_keyword_for(text, prov)
            sess = new_session(keyword=base)

    assert sess is not None
    trim_session_to_budget(sess, budget)
    from tlm.ask_tools import run_interactive_ask

    exit_c, in_tok, out_tok, dt_ms = run_interactive_ask(
        prov,
        sess,
        text,
        tools=tools,
        settings=settings,
        clear_context=clear_context,
    )
    save_session(sess)
    write_last_session_id(sess.id)
    if exit_c == 0:
        auto_harvest_session_if_due(sess, prov, settings)
    model = getattr(prov, "model", "")
    from tlm.telemetry.prices import estimate_cost_usd

    cost = estimate_cost_usd(str(model), in_tok, out_tok)
    status = "ok" if exit_c == 0 else ("error" if exit_c == 3 else "aborted")
    log_event(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "provider": prov.id,
            "model": str(model),
            "session": sess.id,
            "in_tokens": in_tok,
            "out_tokens": out_tok,
            "ms": dt_ms,
            "status": status,
            "cost_usd": cost if exit_c == 0 else None,
        }
    )
    print(
        f"\n(session {sess.keyword}\t{sess.id}; {len(sess.messages)} messages total)",
        file=sys.stderr,
    )
    return exit_c


def cmd_providers() -> int:
    for pid, has_key, model in describe_providers():
        key = "yes" if has_key else "no"
        print(f"{pid}\tkey={key}\tmodel={model}")
    return 0


def cmd_sessions_route(ns: argparse.Namespace) -> int:
    if getattr(ns, "sessions_cmd", None) is None:
        from tlm.sessions_tui import run_sessions_tui

        return run_sessions_tui()
    return cmd_sessions_dispatch(ns)


def cmd_sessions_dispatch(ns: argparse.Namespace) -> int:
    cmd = ns.sessions_cmd
    if cmd == "list":
        for s in list_sessions():
            print(f"{s.id}\t{s.keyword}\t{s.updated}\t{s.title}")
        return 0
    sid = getattr(ns, "session_id", None)
    if cmd == "resume":
        spec = getattr(ns, "session_spec", None) or sid
        if not spec:
            print("usage: tlm sessions resume SPEC", file=sys.stderr)
            return 2
        s = resolve_session(str(spec))
        if s is None:
            print("unknown session", file=sys.stderr)
            return 2
        write_last_session_id(s.id)
        print(f"active\t{s.keyword}\t{s.id}")
        return 0
    if cmd == "show":
        s = resolve_session(str(sid)) if sid else None
        if s is None:
            print("unknown session", file=sys.stderr)
            return 2
        import json as _json

        print(_json.dumps(s.to_json(), indent=2))
        return 0
    if cmd == "delete":
        s = resolve_session(str(sid)) if sid else None
        ok = delete_session(s.id) if s else False
        if not ok:
            print("unknown session", file=sys.stderr)
            return 2
        print("deleted.")
        return 0
    if cmd == "rename":
        title = getattr(ns, "title", "")
        s = resolve_session(str(sid)) if sid else None
        if not s or not rename_session(s.id, str(title)):
            print("unknown session", file=sys.stderr)
            return 2
        print("renamed.")
        return 0
    return 2


def cmd_new_ns(ns: argparse.Namespace) -> int:
    from tlm.session import normalize_keyword

    kw = (getattr(ns, "keyword", None) or "").strip()
    if not kw:
        try:
            kw = input("Name for this session (one word): ").strip()
        except EOFError:
            print("error: need a name (non-interactive stdin)", file=sys.stderr)
            return 2
    try:
        normalize_keyword(kw)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    sess = new_session(keyword=kw)
    save_session(sess)
    write_last_session_id(sess.id)
    print(f"{sess.keyword}\t{sess.id}")
    return 0


def cmd_harvest_ns(ns: argparse.Namespace) -> int:
    settings = load_settings()
    try:
        prov = get_provider(ns.provider, settings=settings)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    from tlm.harvest import apply_harvest_items, extract_harvest_items

    targets: list[Session] = []
    if ns.harvest_all:
        targets = list_sessions()
    elif ns.spec:
        s = resolve_session(ns.spec)
        if s:
            targets.append(s)
    elif ns.session:
        s = resolve_session(ns.session)
        if s:
            targets.append(s)
    elif ns.last:
        lid = read_last_session_id()
        if lid:
            s = load_session(lid)
            if s:
                targets.append(s)
    else:
        lid = read_last_session_id()
        if lid:
            s = load_session(lid)
            if s:
                targets.append(s)

    if not targets:
        print("error: no session to harvest", file=sys.stderr)
        return 2

    for sess in targets:
        items = extract_harvest_items(prov, sess)
        if ns.dry_run:
            for it in items:
                print(it)
            continue
        accepted: list[str] = []
        for it in items:
            if not ns.yes:
                try:
                    c = input(f"Store long-term? [y/N] {it[:120]}: ").strip().lower()
                except EOFError:
                    return 1
                if c not in ("y", "yes"):
                    continue
            accepted.append(it)
        if accepted:
            apply_harvest_items(
                accepted,
                source_session=sess.id,
                settings=settings,
                push_ready_summary=True,
            )
        sess.last_harvested_at = datetime.now(timezone.utc).isoformat()
        sess.message_count_at_last_harvest = len(sess.messages)
        save_session(sess)
    return 0


def cmd_usage(ns: argparse.Namespace) -> int:
    days = parse_since_days(ns.since) if ns.since else None
    print(summarize_usage(since_days=days))
    return 0


def cmd_init() -> int:
    """Ensure XDG dirs exist; write default config.toml if missing."""
    from tlm.config import data_dir, sessions_dir, state_dir

    config_dir()
    data_dir()
    sessions_dir()
    state_dir()
    p = config_file_path()
    created = False
    if not p.is_file():
        save_settings(UserSettings(provider="openrouter", safety_profile="standard"))
        created = True
    print("tlm directories ready:", flush=True)
    print(f"  config:  {p.parent}", flush=True)
    print(f"  data:    {data_dir()}", flush=True)
    print(f"  state:   {state_dir()}", flush=True)
    if created:
        print(f"  created: {p} (default provider openrouter)", flush=True)
    else:
        print(f"  config exists: {p}", flush=True)
    from tlm.gui.dispatch import init_gui_note

    note = init_gui_note()
    if note:
        print(note, flush=True)
    return 0


def cmd_config_route(ns: argparse.Namespace) -> int:
    if getattr(ns, "config_cmd", None) == "gui":
        return run_gui_safe()
    from tlm.tui_config import run_config_tui

    return run_config_tui()


def cmd_completion(ns: argparse.Namespace) -> int:
    try:
        print(emit_completion(ns.shell))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


def cmd_write_ns(ns: argparse.Namespace) -> int:
    text = " ".join(ns.text).strip()
    blob = read_stdin_blob()
    text = merge_prompt(text, blob)
    if not text.strip():
        print("error: empty write request", file=sys.stderr)
        return 2
    settings = load_settings()
    try:
        prov = get_provider(ns.provider, settings=settings)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    base = Path(ns.dir).expanduser().resolve()
    r = run_write(
        text,
        provider=prov,
        base_dir=base,
        overwrite=bool(ns.overwrite),
        dry_run=bool(ns.dry_run),
        auto_yes=bool(ns.yes),
    )
    return r.exit_code


def cmd_do_ns(ns: argparse.Namespace) -> int:
    text = " ".join(ns.text).strip()
    blob = read_stdin_blob()
    text = merge_prompt(text, blob)
    if not text.strip():
        print("error: empty do request", file=sys.stderr)
        return 2
    settings = load_settings()
    try:
        prov = get_provider(ns.provider, settings=settings)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    cwd = Path(ns.cwd).expanduser().resolve()
    r = run_do(
        text,
        provider=prov,
        cwd=cwd,
        timeout=float(ns.timeout),
        pass_env=list(ns.pass_env or []),
        continue_on_error=bool(ns.continue_on_error),
        dry_run=bool(ns.dry_run),
        auto_yes=bool(ns.yes),
        settings=settings,
    )
    return r.exit_code


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tlm",
        description=(
            "Terminal LLM helper (Linux). Natural-language questions continue the last session; "
            "`tlm new` / `tlm sessions` manage one-word session names. "
            "Ready memory auto-injects into ask unless --clear-context; long-term memory is queried via ```tlm-mem``` "
            "blocks or `tlm harvest`."
        ),
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="cmd", required=False, metavar="COMMAND")

    sub.add_parser(
        "gui",
        help="Open settings UI (Tk or FLTK; env TLM_GUI=tk|fltk|auto; same as `tlm config gui`).",
    ).set_defaults(
        _handler=lambda _: run_gui_safe()
    )

    sub.add_parser("init", help="Create XDG dirs and default config.toml if missing.").set_defaults(
        _handler=lambda _: cmd_init()
    )

    p_cfg = sub.add_parser(
        "config",
        help="Edit settings in the terminal; `tlm config gui` opens the window UI.",
    )
    cfg_sub = p_cfg.add_subparsers(dest="config_cmd", required=False)
    cfg_sub.add_parser("gui", help="Open window UI (TLM_GUI selects Tk vs FLTK).")
    p_cfg.set_defaults(_handler=cmd_config_route)

    p_q = sub.add_parser(
        "ask",
        help="Ask the model (equivalent to `tlm ? …`). Reuses last session by default; use --new for a fresh chat.",
    )
    p_q.add_argument("--session", metavar="SPEC", default=None, help="Keyword or session id")
    p_q.add_argument("--provider", metavar="ID", default=None)
    p_q.add_argument("--new", action="store_true", help="Start a new session (prompts for one-word name if needed)")
    p_q.add_argument(
        "--keyword",
        metavar="WORD",
        dest="ask_keyword",
        default=None,
        help="With --new: one-word session name",
    )
    p_q.add_argument("--last", action="store_true", help="Continue last session (default behavior)")
    p_q.add_argument(
        "--clear-context",
        "--fresh",
        action="store_true",
        dest="clear_context",
        help="Do not inject ready memory for this question",
    )
    p_q.add_argument("--budget", type=int, default=8000, help="Trim context to ~this many heuristic tokens")
    p_q.add_argument(
        "--no-tools",
        action="store_true",
        help="Disable model-proposed shell commands (```tlm-exec``` tool loop).",
    )
    p_q.add_argument("text", nargs="*", help="Question text")
    p_q.set_defaults(
        _handler=lambda a: cmd_ask(
            " ".join(a.text).strip(),
            session_spec=a.session,
            provider=a.provider,
            new=a.new,
            last=a.last,
            budget=a.budget,
            tools=not a.no_tools,
            clear_context=bool(a.clear_context),
            new_keyword=a.ask_keyword,
        )
    )

    p_write = sub.add_parser("write", help="Code / file generation (confirm).")
    p_write.add_argument("--dir", default=".", help="Base directory for relative paths")
    p_write.add_argument("--overwrite", action="store_true")
    p_write.add_argument("--dry-run", action="store_true")
    p_write.add_argument("--yes", action="store_true", help="Auto-approve after showing preview")
    p_write.add_argument("--provider", default=None)
    p_write.add_argument("text", nargs="*", default=[])
    p_write.set_defaults(_handler=cmd_write_ns)

    p_do = sub.add_parser("do", help="Planned shell commands (confirm; no shell=True).")
    p_do.add_argument("--cwd", default=".")
    p_do.add_argument("--timeout", type=float, default=60.0)
    p_do.add_argument("--pass-env", action="append", default=[], metavar="VAR")
    p_do.add_argument("--continue-on-error", action="store_true")
    p_do.add_argument("--dry-run", action="store_true")
    p_do.add_argument("--yes", action="store_true")
    p_do.add_argument("--provider", default=None)
    p_do.add_argument("text", nargs="*", default=[])
    p_do.set_defaults(_handler=cmd_do_ns)

    sub.add_parser("providers", help="List providers, key presence, model.").set_defaults(
        _handler=lambda _: cmd_providers()
    )

    p_use = sub.add_parser("usage", help="Summarize token/cost usage from JSONL log.")
    p_use.add_argument("--since", default="30d", help='e.g. "7d" or "30d"')
    p_use.set_defaults(_handler=cmd_usage)

    p_comp = sub.add_parser("completion", help="Print shell completion script.")
    p_comp.add_argument("shell", choices=["bash", "zsh", "fish"])
    p_comp.set_defaults(_handler=cmd_completion)

    p_sess = sub.add_parser(
        "sessions",
        help="Interactive TUI when run with no arguments; or list/show/delete/rename/resume.",
        epilog="Examples: `tlm sessions` (picker), `tlm sessions list`, `tlm sessions resume work`.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sp = p_sess.add_subparsers(dest="sessions_cmd", required=False)
    sp.add_parser("list").set_defaults(_handler=cmd_sessions_dispatch)
    p_resume = sp.add_parser("resume", help="Set active session (keyword or id).")
    p_resume.add_argument("session_spec", metavar="SPEC")
    p_resume.set_defaults(_handler=cmd_sessions_dispatch)
    p_show = sp.add_parser("show")
    p_show.add_argument("session_id", metavar="SPEC")
    p_show.set_defaults(_handler=cmd_sessions_dispatch)
    p_del = sp.add_parser("delete")
    p_del.add_argument("session_id", metavar="SPEC")
    p_del.set_defaults(_handler=cmd_sessions_dispatch)
    p_ren = sp.add_parser("rename")
    p_ren.add_argument("session_id", metavar="SPEC")
    p_ren.add_argument("title")
    p_ren.set_defaults(_handler=cmd_sessions_dispatch)
    p_sess.set_defaults(_handler=cmd_sessions_route, sessions_cmd=None)

    p_new = sub.add_parser("new", help="Create a new session (one-word name); becomes active.")
    p_new.add_argument("keyword", nargs="?", default=None, help="Session keyword (prompted if omitted)")
    p_new.set_defaults(_handler=cmd_new_ns)

    p_harv = sub.add_parser(
        "harvest",
        help="Extract durable facts from session(s) into long-term memory.",
    )
    p_harv.add_argument(
        "spec",
        nargs="?",
        default=None,
        help="Session keyword or id (default: last active)",
    )
    p_harv.add_argument("--session", metavar="SPEC", default=None)
    p_harv.add_argument("--last", action="store_true", help="Use last active session")
    p_harv.add_argument("--all", action="store_true", dest="harvest_all", help="Every session")
    p_harv.add_argument("--yes", action="store_true", help="Store all safe items without prompting")
    p_harv.add_argument("--dry-run", action="store_true", help="Print model-extracted lines only")
    p_harv.add_argument("--provider", default=None)
    p_harv.set_defaults(_handler=cmd_harvest_ns)

    return p


def run_gui_safe() -> int:
    from tlm.gui.dispatch import GuiBackendError, dispatch_gui

    try:
        dispatch_gui()
    except GuiBackendError as e:
        print(f"error: {e}", file=sys.stderr)
        if e.hint:
            print(e.hint, file=sys.stderr, end="")
        return 1
    except Exception as e:
        if type(e).__name__ == "TclError":
            print(f"error: GUI failed to start ({e}). Is DISPLAY set?", file=sys.stderr)
            return 1
        raise
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()

    if not argv:
        parser.print_help()
        return 0

    if argv[0] == "help":
        parser.print_help()
        return 0

    # Natural language: `tlm show me which cpu` → ask (first token not a known subcommand).
    if argv[0] not in KNOWN_SUBCOMMANDS and not argv[0].startswith("-"):
        return cmd_ask(
            " ".join(argv).strip(),
            session_spec=None,
            provider=None,
            new=False,
            last=False,
            budget=8000,
            tools=True,
            clear_context=False,
            new_keyword=None,
        )

    if argv[0] == "?":
        opts, text = parse_ask_tokens(argv[1:])
        return cmd_ask(
            text,
            session_spec=opts["session"],
            provider=opts["provider"],
            new=opts["new"],
            last=opts["last"],
            budget=int(opts["budget"]),
            tools=opts.get("tools", True),
            clear_context=bool(opts.get("clear_context", False)),
            new_keyword=opts.get("keyword"),
        )

    args = parser.parse_args(argv)
    if getattr(args, "cmd", None) is None:
        parser.print_help()
        return 0
    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.print_help()
        return 2
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
