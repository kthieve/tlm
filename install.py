#!/usr/bin/env python3
"""
Multi-platform install script for tlm.
Requires only Python 3.11+.
Provides interactive choices for:
1. Portable Installation (Everything, including settings, in one folder)
2. Standalone Folder (Program in one folder, settings in OS default)
3. Standard Split (Venv in one location, bin in global PATH)
"""

import os
import sys
import subprocess
import venv
import platform
import argparse
from pathlib import Path


def _can_run_gui():
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        root.destroy()
        return True
    except Exception:
        return False


def prompt_choice(prompt_text, options):
    print(prompt_text)
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        try:
            choice = input("Select an option [1-3]: ").strip()
            if not choice:
                continue
            idx = int(choice)
            if 1 <= idx <= len(options):
                return idx
            print("Invalid choice.")
        except ValueError:
            print("Please enter a number.")
        except EOFError:
            print("\nAborted.")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(1)


def get_default_install_dest():
    """Default destination for mode 1/2 on Windows."""
    if platform.system() == "Windows":
        return Path("C:/tlm")
    return Path.cwd() / "tlm-install"


def get_default_standard_paths():
    home = Path.home()
    if platform.system() == "Windows":
        bin_dir = Path("C:/tlm")
        venv_dir = Path("C:/tlm/venv")
    else:
        bin_dir = home / ".local" / "bin"
        venv_dir = home / ".local" / "share" / "tlm-venv"
    return bin_dir, venv_dir


def _add_to_user_path_windows(dir_path: Path) -> bool:
    """Add *dir_path* to the current user's persistent PATH on Windows.

    Uses the registry via PowerShell so the change survives reboots.
    Returns True if the path was actually added (False if already present).
    """
    dir_str = str(dir_path.resolve())
    # Check current user PATH from the registry (not the session env)
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "[Environment]::GetEnvironmentVariable('Path', 'User')",
            ],
            capture_output=True, text=True, check=True,
        )
        current = result.stdout.strip()
    except Exception:
        current = ""

    # Already present?
    dirs = [d.strip().rstrip("\\\\/") for d in current.split(";") if d.strip()]
    normalised = dir_str.rstrip("\\\\/")
    if any(d.lower() == normalised.lower() for d in dirs):
        return False

    new_path = current.rstrip(";") + ";" + dir_str if current else dir_str
    try:
        subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                f"[Environment]::SetEnvironmentVariable('Path', '{new_path}', 'User')",
            ],
            check=True,
        )
        # Also inject into the running session so the user doesn't need to
        # open a new terminal for the rest of the installer to work.
        os.environ["PATH"] = dir_str + os.pathsep + os.environ.get("PATH", "")
        return True
    except Exception as exc:
        print(f"  warning: could not update PATH automatically: {exc}")
        return False


import shutil

def find_existing_install():
    exe = shutil.which("tlm")
    if exe:
        return Path(exe).parent.resolve()
    
    bin_dir, _ = get_default_standard_paths()
    if (bin_dir / ("tlm.bat" if platform.system() == "Windows" else "tlm")).exists():
        return bin_dir.resolve()
        
    default_dest = get_default_install_dest()
    if (default_dest / ("tlm.bat" if platform.system() == "Windows" else "tlm")).exists():
        return default_dest.resolve()
        
    return None


