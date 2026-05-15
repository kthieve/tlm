from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

def _add_to_user_path_windows(dir_path: Path) -> tuple[bool, str]:
    """Add *dir_path* to the current user's persistent PATH on Windows using PowerShell."""
    dir_str = str(dir_path.resolve())
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "[Environment]::GetEnvironmentVariable('Path', 'User')",
            ],
            capture_output=True, text=True, check=True,
        )
        current = result.stdout.strip()
    except Exception as e:
        return False, f"Could not read Windows PATH: {e}"

    # Already present?
    dirs = [d.strip().rstrip("\\") for d in current.split(";") if d.strip()]
    normalized = dir_str.rstrip("\\")
    if any(d.lower() == normalized.lower() for d in dirs):
        return True, f"{dir_str} is already on your PATH."

    new_path = (current.rstrip(";") + ";" + dir_str) if current else dir_str
    try:
        subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                f"[Environment]::SetEnvironmentVariable('Path', '{new_path}', 'User')",
            ],
            check=True,
        )
        return True, f"Successfully added {dir_str} to your user PATH."
    except Exception as e:
        return False, f"Could not update Windows PATH: {e}"

def _add_to_user_path_linux(dir_path: Path) -> tuple[bool, str]:
    """Append the directory to ~/.bashrc or ~/.zshrc."""
    dir_str = str(dir_path.resolve())
    shell = (os.environ.get("SHELL") or "").lower()
    if "zsh" in shell:
        rc = Path.home() / ".zshrc"
    else:
        rc = Path.home() / ".bashrc"
    
    line = f'export PATH="{dir_str}:$PATH"'
    marker = f"# tlm: main bin on PATH (managed by tlm)"
    
    try:
        existing = rc.read_text(encoding="utf-8", errors="replace") if rc.is_file() else ""
    except OSError as e:
        return False, f"Could not read {rc}: {e}"
        
    if marker in existing:
        return True, f"tlm PATH block already present in {rc}."
        
    block = f"\n{marker}\n{line}\n"
    try:
        rc.parent.mkdir(parents=True, exist_ok=True)
        with open(rc, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write(block)
        return True, f"Appended to {rc}. Open a new terminal for changes to take effect."
    except OSError as e:
        return False, f"Could not write {rc}: {e}"

def add_dir_to_path(dir_path: Path) -> tuple[bool, str]:
    """Cross-platform 'Add to PATH' logic."""
    if platform.system() == "Windows":
        return _add_to_user_path_windows(dir_path)
    return _add_to_user_path_linux(dir_path)
