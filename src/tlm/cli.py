"""CLI entry: `tlm ? …`, `tlm write …`, `tlm do …`, `tlm gui`."""

from __future__ import annotations

import argparse
import sys

from tlm import __version__
from tlm.providers import get_provider
from tlm.session import load_session, new_session, save_session
from tlm.safety import check_command_line, split_for_preview


def _prompt_yes(question: str) -> bool:
    try:
        ans = input(f"{question} [y/N]: ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def cmd_ask(text: str, *, session_id: str | None, provider: str | None) -> int:
    if not text.strip():
        print("error: empty question", file=sys.stderr)
        return 2
    sess = load_session(session_id) if session_id else new_session()
    if session_id and sess is None:
        print(f"error: unknown session {session_id}", file=sys.stderr)
        return 2
    if sess is None:
        sess = new_session()
    prov = get_provider(provider)
    reply = prov.complete(text, system="You are tlm, a helpful Linux-oriented assistant.")
    sess.messages.append({"role": "user", "content": text})
    sess.messages.append({"role": "assistant", "content": reply})
    save_session(sess)
    print(reply)
    print(f"\n(session {sess.id}; {len(sess.messages)} messages total)", file=sys.stderr)
    return 0


def cmd_write(text: str) -> int:
    if not text.strip():
        print("error: empty write request", file=sys.stderr)
        return 2
    print("--- proposed action (write mode) ---")
    print(f"Request: {text}")
    print("(stub) No files written. Future: show paths + diff, then require explicit approval.")
    if not _prompt_yes("Approve this write plan?"):
        print("cancelled.")
        return 1
    print("Still stub — implement file generation behind the same gate.")
    return 0


def cmd_do(text: str) -> int:
    if not text.strip():
        print("error: empty command", file=sys.stderr)
        return 2
    ok, reason = check_command_line(text)
    if not ok:
        print(f"error: {reason}", file=sys.stderr)
        return 2
    try:
        argv = split_for_preview(text)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print("--- proposed execution ---")
    print("argv:", argv)
    if not _prompt_yes("Run this command?"):
        print("cancelled.")
        return 1
    print("(stub) Execution not implemented — wire subprocess with timeout, no shell=True.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tlm", description="Terminal LLM helper (Linux).")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="cmd", required=True)

    p_gui = sub.add_parser("gui", help="Open Tk configuration UI.")
    p_gui.set_defaults(_handler=lambda _: run_gui_safe())

    p_q = sub.add_parser("ask", help="Ask the model (equivalent to `tlm ? …`).")
    p_q.add_argument("text", nargs=argparse.REMAINDER, help="Question text")
    p_q.add_argument("--session", metavar="ID", help="Continue an existing session")
    p_q.add_argument("--provider", metavar="ID", help="Override TLM_PROVIDER")
    p_q.set_defaults(_handler=lambda a: cmd_ask(" ".join(a.text).strip(), session_id=a.session, provider=a.provider))

    p_write = sub.add_parser("write", help="Code / file generation (always confirm).")
    p_write.add_argument("text", nargs=argparse.REMAINDER, help="What to write")
    p_write.set_defaults(_handler=lambda a: cmd_write(" ".join(a.text).strip()))

    p_do = sub.add_parser("do", help="Run shell command after denylist check + confirm.")
    p_do.add_argument("text", nargs=argparse.REMAINDER, help="Command line")
    p_do.set_defaults(_handler=lambda a: cmd_do(" ".join(a.text).strip()))

    return p


def run_gui_safe() -> int:
    from tlm.gui import run_gui

    run_gui()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Support `tlm ? question` without a subparser named `?` (invalid Python identifier).
    if argv and argv[0] == "?":
        text = " ".join(argv[1:]).strip()
        return cmd_ask(text, session_id=None, provider=None)

    args = build_parser().parse_args(argv)
    handler = getattr(args, "_handler", None)
    if handler is None:
        return 2
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
