"""Tests for first-run setup wizard."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from tlm.settings import UserSettings, config_file_path, load_settings
from tlm.providers.registry import list_provider_ids
from tlm.setup_wizard import (
    SETUP_VERSION,
    is_setup_complete,
    maybe_first_run_wizard,
    run_setup_wizard,
    setup_marker_path,
    write_setup_marker,
)


@pytest.fixture
def isolated_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return tmp_path


def _tty_stdin(script: str) -> io.StringIO:
    buf = io.StringIO(script)
    buf.isatty = lambda: True  # type: ignore[method-assign]
    return buf


def test_run_setup_wizard_non_tty_returns_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    out, code = run_setup_wizard(UserSettings(provider="openrouter"))
    assert out is None
    assert code == 2


def test_run_setup_wizard_saves_and_marker(
    monkeypatch: pytest.MonkeyPatch, isolated_xdg: Path
) -> None:
    monkeypatch.setenv("TLM_OPENROUTER_API_KEY", "test-key-for-wizard")
    # Active provider, key, model, safety, memory, web, save.
    script = "\n\n\n\n\n\n\n"
    monkeypatch.setattr(sys, "stdin", _tty_stdin(script))
    s0 = UserSettings(provider="openrouter", safety_profile="standard")
    out, code = run_setup_wizard(s0)
    assert code == 0
    assert out is not None
    assert is_setup_complete()
    mp = setup_marker_path()
    assert mp.is_file()
    data = json.loads(mp.read_text(encoding="utf-8"))
    assert data.get("version") == SETUP_VERSION
    assert config_file_path().is_file()


def test_run_setup_wizard_eof(monkeypatch: pytest.MonkeyPatch, isolated_xdg: Path) -> None:
    monkeypatch.setenv("TLM_OPENROUTER_API_KEY", "x")
    monkeypatch.setattr(sys, "stdin", _tty_stdin(""))
    out, code = run_setup_wizard(UserSettings(provider="openrouter"))
    assert out is None
    assert code == 1
    assert not is_setup_complete()


def test_run_setup_wizard_invalid_provider(monkeypatch: pytest.MonkeyPatch, isolated_xdg: Path) -> None:
    monkeypatch.setenv("TLM_OPENROUTER_API_KEY", "x")
    monkeypatch.setattr(sys, "stdin", _tty_stdin("not-a-real-provider\n"))
    out, code = run_setup_wizard(UserSettings(provider="openrouter"))
    assert out is None
    assert code == 2


def test_maybe_first_run_skips_when_complete(monkeypatch: pytest.MonkeyPatch, isolated_xdg: Path) -> None:
    write_setup_marker()
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    s = maybe_first_run_wizard()
    assert isinstance(s, UserSettings)


def test_maybe_first_run_skips_non_tty(monkeypatch: pytest.MonkeyPatch, isolated_xdg: Path) -> None:
    assert not is_setup_complete()
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.delenv("CI", raising=False)
    maybe_first_run_wizard()
    assert not is_setup_complete()


def test_maybe_first_run_skips_ci(monkeypatch: pytest.MonkeyPatch, isolated_xdg: Path) -> None:
    monkeypatch.setenv("CI", "1")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    maybe_first_run_wizard()
    assert not is_setup_complete()


def test_maybe_first_run_runs_wizard_when_needed(monkeypatch: pytest.MonkeyPatch, isolated_xdg: Path) -> None:
    monkeypatch.setenv("TLM_OPENROUTER_API_KEY", "x")
    monkeypatch.delenv("CI", raising=False)
    script = "\n\n\n\n\n\n\n"
    monkeypatch.setattr(sys, "stdin", _tty_stdin(script))
    assert not is_setup_complete()
    s = maybe_first_run_wizard()
    assert isinstance(s, UserSettings)
    assert is_setup_complete()


def test_decline_save_no_marker(monkeypatch: pytest.MonkeyPatch, isolated_xdg: Path) -> None:
    monkeypatch.setenv("TLM_OPENROUTER_API_KEY", "x")
    # defaults then "n" for save (through web prompt)
    script = "\n\n\n\n\n\nn\n"
    monkeypatch.setattr(sys, "stdin", _tty_stdin(script))
    out, code = run_setup_wizard(UserSettings(provider="openrouter"))
    assert code == 0
    assert out is not None
    assert not is_setup_complete()


def test_run_setup_wizard_can_set_multiple_provider_keys(
    monkeypatch: pytest.MonkeyPatch, isolated_xdg: Path
) -> None:
    ids = list_provider_ids()
    openrouter_idx = ids.index("openrouter") + 1
    deepseek_idx = ids.index("deepseek") + 1
    openai_idx = ids.index("openai") + 1

    # Active provider=openrouter, then set keys for deepseek/openai, then finish key loop.
    script = (
        f"{openrouter_idx}\n"
        f"{deepseek_idx}\n"
        "deep-key\n"
        f"{openai_idx}\n"
        "open-key\n"
        "\n"
        "\n"
        "\n"
        "\n"
        "\n"
        "\n"
    )
    monkeypatch.setattr(sys, "stdin", _tty_stdin(script))
    out, code = run_setup_wizard(UserSettings(provider="openrouter"))
    assert code == 0
    assert out is not None
    saved = load_settings()
    assert saved.provider == "openrouter"
    assert saved.api_keys.get("deepseek") == "deep-key"
    assert saved.api_keys.get("openai") == "open-key"
