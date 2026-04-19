"""Unit tests for GUI backend selection (no display required)."""

from __future__ import annotations

import os

import pytest


def test_gui_backend_preference_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from tlm.gui import dispatch

    monkeypatch.delenv("TLM_GUI", raising=False)
    monkeypatch.delenv("TLM_GUI_BACKEND", raising=False)
    assert dispatch.gui_backend_preference() == "auto"

    monkeypatch.setenv("TLM_GUI", "fltk")
    assert dispatch.gui_backend_preference() == "fltk"

    monkeypatch.setenv("TLM_GUI_BACKEND", "tk")
    monkeypatch.delenv("TLM_GUI", raising=False)
    assert dispatch.gui_backend_preference() == "tk"

    monkeypatch.setenv("TLM_GUI", "bogus")
    assert dispatch.gui_backend_preference() == "auto"


def test_dispatch_gui_raises_when_forced_backend_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from tlm.gui import dispatch

    monkeypatch.setenv("TLM_GUI", "fltk")
    monkeypatch.setattr(dispatch, "fltk_available", lambda: False)
    monkeypatch.setattr(dispatch, "tkinter_available", lambda: True)

    with pytest.raises(dispatch.GuiBackendError, match="pyfltk"):
        dispatch.dispatch_gui()
