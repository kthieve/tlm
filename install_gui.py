#!/usr/bin/env python3
"""Standalone GUI installer for tlm (pre-install). No tlm package imports allowed."""

import os
import subprocess
import venv
import platform
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont

# Re-use helpers from install.py if importable, else inline.
try:
    from install import _add_to_user_path_windows, find_existing_install, get_default_standard_paths
except Exception:
    def find_existing_install(): return None
    def get_default_standard_paths():
        home = Path.home()
        if platform.system() == "Windows":
            return Path("C:/tlm"), Path("C:/tlm/venv")
        return home / ".local" / "bin", home / ".local" / "share" / "tlm-venv"

    def _add_to_user_path_windows(dir_path: Path) -> bool:
        """Add *dir_path* to the current user's persistent PATH on Windows."""
        dir_str = str(dir_path.resolve())
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "[Environment]::GetEnvironmentVariable('Path', 'User')"],
                capture_output=True, text=True, check=True,
            )
            current = result.stdout.strip()
        except Exception:
            current = ""
        dirs = [d.strip().rstrip("\\\\/") for d in current.split(";") if d.strip()]
        normalised = dir_str.rstrip("\\\\/")
        if any(d.lower() == normalised.lower() for d in dirs):
            return False
        new_path = current.rstrip(";") + ";" + dir_str if current else dir_str
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"[Environment]::SetEnvironmentVariable('Path', '{new_path}', 'User')"],
                check=True,
            )
            os.environ["PATH"] = dir_str + os.pathsep + os.environ.get("PATH", "")
            return True
        except Exception:
            return False

# Design Tokens (matching tlm style)
_BG_PAGE = "#f0f4f8"
_BG_HEADER = "#0f172a"
_BG_CARD = "#ffffff"
_FG_TITLE = "#f1f5f9"
_FG_BODY = "#1e293b"
_FG_MUTED = "#64748b"
_ACCENT = "#2563eb"
_ACCENT_HOVER = "#1d4ed8"
_SUCCESS = "#16a34a"
_ERROR = "#dc2626"
_TIP_BG = "#fefce8"
_TIP_FG = "#854d0e"


