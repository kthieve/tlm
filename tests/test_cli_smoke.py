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
