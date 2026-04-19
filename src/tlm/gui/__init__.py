"""Configuration GUI: Tk (stdlib) or FLTK (optional `tlm[gui-fltk]`). See TLM_GUI."""

from __future__ import annotations

__all__ = ["run_gui"]


def run_gui() -> None:
    from tlm.gui.dispatch import dispatch_gui

    dispatch_gui()
