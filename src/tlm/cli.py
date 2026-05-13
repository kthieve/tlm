"""CLI entry: `tlm ? …`, `tlm write …`, `tlm do …`, `tlm gui`, etc."""

from __future__ import annotations

import argparse
import select
import sys
import time
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
        "auth",
        "undo",
        "stop",
        "versionlog",
        "wizard",
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
    pid = normalize_provider_id(
        getattr(ns, "models_provider", None) or s.provider or default_provider()
    )

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
    if getattr(ns, "dry_run", False):
        print(f"tlm new [DRY RUN]: would create session {kw!r}")
        return 0
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
    from tlm.config import data_dir, prompts_dir, sessions_dir, state_dir

    p = config_file_path()
    if getattr(ns, "dry_run", False):
        print("tlm init [DRY RUN]:")
        print(
            f"  would create/ensure dirs: {p.parent}, {prompts_dir()}, {data_dir()}, {sessions_dir()}, {state_dir()}"
        )
        if not p.is_file():
            print(f"  would create default config: {p}")
        return 0

    config_dir()
    data_dir()
    sessions_dir()
    state_dir()
    created = False
    if not p.is_file():
        save_settings(UserSettings(provider="openrouter", safety_profile="standard"))
        created = True
    print("tlm directories ready:", flush=True)
    print(f"  config:  {p.parent}", flush=True)
    print(f"  prompts: {prompts_dir()}", flush=True)
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

    from tlm.prompts import init_prompts

    init_prompts()

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


def cmd_wizard() -> int:
    """Explicitly re-run the setup wizard."""
    if not sys.stdin.isatty():
        print("error: wizard requires an interactive terminal (TTY).", file=sys.stderr)
        return 2
    s = load_settings()
    _out, code = run_setup_wizard(s)
    if code == 2:
        return 2
    return 0 if code == 0 else 1


def cmd_config_route(ns: argparse.Namespace) -> int:
    if getattr(ns, "config_cmd", None) == "gui":
        return run_gui_safe()
    if getattr(ns, "config_cmd", None) == "migrate-keys":
        return cmd_migrate_keys()

    try:
        from tlm.tui.app import run_tui_app

        return run_tui_app()
    except (ImportError, Exception):
        # Fallback to simple TUI if textual is missing or fails
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

    from tlm.safety.permissions import (
        effective_policy,
        load_permissions_file,
        permissions_file_path,
    )
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

    if getattr(ns, "dry_run", False):
        kind = "RO" if bool(ns.read_only) else "RW"
        scope = f"project:{ns.project_root or '.'}" if bool(ns.project) else "global"
        print(f"(dry-run) would add {kind} path {ns.path} to {scope} permissions.")
        return 0

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

    if getattr(ns, "dry_run", False):
        scope = f"project:{ns.project_root or '.'}" if bool(ns.project) else "global"
        print(f"(dry-run) would remove path {ns.path} from {scope} permissions.")
        return 0

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


