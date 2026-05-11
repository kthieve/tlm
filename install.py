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

def get_default_standard_paths():
    home = Path.home()
    if platform.system() == "Windows":
        bin_dir = home / "AppData" / "Local" / "bin"
        venv_dir = home / "AppData" / "Local" / "tlm-venv"
    else:
        bin_dir = home / ".local" / "bin"
        venv_dir = home / ".local" / "share" / "tlm-venv"
    return bin_dir, venv_dir

def main():
    if sys.version_info < (3, 11):
        print("error: Python 3.11 or higher is required.", file=sys.stderr)
        sys.exit(1)

    root = Path(__file__).resolve().parent
    if not (root / "pyproject.toml").is_file():
        print(f"error: expected pyproject.toml in {root}", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Install tlm.")
    parser.add_argument("--mode", type=int, choices=[1, 2, 3], help="1: Portable, 2: Standalone Folder, 3: Standard Split")
    parser.add_argument("--dest", type=str, help="Destination folder (for mode 1 and 2)")
    parser.add_argument("--venv-dir", type=str, help="Venv directory (for mode 3)")
    parser.add_argument("--bin-dir", type=str, help="Bin directory (for mode 3)")
    parser.add_argument("--gui", action="store_true", help="Launch the graphical installer")
    args = parser.parse_args()

    if args.gui or (not args.mode and sys.stdin.isatty() and _can_run_gui()):
        if args.gui or input("\nLaunch graphical installer? [Y/n]: ").strip().lower() in ("", "y", "yes"):
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
    if not mode:
        print("tlm Installation Options\n========================")
        mode = prompt_choice("Choose installation mode:", [
            "Portable (Everything, including settings/data, in one local folder)",
            "Standalone Folder (Program in one local folder, settings in OS default locations)",
            "Standard Split (Venv in a share dir, executable linked in your global bin dir)"
        ])

    is_windows = platform.system() == "Windows"
    is_portable = (mode == 1)

    if mode in (1, 2):
        dest_str = args.dest
        if not dest_str:
            default_dest = Path.cwd() / "tlm-install"
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

    print(f"\nConfiguration:")
    print(f"  Mode: {mode}")
    print(f"  Venv Directory: {venv_dir}")
    print(f"  Bin Directory:  {bin_dir}")
    if is_portable:
        print(f"  Data/Settings:  {dest / 'data'}")
    
    bin_dir.mkdir(parents=True, exist_ok=True)
    venv_dir.parent.mkdir(parents=True, exist_ok=True)

    if is_windows:
        py_exe = venv_dir / "Scripts" / "python.exe"
        pip_exe = venv_dir / "Scripts" / "pip.exe"
        tlm_exe = venv_dir / "Scripts" / "tlm.exe"
    else:
        py_exe = venv_dir / "bin" / "python"
        pip_exe = venv_dir / "bin" / "pip"
        tlm_exe = venv_dir / "bin" / "tlm"

    if not py_exe.is_file():
        print(f"\nCreating venv at {venv_dir}...")
        venv.create(venv_dir, with_pip=True)

    print("\nUpgrading pip...")
    subprocess.run([str(py_exe), "-m", "pip", "install", "-U", "pip"], check=True)

    print(f"\nInstalling tlm from {root}...")
    subprocess.run([str(py_exe), "-m", "pip", "install", "-U", "--editable", str(root)], check=True)

    print(f"\nCreating launcher at {bin_dir}...")
    
    if is_portable:
        data_dir = dest / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        if is_windows:
            bat_link = bin_dir / "tlm.bat"
            with open(bat_link, "w") as f:
                f.write('@echo off\n')
                f.write(f'set XDG_CONFIG_HOME={data_dir}\\config\n')
                f.write(f'set XDG_DATA_HOME={data_dir}\\data\n')
                f.write(f'set XDG_STATE_HOME={data_dir}\\state\n')
                f.write(f'"{tlm_exe}" %*\n')
        else:
            sh_link = bin_dir / "tlm"
            with open(sh_link, "w") as f:
                f.write('#!/usr/bin/env bash\n')
                f.write(f'export XDG_CONFIG_HOME="{data_dir}/config"\n')
                f.write(f'export XDG_DATA_HOME="{data_dir}/data"\n')
                f.write(f'export XDG_STATE_HOME="{data_dir}/state"\n')
                f.write(f'exec "{tlm_exe}" "$@"\n')
            sh_link.chmod(0o755)
    else:
        if is_windows:
            bat_link = bin_dir / "tlm.bat"
            with open(bat_link, "w") as f:
                f.write(f'@echo off\n"{tlm_exe}" %*\n')
        else:
            # Mode 2 (Standalone) creates a shell wrapper without overriding XDG if we just want a relative link?
            # Actually, standard split and standalone folder just differ in where the files are placed.
            # But the executable needs to be in bin_dir.
            # If mode 2, bin_dir == dest.
            # A symlink might be fine on unix, but wrapper is safer.
            link_exe = bin_dir / "tlm"
            if link_exe.exists() or link_exe.is_symlink():
                link_exe.unlink()
            os.symlink(tlm_exe, link_exe)

    print("\nInstallation successful.")
    
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    bin_dir_str = str(bin_dir.resolve())
    found = False
    for d in path_dirs:
        if d and Path(d).resolve() == bin_dir.resolve():
            found = True
            break
            
    if not found:
        print(f"\nIMPORTANT: Add to your PATH: {bin_dir_str}")
        if not is_windows:
            print(f"  export PATH=\"{bin_dir_str}:$PATH\"")

if __name__ == "__main__":
    main()
