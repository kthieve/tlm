"""Choose Tk vs FLTK for `tlm gui` (see TLM_GUI / TLM_GUI_BACKEND)."""

from __future__ import annotations

import os

from tlm.gui.availability import fltk_available, tkinter_available

# Mirrors cli hints; shown when a backend is missing.
TKINTER_UNAVAILABLE_HINT = (
    "  Tkinter is not a pip package — install OS bindings (e.g. Debian/Ubuntu: "
    "sudo apt install python3-tk), then recreate .venv with that interpreter "
    "(often /usr/bin/python3). Homebrew Python often omits Tk.\n"
    "  Terminal settings: tlm config"
)

FLTK_UNAVAILABLE_HINT = (
    "  FLTK UI: pip install \"tlm[gui-fltk]\" and install FLTK development files "
    "so fltk-config is on PATH (version 1.4.x; e.g. Debian: libfltk1.3-dev or fltk1.4).\n"
    "  Or set TLM_GUI=tk with a Python that includes tkinter."
)


class GuiBackendError(Exception):
    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.hint = hint


def gui_backend_preference() -> str:
    v = (os.environ.get("TLM_GUI") or os.environ.get("TLM_GUI_BACKEND") or "auto").strip().lower()
    if v in ("tk", "fltk", "auto"):
        return v
    return "auto"


def _run_tk() -> None:
    from tlm.gui.app import run_gui as run_tk

    run_tk()


def _run_fltk() -> None:
    from tlm.gui.app_fltk import run_gui_fltk

    run_gui_fltk()


def dispatch_gui() -> None:
    pref = gui_backend_preference()
    tk_ok = tkinter_available()
    fl_ok = fltk_available()

    if pref == "auto":
        if tk_ok:
            _run_tk()
            return
        if fl_ok:
            _run_fltk()
            return
        raise GuiBackendError(
            "no GUI backend available (tkinter and pyfltk/FLTK both unavailable).",
            hint=TKINTER_UNAVAILABLE_HINT + "\n" + FLTK_UNAVAILABLE_HINT,
        )

    if pref == "tk":
        if not tk_ok:
            raise GuiBackendError("tkinter not available.", hint=TKINTER_UNAVAILABLE_HINT)
        _run_tk()
        return

    if pref == "fltk":
        if not fl_ok:
            raise GuiBackendError("pyfltk not available (or FLTK not built).", hint=FLTK_UNAVAILABLE_HINT)
        _run_fltk()
        return

    raise GuiBackendError(f"invalid TLM_GUI={pref!r} (use tk, fltk, or auto).")


def init_gui_note() -> str | None:
    """Return a note for `tlm init` when no GUI backend is usable, else None."""
    if tkinter_available() or fltk_available():
        return None
    return (
        "note: no window UI backend (tkinter and pyfltk both unavailable).\n"
        + TKINTER_UNAVAILABLE_HINT
        + "\n"
        + FLTK_UNAVAILABLE_HINT
    )