def main():
    if sys.version_info < (3, 11):
        print("error: Python 3.11 or higher is required.", file=sys.stderr)
        sys.exit(1)

    root = Path(__file__).resolve().parent
    if not (root / "pyproject.toml").is_file():
        print(f"error: expected pyproject.toml in {root}", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Install tlm.")
    parser.add_argument(
        "--mode",
        type=int,
        choices=[1, 2, 3],
        help="1: Portable, 2: Standalone Folder, 3: Standard Split",
    )
    parser.add_argument("--dest", type=str, help="Destination folder (for mode 1 and 2)")
    parser.add_argument("--venv-dir", type=str, help="Venv directory (for mode 3)")
    parser.add_argument("--bin-dir", type=str, help="Bin directory (for mode 3)")
    parser.add_argument("--gui", action="store_true", help="Launch the graphical installer")
    args = parser.parse_args()

    if args.gui or (not args.mode and sys.stdin.isatty() and _can_run_gui()):
        if args.gui or input("\nLaunch graphical installer? [Y/n]: ").strip().lower() in (
            "",
            "y",
            "yes",
        ):
            print("Launching GUI installer...")
            try:
                subprocess.run([sys.executable, str(root / "install_gui.py")], check=True)
                return
            except Exception as e:
                print(f"error launching GUI: {e}", file=sys.stderr)
                if args.gui:
                    sys.exit(1)
                print("Falling back to terminal installer.\n")

    mode = args.mode
    is_windows = platform.system() == "Windows"
    
    existing_bin = find_existing_install()
    if existing_bin and not mode and not args.gui and sys.stdin.isatty():
        print(f"\nAn existing tlm installation was found at: {existing_bin}")
        choice = prompt_choice(
            "What would you like to do?",
            [
                "Update existing installation (keep paths, upgrade pip and tlm)",
                "Reinstall (choose new options or overwrite)",
                "Cancel"
            ]
        )
        if choice == 3:
            sys.exit(0)
        elif choice == 1:
            # Try to infer mode and paths
            if (existing_bin / "venv").exists():
                mode = 1 # or 2, doesn't matter for update
                args.dest = str(existing_bin)
            else:
                mode = 3
                def_bin, def_venv = get_default_standard_paths()
                args.bin_dir = str(existing_bin)
                args.venv_dir = str(def_venv) # Assuming default venv location

    if not mode:
        print("\ntlm Installation Options\n========================")
        mode = prompt_choice(
            "Choose installation mode:",
            [
                "Portable (Everything, including settings/data, in one local folder)",
                "Standalone Folder (Program in one local folder, settings in OS default locations)",
                "Standard Split (Venv in a share dir, executable linked in your global bin dir)",
            ],
        )

    is_portable = mode == 1

    if mode in (1, 2):
        dest_str = args.dest
        if not dest_str:
            default_dest = get_default_install_dest()
            try:
                dest_str = input(f"\nEnter destination folder [{default_dest}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                sys.exit(1)
            if not dest_str:
                dest_str = str(default_dest)
        dest = Path(dest_str).resolve()
        venv_dir = dest / "venv"
        bin_dir = dest
    else:
        def_bin, def_venv = get_default_standard_paths()

        bin_str = args.bin_dir
        if not bin_str:
            try:
                bin_str = input(f"\nEnter bin directory for the launcher [{def_bin}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                sys.exit(1)
            if not bin_str:
                bin_str = str(def_bin)
        bin_dir = Path(bin_str).resolve()

        venv_str = args.venv_dir
        if not venv_str:
            try:
                venv_str = input(f"Enter venv directory [{def_venv}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                sys.exit(1)
            if not venv_str:
                venv_str = str(def_venv)
        venv_dir = Path(venv_str).resolve()

    print("\nConfiguration:")
    print(f"  Mode: {mode}")
    print(f"  Venv Directory: {venv_dir}")
    print(f"  Bin Directory:  {bin_dir}")
    if is_portable:
        print(f"  Data/Settings:  {dest / 'data'}")

    bin_dir.mkdir(parents=True, exist_ok=True)
    venv_dir.parent.mkdir(parents=True, exist_ok=True)

    if is_windows:
        py_exe = venv_dir / "Scripts" / "python.exe"
        tlm_exe = venv_dir / "Scripts" / "tlm.exe"
    else:
        py_exe = venv_dir / "bin" / "python"
        tlm_exe = venv_dir / "bin" / "tlm"

    if not py_exe.is_file():
        print(f"\nCreating venv at {venv_dir}...")
        venv.create(venv_dir, with_pip=True)

    print("\nUpgrading pip...")
    subprocess.run([str(py_exe), "-m", "pip", "install", "-U", "pip"], check=True)

    print(f"\nInstalling tlm from {root}...")
    subprocess.run([str(py_exe), "-m", "pip", "install", "-U", "--editable", str(root)], check=True)

    print(f"\nCreating launcher at {bin_dir}...")

    # On Windows every launcher activates the venv so that sub-processes
    # (e.g. pip, python scripts called by tlm) run inside the venv.
    activate_bat = venv_dir / "Scripts" / "activate.bat"

    if is_portable:
        data_dir = dest / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        if is_windows:
            bat_link = bin_dir / "tlm.bat"
            with open(bat_link, "w") as f:
                f.write("@echo off\n")
                f.write(f'call "{activate_bat}"\n')
                f.write(f"set XDG_CONFIG_HOME={data_dir}\\config\n")
                f.write(f"set XDG_DATA_HOME={data_dir}\\data\n")
                f.write(f"set XDG_STATE_HOME={data_dir}\\state\n")
                f.write(f'"{tlm_exe}" %*\n')
        else:
            sh_link = bin_dir / "tlm"
            with open(sh_link, "w") as f:
                f.write("#!/usr/bin/env bash\n")
                f.write(f'export XDG_CONFIG_HOME="{data_dir}/config"\n')
                f.write(f'export XDG_DATA_HOME="{data_dir}/data"\n')
                f.write(f'export XDG_STATE_HOME="{data_dir}/state"\n')
                f.write(f'exec "{tlm_exe}" "$@"\n')
            sh_link.chmod(0o755)
    else:
        if is_windows:
            bat_link = bin_dir / "tlm.bat"
            with open(bat_link, "w") as f:
                f.write("@echo off\n")
                f.write(f'call "{activate_bat}"\n')
                f.write(f'"{tlm_exe}" %*\n')
        else:
            link_exe = bin_dir / "tlm"
            if link_exe.exists() or link_exe.is_symlink():
                link_exe.unlink()
            os.symlink(tlm_exe, link_exe)

    print("\nInstallation successful.")

    # ---- Auto-add to PATH on Windows ----
    if is_windows:
        bin_dir_str = str(bin_dir.resolve())
        added = _add_to_user_path_windows(bin_dir)
        if added:
            print(f"\n  ✔ Added {bin_dir_str} to your user PATH.")
            print("    Open a new terminal for PATH changes to take effect.")
        else:
            # Check if already there
            path_dirs = os.environ.get("PATH", "").split(os.pathsep)
            already = any(
                d and Path(d).resolve() == bin_dir.resolve() for d in path_dirs
            )
            if already:
                print(f"\n  ✔ {bin_dir_str} is already on your PATH.")
            else:
                print(f"\nIMPORTANT: Add to your PATH: {bin_dir_str}")
    else:
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        bin_dir_str = str(bin_dir.resolve())
        found = any(d and Path(d).resolve() == bin_dir.resolve() for d in path_dirs)
        if not found:
            print(f"\nIMPORTANT: Add to your PATH: {bin_dir_str}")
            print(f'  export PATH="{bin_dir_str}:$PATH"')


if __name__ == "__main__":
    main()