class InstallerWizard:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("tlm — Installer")
        self.root.geometry("860x620")
        self.root.minsize(860, 620)
        self.root.configure(bg=_BG_PAGE)

        self.root_dir = Path(__file__).resolve().parent
        self.current_step = 0

        # Installation State
        self.install_mode = tk.IntVar(value=1)  # 1: Portable, 2: Standalone, 3: Standard
        self.dest_path = tk.StringVar(value=str(Path.cwd() / "tlm-install"))
        self.bin_path = tk.StringVar()
        self.venv_path = tk.StringVar()

        self._init_paths()
        self._setup_styles()
        self._build_layout()

        self.existing_bin = find_existing_install()
        self.is_update = tk.BooleanVar(value=bool(self.existing_bin))

        self.steps = []
        if self.existing_bin:
            self.steps.append(self._create_existing_install_page)
        self.steps.extend([
            self._create_welcome_page,
            self._create_mode_page,
            self._create_path_page,
            self._create_summary_page,
        ])

        self.show_step(0)

    def _init_paths(self):
        if platform.system() == "Windows":
            default_dest = "C:\\tlm"
            self.dest_path.set(default_dest)
            self.bin_path.set(default_dest)
            self.venv_path.set(default_dest + "\\venv")
        else:
            home = Path.home()
            self.bin_path.set(str(home / ".local" / "bin"))
            self.venv_path.set(str(home / ".local" / "share" / "tlm-venv"))

    def _setup_styles(self):
        self.style = ttk.Style(self.root)
        for name in ("clam", "alt", "default"):
            if name in self.style.theme_names():
                self.style.theme_use(name)
                break

        self.base_font = tkfont.nametofont("TkDefaultFont")
        self.title_font = self.base_font.copy()
        self.title_font.configure(size=14, weight="bold")
        self.header_font = self.base_font.copy()
        self.header_font.configure(size=16, weight="bold")
        self.tip_font = self.base_font.copy()
        self.tip_font.configure(size=9)

        self.style.configure("TFrame", background=_BG_PAGE)
        self.style.configure("TLabel", background=_BG_PAGE, foreground=_FG_BODY)
        self.style.configure(
            "Header.TLabel", background=_BG_HEADER, foreground=_FG_TITLE, font=self.header_font
        )
        self.style.configure(
            "Accent.TButton", foreground="#ffffff", background=_ACCENT, padding=(12, 6)
        )
        self.style.map("Accent.TButton", background=[("active", _ACCENT_HOVER)])

    def _build_layout(self):
        # Header
        self.header = tk.Frame(self.root, bg=_BG_HEADER, padx=20, pady=15)
        self.header.pack(fill=tk.X)
        tk.Label(self.header, text="tlm", font=self.header_font, fg=_FG_TITLE, bg=_BG_HEADER).pack(
            side=tk.LEFT
        )
        self.step_label = tk.Label(
            self.header, text="Installer", font=self.base_font, fg=_FG_MUTED, bg=_BG_HEADER
        )
        self.step_label.pack(side=tk.LEFT, padx=(15, 0))

        # Content
        self.content_frame = tk.Frame(self.root, bg=_BG_PAGE, padx=30, pady=20)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        # Footer
        self.footer = tk.Frame(self.root, bg=_BG_PAGE, padx=30, pady=20)
        self.footer.pack(fill=tk.X)
        self.back_btn = ttk.Button(self.footer, text="← Back", command=self.prev_step)
        self.back_btn.pack(side=tk.LEFT)
        self.next_btn = ttk.Button(
            self.footer, text="Next →", style="Accent.TButton", command=self.next_step
        )
        self.next_btn.pack(side=tk.RIGHT)

    def show_step(self, index):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        self.current_step = index
        self.steps[index]()
        self.back_btn.configure(state=tk.NORMAL if index > 0 else tk.DISABLED)
        self.step_label.configure(text=f"Step {index + 1} of {len(self.steps)}")

    def next_step(self):
        # If we are on existing install page and chose update, skip to summary
        if self.existing_bin and self.steps[self.current_step] == self._create_existing_install_page:
            if self.is_update.get():
                # Set up paths for update and skip to summary
                if (self.existing_bin / "venv").exists():
                    self.install_mode.set(1)
                    self.dest_path.set(str(self.existing_bin))
                else:
                    self.install_mode.set(3)
                    bin_dir, venv_dir = get_default_standard_paths()
                    self.bin_path.set(str(self.existing_bin))
                    self.venv_path.set(str(venv_dir))
                
                # Find summary step index
                summary_idx = self.steps.index(self._create_summary_page)
                self.show_step(summary_idx)
                return

        if self.current_step < len(self.steps) - 1:
            self.show_step(self.current_step + 1)

    def prev_step(self):
        if self.current_step > 0:
            # If we went back from summary after choosing update, go back to existing install page
            if self.existing_bin and self.is_update.get() and self.steps[self.current_step] == self._create_summary_page:
                self.show_step(self.steps.index(self._create_existing_install_page))
                return
            self.show_step(self.current_step - 1)

    def _create_tip_sidebar(self, parent, title, text):
        tip_frame = tk.Frame(
            parent, bg=_TIP_BG, padx=15, pady=15, highlightbackground=_TIP_FG, highlightthickness=1
        )
        tip_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(20, 0))
        tk.Label(tip_frame, text=f"💡 {title}", font=self.title_font, fg=_TIP_FG, bg=_TIP_BG).pack(
            anchor="w", pady=(0, 10)
        )
        tk.Label(
            tip_frame,
            text=text,
            font=self.tip_font,
            fg=_TIP_FG,
            bg=_TIP_BG,
            justify=tk.LEFT,
            wraplength=220,
        ).pack(anchor="w")

    def _create_existing_install_page(self):
        self._create_tip_sidebar(
            self.content_frame,
            "Existing Install",
            "tlm is already installed. You can easily update it or do a fresh installation."
        )
        tk.Label(
            self.content_frame, text="⚙️ Existing Installation Found", font=self.header_font, bg=_BG_PAGE
        ).pack(anchor="w", pady=(0, 20))
        tk.Label(
            self.content_frame,
            text=f"We found tlm installed at:\n{self.existing_bin}",
            bg=_BG_PAGE,
            justify=tk.LEFT,
            font=self.title_font,
        ).pack(anchor="w", pady=(0, 20))
        
        f = tk.Frame(self.content_frame, bg=_BG_PAGE, pady=10)
        f.pack(fill=tk.X)
        ttk.Radiobutton(f, text="Update existing installation", variable=self.is_update, value=True).pack(anchor="w")
        tk.Label(f, text="Keeps your paths. Upgrades pip and tlm dependencies.", font=self.tip_font, fg=_FG_MUTED, bg=_BG_PAGE, padx=25).pack(anchor="w")

        f2 = tk.Frame(self.content_frame, bg=_BG_PAGE, pady=10)
        f2.pack(fill=tk.X)
        ttk.Radiobutton(f2, text="Reinstall completely", variable=self.is_update, value=False).pack(anchor="w")
        tk.Label(f2, text="Configure new installation paths or overwrite existing.", font=self.tip_font, fg=_FG_MUTED, bg=_BG_PAGE, padx=25).pack(anchor="w")

    def _create_welcome_page(self):
        self._create_tip_sidebar(
            self.content_frame,
            "Welcome",
            "tlm is a powerful assistant for your terminal. This wizard will guide you through a safe installation.",
        )
        tk.Label(
            self.content_frame, text="🎉 Welcome to tlm", font=self.header_font, bg=_BG_PAGE
        ).pack(anchor="w", pady=(0, 20))
        tk.Label(
            self.content_frame,
            text="A terminal-first LLM assistant for Linux, macOS & Windows.",
            bg=_BG_PAGE,
        ).pack(anchor="w")
        tk.Label(
            self.content_frame,
            text="\nThis wizard will:\n• Install tlm in a virtual env\n• Create a launcher on your PATH\n• Configure your LLM provider",
            bg=_BG_PAGE,
            justify=tk.LEFT,
        ).pack(anchor="w")

    def _create_mode_page(self):
        self._create_tip_sidebar(
            self.content_frame,
            "Installation Modes",
            "Portable: Everything stays in one folder.\nStandalone: Program in one folder, settings in system dirs.\nStandard: Follows OS conventions.",
        )
        tk.Label(
            self.content_frame, text="📦 Installation Mode", font=self.title_font, bg=_BG_PAGE
        ).pack(anchor="w", pady=(0, 20))

        modes = [
            (1, "Portable", "Everything in one local folder (best for USB or testing)."),
            (
                2,
                "Standalone Folder",
                "Program in one folder; settings in OS defaults (~/.config/tlm).",
            ),
            (3, "Standard Split", "Follows OS conventions (venv in share, launcher in bin)."),
        ]

        for val, name, desc in modes:
            f = tk.Frame(self.content_frame, bg=_BG_PAGE, pady=10)
            f.pack(fill=tk.X)
            ttk.Radiobutton(f, text=name, variable=self.install_mode, value=val).pack(anchor="w")
            tk.Label(f, text=desc, font=self.tip_font, fg=_FG_MUTED, bg=_BG_PAGE, padx=25).pack(
                anchor="w"
            )

    def _create_path_page(self):
        self._create_tip_sidebar(
            self.content_frame,
            "Paths",
            "Choose where you want tlm to live. The installer will create these folders if they don't exist.",
        )
        tk.Label(self.content_frame, text="📂 Paths", font=self.title_font, bg=_BG_PAGE).pack(
            anchor="w", pady=(0, 20)
        )

        mode = self.install_mode.get()
        if mode in (1, 2):
            tk.Label(self.content_frame, text="Destination Folder", bg=_BG_PAGE).pack(anchor="w")
            f = tk.Frame(self.content_frame, bg=_BG_PAGE)
            f.pack(fill=tk.X, pady=5)
            ttk.Entry(f, textvariable=self.dest_path, width=50).pack(side=tk.LEFT)
            ttk.Button(f, text="Browse…", command=lambda: self._browse(self.dest_path)).pack(
                side=tk.LEFT, padx=5
            )
        else:
            tk.Label(self.content_frame, text="Launcher (Bin) Directory", bg=_BG_PAGE).pack(
                anchor="w"
            )
            f1 = tk.Frame(self.content_frame, bg=_BG_PAGE)
            f1.pack(fill=tk.X, pady=5)
            ttk.Entry(f1, textvariable=self.bin_path, width=50).pack(side=tk.LEFT)
            ttk.Button(f1, text="Browse…", command=lambda: self._browse(self.bin_path)).pack(
                side=tk.LEFT, padx=5
            )

            tk.Label(self.content_frame, text="Virtual Env Directory", bg=_BG_PAGE).pack(
                anchor="w", pady=(10, 0)
            )
            f2 = tk.Frame(self.content_frame, bg=_BG_PAGE)
            f2.pack(fill=tk.X, pady=5)
            ttk.Entry(f2, textvariable=self.venv_path, width=50).pack(side=tk.LEFT)
            ttk.Button(f2, text="Browse…", command=lambda: self._browse(self.venv_path)).pack(
                side=tk.LEFT, padx=5
            )

    def _browse(self, var):
        d = filedialog.askdirectory()
        if d:
            var.set(d)

    def _create_summary_page(self):
        tk.Label(
            self.content_frame, text="📋 Review & Install", font=self.title_font, bg=_BG_PAGE
        ).pack(anchor="w", pady=(0, 20))

        summary = tk.Frame(
            self.content_frame,
            bg=_BG_CARD,
            padx=15,
            pady=15,
            highlightbackground=_FG_MUTED,
            highlightthickness=1,
        )
        summary.pack(fill=tk.X)

        mode_name = ["", "Portable", "Standalone", "Standard"][self.install_mode.get()]
        tk.Label(summary, text=f"Mode: {mode_name}", bg=_BG_CARD).pack(anchor="w")

        if self.install_mode.get() in (1, 2):
            tk.Label(summary, text=f"Destination: {self.dest_path.get()}", bg=_BG_CARD).pack(
                anchor="w"
            )
        else:
            tk.Label(summary, text=f"Bin Dir: {self.bin_path.get()}", bg=_BG_CARD).pack(anchor="w")
            tk.Label(summary, text=f"Venv Dir: {self.venv_path.get()}", bg=_BG_CARD).pack(
                anchor="w"
            )

        self.progress = ttk.Progressbar(self.content_frame, mode="determinate", length=400)
        self.progress.pack(pady=20)
        self.status_lbl = tk.Label(self.content_frame, text="Ready to install", bg=_BG_PAGE)
        self.status_lbl.pack()

        self.next_btn.configure(text="⚡ Install", command=self._start_install)

    def _start_install(self):
        self.next_btn.configure(state=tk.DISABLED)
        self.back_btn.configure(state=tk.DISABLED)
        threading.Thread(target=self._install_thread, daemon=True).start()

    def _install_thread(self):
        try:
            mode = self.install_mode.get()
            if mode in (1, 2):
                dest = Path(self.dest_path.get()).resolve()
                venv_dir = dest / "venv"
                bin_dir = dest
            else:
                bin_dir = Path(self.bin_path.get()).resolve()
                venv_dir = Path(self.venv_path.get()).resolve()

            self._update_status("Creating venv...", 20)
            bin_dir.mkdir(parents=True, exist_ok=True)
            venv_dir.parent.mkdir(parents=True, exist_ok=True)
            venv.create(venv_dir, with_pip=True)

            is_win = platform.system() == "Windows"
            py_exe = venv_dir / ("Scripts/python.exe" if is_win else "bin/python")
            tlm_exe = venv_dir / ("Scripts/tlm.exe" if is_win else "bin/tlm")

            self._update_status("Upgrading pip...", 40)
            subprocess.run([str(py_exe), "-m", "pip", "install", "-U", "pip"], check=True)

            self._update_status("Installing tlm...", 70)
            subprocess.run(
                [str(py_exe), "-m", "pip", "install", "-U", "--editable", str(self.root_dir)],
                check=True,
            )

            self._update_status("Creating launcher...", 90)
            self._create_launcher(mode, dest if mode in (1, 2) else None, bin_dir, tlm_exe, venv_dir, is_win)

            self._update_status("Installation successful!", 100)
            self.root.after(0, self._finish_install, py_exe)

        except Exception as e:
            err = str(e)
            self.root.after(0, lambda: messagebox.showerror("Error", f"Installation failed: {err}"))
            self.root.after(0, lambda: self.next_btn.configure(state=tk.NORMAL))

    def _update_status(self, text, val):
        self.root.after(0, lambda: self.status_lbl.configure(text=text))
        self.root.after(0, lambda: self.progress.configure(value=val))

    def _create_launcher(self, mode, dest, bin_dir, tlm_exe, venv_dir, is_win):
        activate_bat = venv_dir / "Scripts" / "activate.bat"
        if mode == 1:  # Portable
            data_dir = dest / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            if is_win:
                with open(bin_dir / "tlm.bat", "w") as f:
                    f.write(
                        f'@echo off\ncall "{activate_bat}"\nset XDG_CONFIG_HOME={data_dir}\\config\nset XDG_DATA_HOME={data_dir}\\data\nset XDG_STATE_HOME={data_dir}\\state\n"{tlm_exe}" %*\n'
                    )
            else:
                sh = bin_dir / "tlm"
                with open(sh, "w") as f:
                    f.write(
                        f'#!/usr/bin/env bash\nexport XDG_CONFIG_HOME="{data_dir}/config"\nexport XDG_DATA_HOME="{data_dir}/data"\nexport XDG_STATE_HOME="{data_dir}/state"\nexec "{tlm_exe}" "$@"\n'
                    )
                sh.chmod(0o755)
        else:
            if is_win:
                with open(bin_dir / "tlm.bat", "w") as f:
                    f.write(f'@echo off\ncall "{activate_bat}"\n"{tlm_exe}" %*\n')
            else:
                link = bin_dir / "tlm"
                if link.exists():
                    link.unlink()
                os.symlink(tlm_exe, link)

        # Auto-add to PATH on Windows
        if is_win:
            _add_to_user_path_windows(bin_dir)

    def _finish_install(self, py_exe):
        if messagebox.askyesno(
            "Success",
            "Installation complete! Would you like to start the onboarding wizard to configure your LLM provider?",
        ):
            subprocess.Popen([str(py_exe), "-m", "tlm.gui.installer"])
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    InstallerWizard(root)
    root.mainloop()