def authenticate_tier(target_tier: int, settings: UserSettings) -> bool:
    """If a password is set and tier <= 1, prompt for authentication (persists via session token)."""
    if not settings.auth_password_hash or target_tier > 1:
        return True

    from tlm.safety.auth_session import validate_auth_token, create_auth_token

    if validate_auth_token():
        return True

    import getpass
    from tlm.safety.auth import verify_password

    try:
        p = getpass.getpass(f"Tier {target_tier} Access Required. Enter Password: ")
        if verify_password(p, settings.auth_password_hash):
            create_auth_token(ttl_minutes=settings.auth_timeout_minutes)
            return True
        print("Incorrect password.", file=sys.stderr)
    except EOFError:
        print("\nAuthentication required.", file=sys.stderr)

    return False


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

    from tlm.safety.profiles import normalize_profile

    profile = normalize_profile(settings.safety_profile)
    if not authenticate_tier(profile.tier, settings):
        return 1

    base = Path(ns.dir).expanduser().resolve()
    r = run_write(
        text,
        provider=prov,
        base_dir=base,
        overwrite=bool(ns.overwrite),
        dry_run=bool(ns.dry_run),
        auto_yes=bool(ns.yes),
        settings=settings,
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

    from tlm.safety.profiles import normalize_profile

    profile = normalize_profile(settings.safety_profile)
    if not authenticate_tier(profile.tier, settings):
        return 1

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
    try:
        from rich_argparse import RichHelpFormatter, RawDescriptionRichHelpFormatter
        fmt_cls = RichHelpFormatter
        raw_fmt_cls = RawDescriptionRichHelpFormatter
    except ImportError:
        fmt_cls = argparse.HelpFormatter
        raw_fmt_cls = argparse.RawDescriptionHelpFormatter

    p = argparse.ArgumentParser(
        prog="tlm",
        description=(
            "Terminal LLM helper (Linux). Natural-language questions continue the last session; "
            "`tlm new` / `tlm sessions` manage one-word session names. "
            "Ready memory auto-injects into ask unless --clear-context; long-term memory is queried via ```tlm-mem``` "
            "blocks or `tlm harvest`."
        ),
        formatter_class=fmt_cls,
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="cmd", required=False, metavar="COMMAND")

    sub.add_parser(
        "gui",
        help="Open settings UI (Tk or FLTK; env TLM_GUI=tk|fltk|auto; same as `tlm config gui`).",
    ).set_defaults(_handler=lambda _: run_gui_safe())

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
    p_init.add_argument(
        "--dry-run", action="store_true", help="Show what would be created without writing."
    )
    p_init.set_defaults(_handler=cmd_init)

    p_cfg = sub.add_parser(
        "config",
        help="Edit settings in the terminal; `tlm config gui` opens the window UI.",
    )
    cfg_sub = p_cfg.add_subparsers(dest="config_cmd", required=False)
    cfg_sub.add_parser("gui", help="Open window UI (TLM_GUI selects Tk vs FLTK).")
    cfg_sub.add_parser(
        "migrate-keys", help="Move API keys from config.toml into the OS keyring (needs [secure])."
    )
    p_cfg.set_defaults(_handler=cmd_config_route)

    p_q = sub.add_parser(
        "ask",
        help="Ask the model (equivalent to `tlm ? …`). Use `tlm web …` for the same flags with web tools emphasized. Reuses last session by default; use --new for a fresh chat.",
    )
    p_q.add_argument("--session", metavar="SPEC", default=None, help="Keyword or session id")
    p_q.add_argument("--provider", metavar="ID", default=None)
    p_q.add_argument(
        "--new",
        action="store_true",
        help="Start a new session (prompts for one-word name if needed)",
    )
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
    p_q.add_argument(
        "--budget", type=int, default=8000, help="Trim context to ~this many heuristic tokens"
    )
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
    p_web.add_argument(
        "--budget", type=int, default=8000, help="Trim context to ~this many heuristic tokens"
    )
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
        formatter_class=raw_fmt_cls,
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
    p_new.add_argument(
        "keyword", nargs="?", default=None, help="Session keyword (prompted if omitted)"
    )
    p_new.add_argument(
        "--dry-run", action="store_true", help="Show what would be created without writing."
    )
    p_new.set_defaults(_handler=cmd_new_ns)

    p_mem = sub.add_parser("memory", help="Manage tlm memory (ready items, long-term, rules).")
    msub = p_mem.add_subparsers(dest="memory_cmd", required=False)
    
    # Ready items
    p_mready = msub.add_parser("ready", help="List or add ready memory items.")
    p_mready.add_argument("text", nargs="?", help="If provided, add this to ready memory.")
    
    # Rules
    p_mrules = msub.add_parser("rules", help="Manage memory storage rules.")
    rsub = p_mrules.add_subparsers(dest="rules_cmd", required=False)
    rsub.add_parser("list", help="List all active memory rules.")
    p_radd = rsub.add_parser("add", help="Add a new memory rule.")
    p_radd.add_argument("text", help="Rule description text.")
    p_radd.add_argument("--type", choices=["store", "never"], default="store", help="Rule type.")
    p_rdel = rsub.add_parser("delete", help="Delete a memory rule by id.")
    p_rdel.add_argument("id", help="Rule ID.")
    rsub.add_parser("reset", help="Reset rules to defaults.")
    
    p_mem.add_argument("--dry-run", action="store_true", help="Show what would change.")
    p_mem.set_defaults(_handler=cmd_memory_ns)

    sub.add_parser(
        "clear", help="Start a fresh conversation context (new active session)."
    ).set_defaults(_handler=lambda _: cmd_new_context())

    p_auth = sub.add_parser(
        "auth",
        help="Manage password protection and recovery keys for sensitive Tiers.",
    )
    asub = p_auth.add_subparsers(dest="auth_cmd", required=False)
    asub.add_parser("set-password", help="Set or change the master password.")
    asub.add_parser("recover", help="Reset password using the Master Recovery Key.")
    asub.add_parser("login", help="Authenticate and create a persistent session token.")
    asub.add_parser("logout", help="Revoke the current session token.")
    asub.add_parser("status", help="Show current authentication and session status.")
    p_auth.add_argument(
        "--dry-run", action="store_true", help="Show what would be changed without writing."
    )
    p_auth.set_defaults(_handler=cmd_auth_ns)

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

    sub.add_parser(
        "paths", help="Show freelist paths from permissions.toml (global, project, escape grants)."
    ).set_defaults(_handler=lambda _: cmd_paths())

    p_allow = sub.add_parser("allow", help="Add a freelist path (RW or --read-only).")
    p_allow.add_argument("path", help="Directory path")
    p_allow.add_argument("--read-only", action="store_true", help="Read-only freelist")
    p_allow.add_argument("--project", action="store_true", help="Scope to current project root")
    p_allow.add_argument(
        "--project-root", metavar="DIR", default=None, help="Explicit project root"
    )
    p_allow.add_argument(
        "--dry-run", action="store_true", help="Show what would be added without writing"
    )
    p_allow.set_defaults(_handler=cmd_allow_ns)

    p_un = sub.add_parser("unallow", help="Remove a path from freelist or escape_grants.")
    p_un.add_argument("path")
    p_un.add_argument("--project", action="store_true")
    p_un.add_argument("--project-root", metavar="DIR", default=None)
    p_un.add_argument(
        "--dry-run", action="store_true", help="Show what would be removed without writing"
    )
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
        help="Git ref (default: latest GitHub release tag), e.g. main",
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

    p_undo = sub.add_parser("undo", help="Revert the workspace to a previous snapshot.")
    p_undo.add_argument(
        "snapshot_id",
        nargs="?",
        help="Specific snapshot ID. If omitted, prompts with a list of recent snapshots.",
    )
    p_undo.add_argument("--dir", default=".", help="Base directory of the workspace")
    p_undo.add_argument("--list", action="store_true", help="List all available snapshots")
    p_undo.add_argument("--hard", action="store_true", help="Skip confirmation prompt")
    p_undo.add_argument(
        "--dry-run", action="store_true", help="Show what would be restored without acting"
    )
    p_undo.set_defaults(_handler=cmd_undo_ns)

    p_stop = sub.add_parser(
        "stop", help="Hard-kill runaway processes and clean up temporary stages."
    )
    p_stop.add_argument("--dir", default=".", help="Base directory of the workspace")
    p_stop.add_argument("--signal", default="KILL", help="Signal to send (TERM, KILL, etc.)")
    p_stop.add_argument(
        "--dry-run", action="store_true", help="Show what would be stopped without acting"
    )
    p_stop.set_defaults(_handler=cmd_stop_ns)

    p_versionlog = sub.add_parser("versionlog", help="View the version changes (changelog).")
    p_versionlog.set_defaults(_handler=cmd_versionlog_ns)

    sub.add_parser("wizard", help="Re-run the interactive setup wizard.").set_defaults(
        _handler=lambda _: cmd_wizard()
    )

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


def cmd_undo_ns(ns: argparse.Namespace) -> int:
    from tlm.safety.snapshot import list_snapshots, restore_snapshot
    from rich.console import Console
    from rich.table import Table
    import sys

    console = Console()
    base = Path(ns.dir).expanduser().resolve()

    snapshots = list_snapshots(base)

    if ns.list:
        if not snapshots:
            print("No snapshots found.")
            return 0
        table = Table(title=f"Snapshots in {base}")
        table.add_column("Index", justify="right", style="cyan")
        table.add_column("ID", style="magenta")
        table.add_column("Type", style="green")
        table.add_column("Message")
        table.add_column("Date", style="blue")

        for i, s in enumerate(snapshots):
            table.add_row(
                str(i + 1), s.id, "Git" if s.is_git else "File", s.message, time.ctime(s.timestamp)
            )
        console.print(table)
        return 0

    snapshot_id = ns.snapshot_id
    if not snapshot_id:
        if not snapshots:
            print("error: no snapshots found.", file=sys.stderr)
            return 2

        # Interactive pick
        print(f"Recent snapshots in {base}:")
        for i, s in enumerate(snapshots[:10]):
            print(f" [{i + 1}] {s.id} ({'Git' if s.is_git else 'File'}) - {s.message}")

        try:
            val = input("\nPick a snapshot to restore (1-10) or 'q' to quit: ").strip().lower()
            if val == "q" or not val:
                return 0
            idx = int(val) - 1
            if 0 <= idx < len(snapshots):
                snapshot_id = snapshots[idx].id
            else:
                print("Invalid choice.")
                return 1
        except (ValueError, EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return 1

    # Find the snapshot for metadata
    target = next((s for s in snapshots if s.id == snapshot_id), None)
    if not target:
        print(f"error: snapshot {snapshot_id} not found.", file=sys.stderr)
        return 1

    if ns.dry_run:
        from tlm.safety.snapshot import diff_snapshot

        print(f"[DRY-RUN] Would restore snapshot {snapshot_id}: {target.message}")
        print("--- changes ---")
        print(diff_snapshot(base, snapshot_id))
        return 0

    if not ns.hard:
        confirm = (
            input(f"Restore workspace to {snapshot_id} ({target.message})? [y/N]: ").strip().lower()
        )
        if confirm != "y":
            print("Aborted.")
            return 0

    ok = restore_snapshot(base, snapshot_id)
    if ok:
        print(f"Successfully restored to snapshot {snapshot_id}")
        return 0
    else:
        print(f"error: failed to restore snapshot {snapshot_id}", file=sys.stderr)
        return 1


def cmd_stop_ns(ns: argparse.Namespace) -> int:
    """Hard-kill runaway processes and clean up temporary stages."""
    import signal
    import shutil
    from tlm.safety.proctrack import list_processes, kill_all

    base = Path(ns.dir).expanduser().resolve()

    # Resolve signal
    sig_name = ns.signal.upper()
    if not sig_name.startswith("SIG"):
        sig_name = f"SIG{sig_name}"
    try:
        sig = getattr(signal, sig_name)
    except AttributeError:
        print(f"error: unknown signal {ns.signal}")
        return 1

    procs = list_processes(base)
    if not procs:
        print(f"No tracked processes found in {base}.")
    else:
        print(f"Found {len(procs)} active processes:")
        for p in procs:
            print(f"  [{p.proc_id[:8]}] PID {p.pid} (PGID {p.pgid}): {' '.join(p.argv)}")

        if ns.dry_run:
            print(f"[DRY-RUN] Would send {sig_name} to these process groups.")
        else:
            count = kill_all(base, sig=sig)
            print(f"Signaled {count} process groups.")

    # Always clean up .tlm/tmp
    tlm_tmp = base / ".tlm" / "tmp"
    if tlm_tmp.exists():
        if ns.dry_run:
            print(f"[DRY-RUN] Would clean up {tlm_tmp}")
        else:
            print(f"Cleaning up {tlm_tmp}...")
            try:
                # We keep the procs dir if we didn't kill anything?
                # No, stop means stop everything.
                shutil.rmtree(tlm_tmp)
                tlm_tmp.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                print(f"error: failed to clean up {tlm_tmp}: {e}")
                return 1

    print("Done.")
    return 0


def cmd_auth_ns(ns: argparse.Namespace) -> int:
    import getpass
    from tlm.safety.auth import (
        hash_password,
        generate_recovery_key,
        hash_recovery_key,
        verify_recovery_key,
    )
    from tlm.settings import load_settings, save_settings
    from tlm.cli_auth import authenticate_tier

    cmd = getattr(ns, "auth_cmd", None)
    s = load_settings()

    if cmd == "set-password":
        p1 = getpass.getpass("Enter new password: ")
        if not p1:
            print("Password cannot be empty.")
            return 2
        p2 = getpass.getpass("Confirm password: ")
        if p1 != p2:
            print("Passwords do not match.")
            return 2

        if getattr(ns, "dry_run", False):
            print(f"[DRY-RUN] would set password and generate recovery key for config: {config_file_path()}")
            return 0

        s.auth_password_hash = hash_password(p1)
        rk = generate_recovery_key()
        s.auth_recovery_hash = hash_recovery_key(rk)
        save_settings(s)
        print("\nPassword set successfully.")
        print(f"MASTER RECOVERY KEY: {rk}")
        print("STORE THIS KEY OFFLINE. It is the only way to reset your password if lost.")
        return 0

    if cmd == "recover":
        key = input("Enter Master Recovery Key: ").strip()
        if not s.auth_recovery_hash or not verify_recovery_key(key, s.auth_recovery_hash):
            print("Invalid recovery key.")
            return 1

        if getattr(ns, "dry_run", False):
            print("[DRY-RUN] recovery successful (simulated). would prompt for new password.")
            return 0

        print("Recovery successful. Please set a new password.")
        # We don't save s.auth_password_hash = None here to avoid persistence without new pass.
        # Just call set-password directly.
        return cmd_auth_ns(argparse.Namespace(auth_cmd="set-password", dry_run=False))

    if cmd == "login":
        if not s.auth_password_hash:
            print("No password set. Use `tlm auth set-password` first.")
            return 1
        if authenticate_tier(0, s):
            print("Login successful.")
            return 0
        return 1

    if cmd == "logout":
        from tlm.safety.auth_session import revoke_auth_token

        revoke_auth_token()
        print("Logged out.")
        return 0

    if cmd == "status":
        from tlm.safety.auth_session import get_token_expiry

        status = "Password Set" if s.auth_password_hash else "No Password"
        print(f"Auth Status: {status}")

        expiry = get_token_expiry()
        if expiry:
            remaining = int((expiry - time.time()) / 60)
            if remaining > 0:
                print(f"Session Token: Active (expires in ~{remaining}m)")
            else:
                print("Session Token: Expired")
        else:
            print("Session Token: None")
        return 0

    return 2


def cmd_memory_ns(ns: argparse.Namespace) -> int:
    from tlm.memory_rules import load_memory_rules, save_memory_rules, MemoryRule, DEFAULT_RULES
    import uuid

    cmd = getattr(ns, "memory_cmd", None)
    if not cmd:
        print("Use `tlm memory ready` or `tlm memory rules`.")
        return 0

    if cmd == "ready":
        from tlm.memory import load_ready, append_ready
        from tlm.settings import load_settings
        if ns.text:
            if getattr(ns, "dry_run", False):
                print(f"[DRY-RUN] Would add to ready memory: {ns.text}")
                return 0
            st = load_settings()
            append_ready([ns.text], budget_chars=st.memory_ready_budget_chars)
            print("Added to ready memory.")
        else:
            items = load_ready()
            if not items:
                print("Ready memory is empty.")
            for i, item in enumerate(items, start=1):
                print(f"{i}. {item}")
        return 0

    if cmd == "rules":
        rcmd = getattr(ns, "rules_cmd", "list") or "list"
        rules = load_memory_rules()

        if rcmd == "list":
            from rich.console import Console
            from rich.table import Table
            console = Console()
            table = Table(title="Memory Rules")
            table.add_column("ID", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Rule Text")
            for r in rules:
                table.add_row(r.id, r.type, r.text)
            console.print(table)
            return 0

        if rcmd == "add":
            if getattr(ns, "dry_run", False):
                print(f"[DRY-RUN] Would add rule: {ns.text} ({ns.type})")
                return 0
            new_id = f"rule_{uuid.uuid4().hex[:8]}"
            rules.append(MemoryRule(id=new_id, text=ns.text, type=ns.type))
            save_memory_rules(rules)
            print(f"Added rule {new_id}")
            return 0

        if rcmd == "delete":
            if getattr(ns, "dry_run", False):
                print(f"[DRY-RUN] Would delete rule: {ns.id}")
                return 0
            new_rules = [r for r in rules if r.id != ns.id]
            if len(new_rules) == len(rules):
                print(f"error: rule {ns.id} not found.")
                return 1
            save_memory_rules(new_rules)
            print(f"Deleted rule {ns.id}")
            return 0

        if rcmd == "reset":
            if getattr(ns, "dry_run", False):
                print("[DRY-RUN] Would reset rules to defaults.")
                return 0
            save_memory_rules(list(DEFAULT_RULES))
            print("Reset rules to defaults.")
            return 0

    return 0


def cmd_versionlog_ns(ns: argparse.Namespace) -> int:
    try:
        from rich.console import Console
        from rich.markdown import Markdown
    except ImportError:
        Console = None  # type: ignore

    from pathlib import Path
    import urllib.request

    project_root = Path(__file__).resolve().parent.parent.parent
    local_cl = project_root / "CHANGELOG.md"

    if local_cl.is_file():
        text = local_cl.read_text(encoding="utf-8")
    else:
        try:
            url = "https://raw.githubusercontent.com/kthieve/tlm/main/CHANGELOG.md"
            req = urllib.request.Request(url, headers={"User-Agent": "tlm-cli"})
            with urllib.request.urlopen(req, timeout=5.0) as response:
                text = response.read().decode("utf-8")
        except Exception as e:
            print(f"error: could not fetch changelog: {e}", file=sys.stderr)
            return 2

    if Console is not None:
        console = Console()
        console.print(Markdown(text))
    else:
        print(text)
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
        try:
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
        except KeyboardInterrupt:
            print("\ninterrupted.", file=sys.stderr)
            return 1

    if argv[0] == "?":
        opts, text = parse_ask_tokens(argv[1:])
        try:
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
        except KeyboardInterrupt:
            print("\ninterrupted.", file=sys.stderr)
            return 1

    args = parser.parse_args(argv)
    if getattr(args, "cmd", None) is None:
        parser.print_help()
        return 0
    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.print_help()
        return 2

    try:
        return int(handler(args))
    except KeyboardInterrupt:
        print("\ninterrupted.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
