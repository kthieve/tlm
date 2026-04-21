import subprocess
import sys

from tlm.cli import KNOWN_SUBCOMMANDS, main


def test_help_exits_zero() -> None:
    r = subprocess.run([sys.executable, "-m", "tlm", "--help"], capture_output=True, text=True, check=False)
    assert r.returncode == 0
    assert "Terminal LLM" in r.stdout or "tlm" in r.stdout


def test_no_args_prints_help() -> None:
    assert main([]) == 0


def test_natural_language_not_subcommand() -> None:
    assert "show" not in KNOWN_SUBCOMMANDS


def test_context_commands_registered() -> None:
    assert "new" in KNOWN_SUBCOMMANDS
    assert "clear" in KNOWN_SUBCOMMANDS


def test_web_subcommand_registered() -> None:
    assert "web" in KNOWN_SUBCOMMANDS


def test_web_invokes_cmd_ask_with_web_focus(monkeypatch) -> None:
    called: dict = {}

    def fake_cmd_ask(text: str, **kwargs) -> int:
        called["text"] = text
        called["web_focus"] = kwargs.get("web_focus")
        return 0

    monkeypatch.setattr("tlm.cli.cmd_ask", fake_cmd_ask)
    assert main(["web", "price", "check"]) == 0
    assert called["text"] == "price check"
    assert called["web_focus"] is True
