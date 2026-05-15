"""Cross-platform elevation (UAC/root) support for Windows, Linux, and macOS."""

from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import sys
from typing import NoReturn

def is_elevated() -> bool:
    """Check if the current process has administrative/root privileges."""
    if platform.system() == "Windows":
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    else:
        try:
            # os.getuid() is generally more appropriate than geteuid() for basic root check
            # but tlm root_guard used geteuid, so we stay compatible.
            return os.geteuid() == 0
        except (AttributeError, OSError):
            return False

def elevate_me() -> NoReturn:
    """
    Restart the current process with elevated privileges.
    On Windows, this triggers a UAC prompt.
    On Linux/macOS, this tries pkexec/osascript (GUI) or sudo (TUI).
    """
    if is_elevated():
        return  # Already elevated, nothing to do. (Actually shouldn't return NoReturn)

    # Use absolute path to the current python interpreter and script
    # This is safer than relying on sys.argv[0] alone.
    executable = sys.executable
    script = os.path.abspath(sys.argv[0])
    
    # Quote arguments correctly
    def _quote(arg: str) -> str:
        if " " in arg or '"' in arg or "'" in arg:
            return f'"{arg}"'
        return arg

    quoted_args = [_quote(arg) for arg in sys.argv[1:]]
    
    if platform.system() == "Windows":
        # ShellExecute with 'runas' verb triggers UAC
        params = f'"{script}" ' + " ".join(quoted_args)
        
        # SW_SHOWNORMAL = 1
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, params, None, 1
        )
        if ret <= 32:
            raise RuntimeError(f"UAC elevation failed or was cancelled (code {ret})")
        sys.exit(0)
    
    elif platform.system() == "Darwin":
        # macOS: use osascript for graphical prompt
        full_cmd = f'{executable} "{script}" ' + " ".join(quoted_args)
        applescript = f'do shell script "{full_cmd}" with administrator privileges'
        try:
            subprocess.run(["osascript", "-e", applescript], check=True)
            sys.exit(0)
        except subprocess.CalledProcessError:
            raise RuntimeError("macOS elevation failed or was cancelled")
            
    else:
        # Linux / Unix
        has_display = "DISPLAY" in os.environ or "WAYLAND_DISPLAY" in os.environ
        
        if has_display:
            # Try pkexec for graphical prompt if in a GUI session
            try:
                cmd = ["pkexec", executable, script] + sys.argv[1:]
                subprocess.run(cmd, check=True)
                sys.exit(0)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback to sudo if pkexec fails or is missing
                pass
        
        # Fallback to sudo (requires TTY)
        try:
            cmd = ["sudo", executable, script] + sys.argv[1:]
            subprocess.run(cmd, check=True)
            sys.exit(0)
        except subprocess.CalledProcessError:
            raise RuntimeError("Elevation failed or was cancelled")

    # If we get here, something went wrong with the elevation calls
    sys.exit(1)
