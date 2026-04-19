"""Smoke test for Tkinter and the configuration GUI (import + minimal display init)."""

from __future__ import annotations

import os

import pytest


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _require_tkinter_import() -> None:
    try:
        import tkinter  # noqa: F401
    except ImportError as e:
        pytest.fail(
            "tkinter is required for `tlm gui`. Install Tk for your Python build "
            "(e.g. Debian/Ubuntu: sudo apt install python3-tk; Homebrew Python often "
            "lacks `_tkinter` — use distro `/usr/bin/python3` or python.org builds). "
            "To skip this check: TLM_SKIP_GUI_TESTS=1 pytest. "
            f"Original error: {e}"
        )


@pytest.mark.gui
def test_gui_stack_smoke() -> None:
    """Stdlib Tk + hidden root + `tlm.gui` import — catches missing _tkinter, Tcl/Tk, or DISPLAY."""
    if _env_truthy("TLM_SKIP_GUI_TESTS"):
        pytest.skip("TLM_SKIP_GUI_TESTS set — Tk not required for this run")
    _require_tkinter_import()
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk

    assert tk.Tk is not None
    assert ttk.Frame is not None
    assert scrolledtext.ScrolledText is not None
    assert messagebox is not None

    root = tk.Tk()
    root.withdraw()
    try:
        root.update_idletasks()
    finally:
        root.destroy()

    from tlm.gui import run_gui
    import tlm.gui.app as app

    assert callable(run_gui)
    assert callable(app.run_gui)
