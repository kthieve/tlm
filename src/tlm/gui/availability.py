"""Detect whether optional GUI backends can be imported."""

from __future__ import annotations


def tkinter_available() -> bool:
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return False
    return True


def fltk_available() -> bool:
    try:
        from fltk import Fl_Window  # noqa: F401
    except ImportError:
        return False
    return True
