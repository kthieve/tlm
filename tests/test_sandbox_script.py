import os
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
        [sys.executable, str(root / "sandbox.py"), "env", "--posix"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert "XDG_CONFIG_HOME" in r.stdout


def test_sandbox_env_default_paths_include_sandboxes() -> None:
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, str(root / "sandbox.py"), "env", "--posix"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert "sandboxes" in r.stdout
    assert "default" in r.stdout


def test_sandbox_env_tlmsandbox_root(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["TLM_SANDBOXES_ROOT"] = str(tmp_path)
    r = subprocess.run(
        [sys.executable, str(root / "sandbox.py"), "env", "--posix"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert r.returncode == 0
    expected = str(tmp_path / "default")
    assert expected.replace("\\", "/") in r.stdout.replace("\\", "/")
