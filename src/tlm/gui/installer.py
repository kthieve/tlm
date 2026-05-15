"""Post-install onboarding wizard (Tkinter)."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
import tkinter.font as tkfont

from tlm import __version__
from tlm.providers.registry import get_provider, list_provider_ids, list_remote_model_ids
from tlm.settings import UserSettings, load_settings, save_settings
from tlm.providers.openai_compat import DEFAULT_MODELS
from tlm.gui.tips import FEATURE_TIPS, QUICKSTART_COMMANDS

# Design Tokens (matching app.py)
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


class OnboardingWizard:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"tlm — Setup Wizard ({__version__})")
        self.root.geometry("860x620")
        self.root.minsize(860, 620)
        self.root.configure(bg=_BG_PAGE)

        self.settings = load_settings()
        self.current_step = 0
        self.steps = []

        self._setup_styles()
        self._build_layout()

        # Define steps: Provider (0), Features (1), Guide (2), PATH (3)
        self.steps = [
            self._create_provider_page,
            self._create_features_page,
            self._create_guide_page,
            self._create_path_page,
        ]

        self.show_step(0)

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
        self.mono_font = tkfont.nametofont("TkFixedFont")
        self.mono_font.configure(size=10)

        self.style.configure("TFrame", background=_BG_PAGE)
        self.style.configure("TLabel", background=_BG_PAGE, foreground=_FG_BODY)
        self.style.configure(
            "Header.TLabel", background=_BG_HEADER, foreground=_FG_TITLE, font=self.header_font
        )
        self.style.configure(
            "Accent.TButton", foreground="#ffffff", background=_ACCENT, padding=(12, 6)
        )
        self.style.map("Accent.TButton", background=[("active", _ACCENT_HOVER)])

        self.style.configure("Card.TFrame", background=_BG_CARD)

    def _build_layout(self):
        # Header
        self.header = tk.Frame(self.root, bg=_BG_HEADER, padx=20, pady=15)
        self.header.pack(fill=tk.X)

        tk.Label(self.header, text="tlm", font=self.header_font, fg=_FG_TITLE, bg=_BG_HEADER).pack(
            side=tk.LEFT
        )
        self.step_label = tk.Label(
            self.header, text="Setup Wizard", font=self.base_font, fg=_FG_MUTED, bg=_BG_HEADER
        )
        self.step_label.pack(side=tk.LEFT, padx=(15, 0))

        # Content Area
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

        if index == len(self.steps) - 1:
            self.next_btn.configure(text="Finish ✓", command=self.finish)
        else:
            self.next_btn.configure(text="Next →", command=self.next_step)

        self.step_label.configure(text=f"Step {index + 1} of {len(self.steps)}")

    def next_step(self):
        if self.current_step < len(self.steps) - 1:
            self.show_step(self.current_step + 1)

    def prev_step(self):
        if self.current_step > 0:
            self.show_step(self.current_step - 1)

    def finish(self):
        try:
            from tlm.setup_wizard import write_setup_marker
            write_setup_marker()
        except ImportError:
            pass
        self.root.destroy()

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
        return tip_frame

    def _create_provider_page(self):
        self._create_tip_sidebar(
            self.content_frame,
            "Choosing a Provider",
            "tlm supports multiple providers. If you're new, OpenRouter is a great choice as it gives you access to many models with one key.",
        )

        main = tk.Frame(self.content_frame, bg=_BG_PAGE)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(main, text="LLM Provider Setup", font=self.title_font, bg=_BG_PAGE).pack(
            anchor="w", pady=(0, 20)
        )

        # Form
        form = tk.Frame(main, bg=_BG_PAGE)
        form.pack(fill=tk.X)

        tk.Label(form, text="Provider", bg=_BG_PAGE).grid(row=0, column=0, sticky="w", pady=5)
        prov_var = tk.StringVar(value=self.settings.provider or "openrouter")
        prov_cb = ttk.Combobox(
            form, textvariable=prov_var, values=list_provider_ids(), state="readonly", width=30
        )
        prov_cb.grid(row=0, column=1, sticky="w", padx=10, pady=5)

        is_default_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Set as default provider", variable=is_default_var).grid(
            row=0, column=2, sticky="w", padx=5
        )

        tk.Label(form, text="API Key", bg=_BG_PAGE).grid(row=1, column=0, sticky="w", pady=5)
        key_var = tk.StringVar(value=self.settings.api_keys.get(prov_var.get(), ""))
        key_ent = ttk.Entry(form, textvariable=key_var, show="*", width=45)
        key_ent.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        show_var = tk.BooleanVar(value=False)

        def toggle_key():
            key_ent.configure(show="" if show_var.get() else "*")

        ttk.Checkbutton(form, text="Show", variable=show_var, command=toggle_key).grid(
            row=1, column=2, sticky="w", padx=5
        )

        tk.Label(form, text="Default Model", bg=_BG_PAGE).grid(row=2, column=0, sticky="w", pady=5)
        model_var = tk.StringVar(
            value=self.settings.models.get(prov_var.get())
            or self.settings.model
            or DEFAULT_MODELS.get(prov_var.get(), "")
        )
        model_cb = ttk.Combobox(form, textvariable=model_var, width=42)
        model_cb.grid(row=2, column=1, sticky="w", padx=10, pady=5)

        status_var = tk.StringVar(value="Ready")
        status_lbl = tk.Label(main, textvariable=status_var, bg=_BG_PAGE, fg=_FG_MUTED)
        status_lbl.pack(anchor="e", pady=(5, 0))

        def on_provider_change(_event=None):
            pid = prov_var.get()
            key_var.set(self.settings.api_keys.get(pid, ""))
            model_var.set(
                self.settings.models.get(pid) or DEFAULT_MODELS.get(pid, "gpt-4o-mini")
            )
            is_default_var.set(self.settings.provider == pid)
            model_cb.configure(values=[])

        prov_cb.bind("<<ComboboxSelected>>", on_provider_change)

        def fetch_models():
            pid = prov_var.get()
            key = key_var.get().strip()
            if not key:
                messagebox.showwarning("tlm", f"Please enter an API key for {pid} first.")
                return
            status_var.set("Fetching models...")

            def worker():
                try:
                    mids = list_remote_model_ids(pid, settings=UserSettings(api_keys={pid: key}))
                    self.root.after(0, lambda: model_cb.configure(values=mids))
                    self.root.after(0, lambda: status_var.set(f"Fetched {len(mids)} models"))
                except Exception as e:
                    self.root.after(0, lambda: status_var.set(f"❌ Fetch failed: {str(e)[:30]}"))

            threading.Thread(target=worker, daemon=True).start()

        ttk.Button(form, text="Fetch Models", command=fetch_models).grid(
            row=2, column=2, sticky="w", padx=5
        )

        def test_connection():
            status_var.set("Testing...")
            status_lbl.configure(fg=_FG_MUTED)

            def worker():
                try:
                    pid = prov_var.get()
                    key = key_var.get().strip()
                    model = model_var.get().strip()
                    s = UserSettings(
                        provider=pid,
                        api_keys={pid: key},
                        models={pid: model},
                    )
                    p = get_provider(pid, settings=s)
                    out = p.complete("Reply: ok")
                    self.root.after(0, lambda: status_var.set(f"✅ Connection OK: {out[:20]}"))
                    self.root.after(0, lambda: status_lbl.configure(fg=_SUCCESS))
                except Exception as e:
                    err_msg = str(e)[:40]
                    self.root.after(0, lambda msg=err_msg: status_var.set(f"❌ Failed: {msg}..."))
                    self.root.after(0, lambda: status_lbl.configure(fg=_ERROR))

            threading.Thread(target=worker, daemon=True).start()

        def save_only():
            pid = prov_var.get()
            self.settings.api_keys[pid] = key_var.get().strip()
            self.settings.models[pid] = model_var.get().strip()
            if is_default_var.get():
                self.settings.provider = pid
                # Also set the global model if this is the default
                self.settings.model = self.settings.models[pid]
            save_settings(self.settings)
            messagebox.showinfo("tlm", f"Settings saved for {pid}.")

        btn_fr = tk.Frame(main, bg=_BG_PAGE)
        btn_fr.pack(anchor="e", pady=10)
        ttk.Button(btn_fr, text="Test Connection", command=test_connection).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_fr, text="Save Settings", command=save_only).pack(side=tk.LEFT)

    def _create_features_page(self):
        self._create_tip_sidebar(
            self.content_frame,
            "Core Features",
            FEATURE_TIPS["memory"] + "\n\n" + FEATURE_TIPS["web"],
        )

        main = tk.Frame(self.content_frame, bg=_BG_PAGE)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(main, text="Enable Features", font=self.title_font, bg=_BG_PAGE).pack(
            anchor="w", pady=(0, 20)
        )

        mem_var = tk.BooleanVar(value=self.settings.memory_enabled)
        ttk.Checkbutton(main, text="Enable Ready/Long-term Memory", variable=mem_var).pack(
            anchor="w", pady=5
        )

        upd_var = tk.BooleanVar(value=self.settings.check_for_updates)
        ttk.Checkbutton(main, text="Auto-check for updates (daily)", variable=upd_var).pack(
            anchor="w", pady=5
        )

        web_var = tk.BooleanVar(value=self.settings.web_enabled)
        ttk.Checkbutton(main, text="Enable Web Tools (Browser)", variable=web_var).pack(
            anchor="w", pady=5
        )

        tk.Label(main, text="Safety Profile", bg=_BG_PAGE).pack(anchor="w", pady=(15, 5))
        prof_var = tk.StringVar(value=self.settings.safety_profile)
        prof_cb = ttk.Combobox(
            main,
            textvariable=prof_var,
            values=["strict", "standard", "trusted", "sandbox"],
            state="readonly",
        )
        prof_cb.pack(anchor="w")

        def save_features():
            self.settings.memory_enabled = mem_var.get()
            self.settings.check_for_updates = upd_var.get()
            self.settings.web_enabled = web_var.get()
            self.settings.safety_profile = prof_var.get()
            save_settings(self.settings)
            messagebox.showinfo("tlm", "Features updated.")

        ttk.Button(main, text="Save Settings", command=save_features).pack(anchor="e", pady=20)

    def _create_guide_page(self):
        tk.Label(
            self.content_frame, text="🚀 You're Ready!", font=self.header_font, bg=_BG_PAGE
        ).pack(pady=(0, 20))

        # Examples
        card = tk.Frame(
            self.content_frame,
            bg=_BG_CARD,
            padx=20,
            pady=20,
            highlightbackground=_FG_MUTED,
            highlightthickness=1,
        )
        card.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            card, text="Try these commands in your terminal:", font=self.title_font, bg=_BG_CARD
        ).pack(anchor="w", pady=(0, 15))

        for title, cmd in QUICKSTART_COMMANDS:
            tk.Label(card, text=title, font=self.base_font, bg=_BG_CARD, fg=_FG_MUTED).pack(
                anchor="w"
            )
            f = tk.Frame(card, bg="#f1f5f9", padx=10, pady=5)
            f.pack(fill=tk.X, pady=(2, 10))
            tk.Label(f, text=f"$ {cmd}", font=self.mono_font, bg="#f1f5f9").pack(side=tk.LEFT)

    def _create_path_page(self):
        import platform
        from tlm.config import find_tlm_bin_dir

        is_windows = platform.system() == "Windows"

        tk.Label(
            self.content_frame,
            text="📎 Final Step — PATH Setup",
            font=self.header_font,
            bg=_BG_PAGE,
        ).pack(pady=(0, 20))

        tk.Label(
            self.content_frame,
            text="To run 'tlm' from anywhere, ensure the bin directory is on your PATH.",
            bg=_BG_PAGE,
            wraplength=600,
        ).pack(pady=10)

        bin_dir_path = find_tlm_bin_dir()
        bin_dir = str(bin_dir_path) if bin_dir_path else ""

        tk.Label(
            self.content_frame,
            text=f"Detected bin path: {bin_dir or 'unknown'}",
            font=self.tip_font,
            bg=_BG_PAGE,
        ).pack()

        if is_windows:
            tk.Label(
                self.content_frame,
                text="Recommended: Add to User PATH",
                font=self.title_font,
                bg=_BG_PAGE,
            ).pack(pady=(20, 10))

            def add_to_path_win():
                if not bin_dir_path:
                    messagebox.showerror("Error", "Could not detect tlm bin directory.")
                    return
                
                from install import _add_to_user_path_windows
                try:
                    added = _add_to_user_path_windows(bin_dir_path)
                    if added:
                        messagebox.showinfo("Success", "Added to your user PATH. Please restart your terminal.")
                    else:
                        messagebox.showinfo("tlm", "Path is already in your environment.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update PATH: {e}")

            ttk.Button(self.content_frame, text="Add to User PATH", command=add_to_path_win).pack(pady=10)
        else:
            tk.Label(
                self.content_frame,
                text="Recommended: Add to ~/.bashrc or ~/.zshrc",
                font=self.title_font,
                bg=_BG_PAGE,
            ).pack(pady=(20, 10))

            def add_to_rc(shell):
                rc = Path.home() / f".{shell}rc"
                if not rc.is_file():
                    messagebox.showerror("Error", f"{rc} not found.")
                    return
                line = f'\nexport PATH="{bin_dir}:$PATH"\n'
                try:
                    with open(rc, "a") as f:
                        f.write(line)
                    messagebox.showinfo(
                        "Success", f"Added to {rc}. Please restart your terminal or run 'source {rc}'."
                    )
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to write to {rc}: {e}")

            btn_fr = tk.Frame(self.content_frame, bg=_BG_PAGE)
            btn_fr.pack()

            ttk.Button(btn_fr, text="Add to ~/.bashrc", command=lambda: add_to_rc("bash")).pack(
                side=tk.LEFT, padx=10
            )
            ttk.Button(btn_fr, text="Add to ~/.zshrc", command=lambda: add_to_rc("zsh")).pack(
                side=tk.LEFT, padx=10
            )


def run_onboarding():
    root = tk.Tk()
    OnboardingWizard(root)
    root.mainloop()


if __name__ == "__main__":
    run_onboarding()
