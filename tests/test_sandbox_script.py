import subprocess
import sys
from pathlib import Path


def test_sandbox_help() -> None:
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run([sys.executable, str(root / "sandbox.py")], capture_output=True, text=True, check=False)
    assert r.returncode == 0
    assert "sandbox.py env" in r.stdout


def test_sandbox_env_smoke() -> None:
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, str(root / "sandbox.py"), "env"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert "XDG_CONFIG_HOME" in r.stdout
