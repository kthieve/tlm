"""Paths and settings (API keys via env / future GUI)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def xdg_data_home() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base).expanduser()
    if os.name == "nt":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata)
    return Path.home() / ".local" / "share"


def data_dir() -> Path:
    d = xdg_data_home() / "tlm"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sessions_dir() -> Path:
    d = data_dir() / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def abilities_dir() -> Path:
    d = data_dir() / "abilities"
    d.mkdir(parents=True, exist_ok=True)
    return d


def browsers_dir() -> Path:
    """Directory for portable browser installations (e.g. Playwright Chromium)."""
    d = data_dir() / "browsers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def xdg_state_home() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    if base:
        return Path(base).expanduser()
    if os.name == "nt":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata)
    return Path.home() / ".local" / "state"


def state_dir() -> Path:
    d = xdg_state_home() / "tlm"
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_provider() -> str:
    return os.environ.get("TLM_PROVIDER", "openrouter").strip().lower()


def api_key_for(provider: str) -> str | None:
    """Read `TLM_<PROVIDER>_API_KEY` or generic `TLM_API_KEY`."""
    p = provider.upper().replace("-", "_")
    return os.environ.get(f"TLM_{p}_API_KEY") or os.environ.get("TLM_API_KEY")


def base_url_env(provider: str) -> str | None:
    p = provider.upper().replace("-", "_")
    return os.environ.get(f"TLM_{p}_BASE_URL")


def default_model_env() -> str | None:
    v = os.environ.get("TLM_MODEL")
    return v.strip() if v else None


def prompts_dir() -> Path:
    from tlm.settings import config_dir

    d = config_dir() / "prompts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_tlm_bin_dir() -> Path | None:
    """Best-effort find the directory containing the 'tlm' executable."""
    import sys
    import platform
    import shutil

    bin_name = "tlm.exe" if platform.system() == "Windows" else "tlm"

    # 1. Check PATH
    found = shutil.which("tlm")
    if found:
        return Path(found).parent.resolve()

    # 2. Check current executable's folder (e.g. .venv/bin or .venv/Scripts)
    exe_path = Path(sys.executable).parent
    if (exe_path / bin_name).exists():
        return exe_path.resolve()
    if platform.system() == "Windows" and (exe_path / "tlm.bat").exists():
        return exe_path.resolve()

    # 3. Check sys.prefix (Scripts on Windows, bin on Linux)
    prefix_path = Path(sys.prefix)
    if platform.system() == "Windows":
        scripts = prefix_path / "Scripts"
        if (scripts / bin_name).exists():
            return scripts.resolve()
        if (scripts / "tlm.bat").exists():
            return scripts.resolve()
    else:
        bin_dir = prefix_path / "bin"
        if (bin_dir / bin_name).exists():
            return bin_dir.resolve()

    # 4. Check default install locations
    if platform.system() == "Windows":
        # Prefer user local app data over C:/tlm
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            user_tlm = Path(local_appdata) / "tlm"
            if (user_tlm / "tlm.bat").exists() or (user_tlm / "tlm.exe").exists():
                return user_tlm.resolve()
        
        if (Path("C:/tlm") / "tlm.bat").exists():
            return Path("C:/tlm").resolve()
        if (Path("C:/tlm") / "tlm.exe").exists():
            return Path("C:/tlm").resolve()
    else:
        if (Path.home() / ".local/bin/tlm").exists():
            return (Path.home() / ".local/bin").resolve()

    return None
