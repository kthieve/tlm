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
from tlm.config import default_provider
from tlm.providers.registry import (
    describe_providers,
    get_provider,
    list_remote_model_ids,
    normalize_provider_id,
    resolved_model,
)
from tlm.setup_wizard import maybe_first_run_wizard, run_setup_wizard
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
from tlm.settings import (
    UserSettings,
    config_dir,
    config_file_path,
    load_settings,
    save_settings,
    warn_config_permissions,
)
from tlm.self_update import cmd_update_ns, maybe_print_update_notice
from tlm.telemetry import log_event, summarize_usage

# First argv token must be one of these to use structured subcommands (else → natural-language ask).
KNOWN_SUBCOMMANDS = frozenset(
    {
        "?",
        "gui",
        "ask",
        "web",
        "write",
        "do",
        "providers",
        "sessions",
        "usage",
        "completion",
        "init",
        "config",
        "new",
        "clear",
        "harvest",
        "help",
        "paths",
        "allow",
        "unallow",
        "update",
        "models",
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
        "web": True,
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
        if t == "--no-web":
            opts["web"] = False
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
    web: bool = True,
    clear_context: bool = False,
    new_keyword: str | None = None,
    web_focus: bool = False,
) -> int:
    blob = read_stdin_blob()
    text = merge_prompt(text, blob)
    if not text.strip():
        print("error: empty question", file=sys.stderr)
        return 2
    settings = maybe_first_run_wizard()
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
        web=web,
        settings=settings,
        clear_context=clear_context,
        web_focus=web_focus,
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


def cmd_models_route(ns: argparse.Namespace) -> int:
    """List / set / pick models (OpenAI-compatible ``GET .../v1/models``)."""
    sub = getattr(ns, "models_cmd", None) or "pick"
    s = load_settings()
    pid = normalize_provider_id(getattr(ns, "models_provider", None) or s.provider or default_provider())

    if sub == "set":
        model = getattr(ns, "model_name", "").strip()
        if not model:
            print("error: MODEL is required", file=sys.stderr)
            return 2
        if getattr(ns, "global_model", False):
            s.model = model
        else:
            s.models[pid] = model
        save_settings(s)
        where = "global default" if getattr(ns, "global_model", False) else f"per-provider [{pid}]"
        print(f"Saved model {model!r} ({where}). Config: {config_file_path()}", file=sys.stderr)
        return 0

    try:
        ids = list_remote_model_ids(pid, settings=s)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if not ids:
        print(f"error: empty model list from provider {pid!r}", file=sys.stderr)
        return 2

    if sub == "list":
        if getattr(ns, "json_models", False):
            import json

            print(json.dumps(ids))
            return 0
        for i, mid in enumerate(ids, 1):
            print(f"{i}\t{mid}")
        return 0

    # pick (default)
    assert sub == "pick"
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        Console = None  # type: ignore[misc,assignment]
        Table = None  # type: ignore[misc,assignment]

    cur = resolved_model(pid, s)
    if Console is not None and Table is not None:
        console = Console(stderr=True)
        table = Table(title=f"Models — {pid}", show_lines=False)
        table.add_column("#", justify="right", style="dim")
        table.add_column("model id")
        for i, mid in enumerate(ids, 1):
            hint = "  (current)" if mid == cur else ""
            table.add_row(str(i), mid + hint)
        console.print(table)
    else:
        for i, mid in enumerate(ids, 1):
            mark = "\t*" if mid == cur else ""
            print(f"{i}\t{mid}{mark}", file=sys.stderr)

    try:
        raw = input("Number or full model id [empty=cancel]: ").strip()
    except EOFError:
        print("cancelled", file=sys.stderr)
        return 1
    if not raw:
        return 0

    chosen: str | None = None
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(ids):
            chosen = ids[n - 1]
    if chosen is None:
        if raw in ids:
            chosen = raw
        else:
            print(f"error: not in list: {raw!r}", file=sys.stderr)
            return 2

    if getattr(ns, "global_model", False):
        s.model = chosen
    else:
        s.models[pid] = chosen
    save_settings(s)
    scope = "global default" if getattr(ns, "global_model", False) else f"for provider {pid}"
    print(f"Saved {chosen!r} ({scope}).", file=sys.stderr)
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
        return cmd_new_context()
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


def cmd_new_context() -> int:
    """Start a fresh context by creating and activating a new session."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    sess = new_session(keyword=f"ctx{ts}")
    save_session(sess)
    write_last_session_id(sess.id)
    print(f"new context\t{sess.keyword}\t{sess.id}")
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


def cmd_init(ns: argparse.Namespace) -> int:
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

    no_wiz = bool(getattr(ns, "no_wizard", False))
    want_wiz = bool(getattr(ns, "wizard", False))
    if no_wiz:
        return 0

    def _run_wizard() -> int:
        s = load_settings()
        _out, code = run_setup_wizard(s)
        if code == 2:
            return 2
        return 0 if code == 0 else 1

    if want_wiz:
        if not sys.stdin.isatty():
            print("error: --wizard requires an interactive terminal (TTY).", file=sys.stderr)
            return 2
        return _run_wizard()

    if not sys.stdin.isatty():
        return 0

    if created:
        return _run_wizard()

    try:
        c = input("Run setup wizard now? [y/N]: ").strip().lower()
    except EOFError:
        return 0
    if c in ("y", "yes"):
        return _run_wizard()
    return 0


def cmd_config_route(ns: argparse.Namespace) -> int:
    if getattr(ns, "config_cmd", None) == "gui":
        return run_gui_safe()
    if getattr(ns, "config_cmd", None) == "migrate-keys":
        return cmd_migrate_keys()
    from tlm.tui_config import run_config_tui

    return run_config_tui()


def cmd_migrate_keys() -> int:
    try:
        import keyring  # type: ignore[import-not-found]
    except ImportError:
        print("error: install keyring: pip install 'tlm[secure]'", file=sys.stderr)
        return 2
    s = load_settings()
    if not s.api_keys:
        print("no keys in config.toml to migrate.")
        return 0
    for pid, secret in list(s.api_keys.items()):
        try:
            keyring.set_password("tlm", pid, secret)
        except Exception as e:  # noqa: BLE001
            print(f"error: keyring set {pid}: {e}", file=sys.stderr)
            return 2
        del s.api_keys[pid]
    save_settings(s)
    print("migrated API keys from config.toml to OS keyring.")
    return 0


def cmd_paths() -> int:
    from pathlib import Path

    from tlm.safety.permissions import effective_policy, load_permissions_file, permissions_file_path
    from tlm.safety.permissions import git_toplevel

    cwd = Path.cwd().resolve()
    ep = effective_policy(cwd)
    pf = load_permissions_file()
    print(f"permissions: {permissions_file_path()}")
    print(f"cwd:\t{ep.cwd}")
    print(f"project_root:\t{ep.project_root or '(none)'}")
    print(f"git_toplevel:\t{git_toplevel(cwd) or '(none)'}")
    print("kind\tsource\tpath")
    for p in pf.allow_paths:
        print(f"RW\tglobal\t{p}")
    for p in pf.read_paths:
        print(f"RO\tglobal\t{p}")
    for pr in pf.projects:
        for p in pr.allow_paths:
            print(f"RW\tproject:{pr.root}\t{p}")
        for p in pr.read_paths:
            print(f"RO\tproject:{pr.root}\t{p}")
    for p in pf.escape_grants:
        print(f"RW\tescape_grants\t{p}")
    print("--- effective (merged) ---")
    for p in ep.allow_paths:
        print(f"RW\tmerged\t{p}")
    for p in ep.read_paths:
        print(f"RO\tmerged\t{p}")
    for p in ep.escape_grants:
        print(f"RW\tescape\t{p}")
    return 0


def cmd_allow_ns(ns: argparse.Namespace) -> int:
    from pathlib import Path

    from tlm.safety.permissions import add_freelist_path

    add_freelist_path(
        ns.path,
        read_only=bool(ns.read_only),
        project=bool(ns.project),
        project_root=Path(ns.project_root).expanduser() if ns.project_root else None,
    )
    print("updated permissions.toml")
    return 0


def cmd_unallow_ns(ns: argparse.Namespace) -> int:
    from pathlib import Path

    from tlm.safety.permissions import remove_freelist_path

    ok = remove_freelist_path(
        ns.path,
        project=bool(ns.project),
        project_root=Path(ns.project_root).expanduser() if ns.project_root else None,
    )
    if not ok:
        print("path not found in allow/read/escape_grants.", file=sys.stderr)
        return 1
    print("updated permissions.toml")
    return 0


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
    settings = maybe_first_run_wizard()
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
    settings = maybe_first_run_wizard()
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

    p_init = sub.add_parser(
        "init",
        help="Create XDG dirs and default config.toml if missing; optional first-run setup wizard.",
    )
    p_init.add_argument(
        "--wizard",
        action="store_true",
        help="Run the interactive setup wizard after preparing directories.",
    )
    p_init.add_argument(
        "--no-wizard",
        action="store_true",
        help="Do not run the setup wizard (also skips the optional prompt when config already exists).",
    )
    p_init.set_defaults(_handler=cmd_init)

    p_cfg = sub.add_parser(
        "config",
        help="Edit settings in the terminal; `tlm config gui` opens the window UI.",
    )
    cfg_sub = p_cfg.add_subparsers(dest="config_cmd", required=False)
    cfg_sub.add_parser("gui", help="Open window UI (TLM_GUI selects Tk vs FLTK).")
    cfg_sub.add_parser("migrate-keys", help="Move API keys from config.toml into the OS keyring (needs [secure]).")
    p_cfg.set_defaults(_handler=cmd_config_route)

    p_q = sub.add_parser(
        "ask",
        help="Ask the model (equivalent to `tlm ? …`). Use `tlm web …` for the same flags with web tools emphasized. Reuses last session by default; use --new for a fresh chat.",
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
    p_q.add_argument(
        "--no-web",
        action="store_true",
        help="Disable model-proposed web fetches (```tlm-web```; Lightpanda).",
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
            web=not a.no_web,
            clear_context=bool(a.clear_context),
            new_keyword=a.ask_keyword,
            web_focus=False,
        )
    )

    p_web = sub.add_parser(
        "web",
        help="Ask with **web tools emphasized** (```tlm-web``` / Lightpanda). Same options as `tlm ask`.",
    )
    p_web.add_argument("--session", metavar="SPEC", default=None, help="Keyword or session id")
    p_web.add_argument("--provider", metavar="ID", default=None)
    p_web.add_argument("--new", action="store_true", help="Start a new session")
    p_web.add_argument(
        "--keyword",
        metavar="WORD",
        dest="ask_keyword",
        default=None,
        help="With --new: one-word session name",
    )
    p_web.add_argument("--last", action="store_true", help="Continue last session (default)")
    p_web.add_argument(
        "--clear-context",
        "--fresh",
        action="store_true",
        dest="clear_context",
        help="Do not inject ready memory for this question",
    )
    p_web.add_argument("--budget", type=int, default=8000, help="Trim context to ~this many heuristic tokens")
    p_web.add_argument(
        "--no-tools",
        action="store_true",
        help="Disable ```tlm-exec``` tool loop",
    )
    p_web.add_argument(
        "--no-web",
        action="store_true",
        help="Disable ```tlm-web``` (unusual for this subcommand)",
    )
    p_web.add_argument("text", nargs="*", help="Question (live web via Lightpanda when configured)")
    p_web.set_defaults(
        _handler=lambda a: cmd_ask(
            " ".join(a.text).strip(),
            session_spec=a.session,
            provider=a.provider,
            new=a.new,
            last=a.last,
            budget=a.budget,
            tools=not a.no_tools,
            web=not a.no_web,
            clear_context=bool(a.clear_context),
            new_keyword=a.ask_keyword,
            web_focus=True,
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

    p_mod = sub.add_parser(
        "models",
        help="List / pick models via provider GET /v1/models; `set` saves model id to config.",
    )
    p_mod.add_argument(
        "--provider",
        dest="models_provider",
        metavar="ID",
        default=None,
        help="Provider id (default: config provider or TLM_PROVIDER).",
    )
    p_mod.add_argument(
        "--global",
        action="store_true",
        dest="global_model",
        help="With set/pick: write global `model` instead of `[models.<provider>]`.",
    )
    msub = p_mod.add_subparsers(dest="models_cmd", required=False, metavar="SUBCOMMAND")
    p_mlist = msub.add_parser("list", help="Fetch and print remote model ids.")
    p_mlist.add_argument(
        "--json",
        action="store_true",
        dest="json_models",
        help="Print one JSON array line.",
    )
    msub.add_parser(
        "pick",
        help="Interactive picker (default when `tlm models` is run with no subcommand).",
    )
    p_mset = msub.add_parser("set", help="Save MODEL to config without calling the API.")
    p_mset.add_argument("model_name", metavar="MODEL", help="Model id (e.g. deepseek-v4-flash)")
    p_mod.set_defaults(_handler=cmd_models_route)

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

    sub.add_parser("clear", help="Start a fresh conversation context (new active session).").set_defaults(
        _handler=lambda _: cmd_new_context()
    )

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

    sub.add_parser("paths", help="Show freelist paths from permissions.toml (global, project, escape grants).").set_defaults(
        _handler=lambda _: cmd_paths()
    )

    p_allow = sub.add_parser("allow", help="Add a freelist path (RW or --read-only).")
    p_allow.add_argument("path", help="Directory path")
    p_allow.add_argument("--read-only", action="store_true", help="Read-only freelist")
    p_allow.add_argument("--project", action="store_true", help="Scope to current project root")
    p_allow.add_argument("--project-root", metavar="DIR", default=None, help="Explicit project root")
    p_allow.set_defaults(_handler=cmd_allow_ns)

    p_un = sub.add_parser("unallow", help="Remove a path from freelist or escape_grants.")
    p_un.add_argument("path")
    p_un.add_argument("--project", action="store_true")
    p_un.add_argument("--project-root", metavar="DIR", default=None)
    p_un.set_defaults(_handler=cmd_unallow_ns)

    p_upd = sub.add_parser(
        "update",
        help="Reinstall tlm from GitHub (pipx or ~/.local/share/tlm-venv); use --yes to run.",
    )
    p_upd.add_argument(
        "--ref",
        dest="update_ref",
        metavar="GIT_REF",
        default=None,
        help='Git ref (default: latest GitHub release tag), e.g. main',
    )
    p_upd.add_argument(
        "--version",
        dest="update_version",
        metavar="VER",
        default=None,
        help="Version like 0.2.0b2 (implies tag v…); overrides --ref",
    )
    p_upd.add_argument(
        "--yes",
        action="store_true",
        help="Run pipx/pip after showing the command",
    )
    p_upd.set_defaults(_handler=lambda a: cmd_update_ns(a, load_settings()))

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
    warn_config_permissions()
    if argv:
        maybe_print_update_notice(load_settings(), argv0=argv[0])
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
            web=True,
            clear_context=False,
            new_keyword=None,
            web_focus=False,
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
            web=opts.get("web", True),
            clear_context=bool(opts.get("clear_context", False)),
            new_keyword=opts.get("keyword"),
            web_focus=False,
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
