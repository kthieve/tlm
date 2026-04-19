"""Interactive terminal UI for `tlm sessions` (no subcommand)."""

from __future__ import annotations

import sys

from tlm.harvest import auto_harvest_session_if_due, extract_harvest_items
from tlm.providers.registry import get_provider
from tlm.session import (
    delete_session,
    list_sessions,
    load_session,
    new_session,
    normalize_keyword,
    read_last_session_id,
    rename_session,
    save_session,
    write_last_session_id,
)
from tlm.settings import load_settings


def _print_table(sessions: list) -> None:
    print("\n#   keyword      updated                      msgs  title", flush=True)
    for i, s in enumerate(sessions, start=1):
        title = (s.title or "")[:40]
        print(
            f"{i:<3} {s.keyword:<12} {s.updated:<28} {len(s.messages):<5} {title}",
            flush=True,
        )
    print(
        "\n[#] resume   d <#> delete   r <#> rename   n new   "
        "h <#> harvest   q quit",
        flush=True,
    )


def run_sessions_tui() -> int:
    settings = load_settings()
    try:
        prov = get_provider(None, settings=settings)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    while True:
        sessions = list_sessions()
        if not sessions:
            print("(no sessions yet; use `n` to create one)", flush=True)
        else:
            _print_table(sessions)
        cur = read_last_session_id()
        if cur:
            cs = load_session(cur)
            if cs:
                print(f"\nActive session: {cs.keyword} ({cs.id})", flush=True)

        try:
            line = input("\n> ").strip()
        except EOFError:
            print("", flush=True)
            return 0

        if not line or line.lower() in ("q", "quit"):
            return 0

        if line.lower() == "n":
            try:
                kw = input("Name for this session (one word): ").strip()
            except EOFError:
                return 1
            try:
                normalize_keyword(kw)
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                continue
            sess = new_session(keyword=kw)
            save_session(sess)
            write_last_session_id(sess.id)
            print(f"Created {sess.keyword} ({sess.id})", flush=True)
            continue

        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if cmd.isdigit():
            idx = int(cmd)
            if idx < 1 or idx > len(sessions):
                print("invalid #", file=sys.stderr)
                continue
            sid = sessions[idx - 1].id
            write_last_session_id(sid)
            s = load_session(sid)
            print(f"Resumed {s.keyword if s else sid}", flush=True)
            continue

        if cmd == "d" and rest.isdigit():
            idx = int(rest)
            if idx < 1 or idx > len(sessions):
                print("invalid #", file=sys.stderr)
                continue
            sid = sessions[idx - 1].id
            if delete_session(sid):
                print("Deleted.", flush=True)
            else:
                print("delete failed", file=sys.stderr)
            continue

        if cmd == "r" and rest:
            sub = rest.split(maxsplit=1)
            if not sub[0].isdigit():
                print("usage: r <#> new title", file=sys.stderr)
                continue
            idx = int(sub[0])
            new_title = sub[1].strip() if len(sub) > 1 else ""
            if idx < 1 or idx > len(sessions) or not new_title:
                print("usage: r <#> new title", file=sys.stderr)
                continue
            sid = sessions[idx - 1].id
            if rename_session(sid, new_title):
                print("Renamed.", flush=True)
            else:
                print("rename failed", file=sys.stderr)
            continue

        if cmd == "h" and rest.isdigit():
            idx = int(rest)
            if idx < 1 or idx > len(sessions):
                print("invalid #", file=sys.stderr)
                continue
            sid = sessions[idx - 1].id
            sess = load_session(sid)
            if sess is None:
                print("session not found", file=sys.stderr)
                continue
            items = extract_harvest_items(prov, sess)
            if not items:
                print("(nothing to harvest)", flush=True)
                continue
            for it in items:
                try:
                    c = input(f"Store long-term? [y/N] {it[:100]}: ").strip().lower()
                except EOFError:
                    return 1
                if c not in ("y", "yes"):
                    continue
                from tlm.harvest import apply_harvest_items

                apply_harvest_items(
                    [it],
                    source_session=sess.id,
                    settings=settings,
                    push_ready_summary=False,
                )
            from datetime import datetime, timezone

            sess.last_harvested_at = datetime.now(timezone.utc).isoformat()
            sess.message_count_at_last_harvest = len(sess.messages)
            save_session(sess)
            print("Harvest done.", flush=True)
            continue

        print("Unknown action. Try a number to resume, d 2, r 2 title, n, h 2, q.", file=sys.stderr)
