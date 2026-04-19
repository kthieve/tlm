"""Tkinter configuration UI: keys, sessions, usage, logs, permissions."""

from __future__ import annotations

import json
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, scrolledtext, ttk

from tlm import __version__
from tlm.providers.registry import REAL_PROVIDER_IDS, get_provider
from tlm.session import list_sessions, load_session
from tlm.settings import load_settings, save_settings
from tlm.telemetry import requests_log_path, summarize_usage

# Light shell: header + soft page background (works with clam / default ttk)
_BG_PAGE = "#e8edf3"
_BG_HEADER = "#0f172a"
_FG_MUTED = "#94a3b8"
_FG_TITLE = "#f1f5f9"
_TREE_STRIPE = "#f1f5f9"


def _maybe_keyring_get(provider_id: str) -> str | None:
    try:
        import keyring  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        return keyring.get_password("tlm", provider_id)
    except Exception:
        return None


def _maybe_keyring_set(provider_id: str, secret: str) -> None:
    try:
        import keyring  # type: ignore[import-not-found]
    except ImportError:
        return
    try:
        keyring.set_password("tlm", provider_id, secret)
    except Exception:
        pass


def run_gui() -> None:
    root = tk.Tk()
    root.title(f"tlm — configuration ({__version__})")
    root.minsize(780, 520)
    root.configure(bg=_BG_PAGE)

    style = ttk.Style(root)
    for name in ("clam", "alt", "default"):
        if name in style.theme_names():
            style.theme_use(name)
            break

    base_font = tkfont.nametofont("TkDefaultFont")
    title_font = base_font.copy()
    title_font.configure(size=13, weight="bold")
    small_font = base_font.copy()
    small_font.configure(size=9)
    mono = tkfont.nametofont("TkFixedFont")
    mono.configure(size=10)

    style.configure("TFrame", background=_BG_PAGE)
    style.configure("TLabelframe", background=_BG_PAGE)
    style.configure("TLabelframe.Label", background=_BG_PAGE, font=small_font)
    style.configure("TNotebook", background=_BG_PAGE)
    style.configure("TNotebook.Tab", padding=(14, 6))
    style.configure("Treeview", rowheight=26, font=base_font)
    style.configure("Treeview.Heading", font=small_font)
    style.map("Treeview", background=[("selected", "#2563eb")])
    try:
        style.configure("Accent.TButton", foreground="#ffffff", background="#2563eb", padding=(12, 6))
        style.map("Accent.TButton", background=[("active", "#1d4ed8"), ("pressed", "#1e40af")])
    except tk.TclError:
        style.configure("Accent.TButton", padding=(12, 6))

    header = tk.Frame(root, bg=_BG_HEADER, padx=20, pady=14)
    header.pack(fill=tk.X)
    tk.Label(header, text="tlm", font=title_font, fg=_FG_TITLE, bg=_BG_HEADER).pack(side=tk.LEFT)
    tk.Label(
        header,
        text="Configuration",
        font=small_font,
        fg=_FG_MUTED,
        bg=_BG_HEADER,
    ).pack(side=tk.LEFT, padx=(10, 0))
    tk.Label(header, text=f"v{__version__}", font=small_font, fg=_FG_MUTED, bg=_BG_HEADER).pack(side=tk.RIGHT)

    outer = ttk.Frame(root, padding=(14, 12))
    outer.pack(fill=tk.BOTH, expand=True)

    nb = ttk.Notebook(outer)
    nb.pack(fill=tk.BOTH, expand=True)

    # --- Keys ---
    tab_keys = ttk.Frame(nb, padding=12)
    nb.add(tab_keys, text="Keys")
    tab_keys.columnconfigure(0, weight=1)

    lf_keys = ttk.LabelFrame(tab_keys, text="Provider & API key", padding=(12, 10))
    lf_keys.grid(row=0, column=0, sticky="nsew")
    tab_keys.rowconfigure(0, weight=1)

    settings = load_settings()
    prov_var = tk.StringVar(value=settings.provider or "openrouter")
    key_var = tk.StringVar()

    def load_key_for_provider(*_a: object) -> None:
        pid = prov_var.get().strip()
        s = load_settings()
        v = s.api_keys.get(pid, "") or _maybe_keyring_get(pid) or ""
        key_var.set(v)

    ttk.Label(lf_keys, text="Provider").grid(row=0, column=0, sticky="w", pady=(0, 6))
    prov_box = ttk.Combobox(
        lf_keys, textvariable=prov_var, values=["stub", *REAL_PROVIDER_IDS], state="readonly", width=32
    )
    prov_box.grid(row=0, column=1, sticky="w", pady=(0, 6))
    prov_box.bind("<<ComboboxSelected>>", load_key_for_provider)

    ttk.Label(lf_keys, text="API key").grid(row=1, column=0, sticky="nw", pady=(4, 0))
    ent = ttk.Entry(lf_keys, textvariable=key_var, width=58, show="*")
    ent.grid(row=1, column=1, sticky="we", pady=(4, 0))
    lf_keys.columnconfigure(1, weight=1)

    def save_keys() -> None:
        s = load_settings()
        pid = prov_var.get().strip()
        s.provider = pid
        if key_var.get().strip():
            s.api_keys[pid] = key_var.get().strip()
            _maybe_keyring_set(pid, key_var.get().strip())
        save_settings(s)
        messagebox.showinfo("tlm", "Saved config.toml (and keyring if available).")

    def test_keys() -> None:
        s = load_settings()
        s.provider = prov_var.get().strip()
        if key_var.get().strip():
            s.api_keys[s.provider] = key_var.get().strip()
        try:
            p = get_provider(s.provider, settings=s)
            out = p.complete("Reply with the single word: ok", system="You are a connection test.")
            messagebox.showinfo("tlm", out[:400])
        except Exception as e:  # noqa: BLE001 — show user-visible error
            messagebox.showerror("tlm", str(e))

    bf = ttk.Frame(lf_keys)
    bf.grid(row=2, column=1, sticky="e", pady=(14, 0))
    ttk.Button(bf, text="Save", command=save_keys, style="Accent.TButton").pack(side=tk.RIGHT, padx=(6, 0))
    ttk.Button(bf, text="Test connection", command=test_keys).pack(side=tk.RIGHT)
    load_key_for_provider()

    # --- Sessions ---
    tab_sess = ttk.Frame(nb, padding=12)
    nb.add(tab_sess, text="Sessions")
    tab_sess.grid_columnconfigure(0, weight=1)
    tab_sess.grid_rowconfigure(0, weight=2)
    tab_sess.grid_rowconfigure(1, weight=1)

    lf_list = ttk.LabelFrame(tab_sess, text="Sessions", padding=(8, 6))
    lf_list.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 8))
    lf_list.columnconfigure(0, weight=1)
    lf_list.rowconfigure(0, weight=1)

    cols = ("id", "updated", "title")
    tree = ttk.Treeview(lf_list, columns=cols, show="headings", height=9)
    for c, w in zip(cols, (300, 170, 240), strict=False):
        tree.heading(c, text=c.replace("_", " ").title())
        tree.column(c, width=w, stretch=True)
    tree.grid(row=0, column=0, sticky="nsew")
    sb = ttk.Scrollbar(lf_list, orient=tk.VERTICAL, command=tree.yview)
    sb.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=sb.set)
    tree.tag_configure("odd", background=_TREE_STRIPE)
    tree.tag_configure("even", background="#ffffff")

    lf_json = ttk.LabelFrame(tab_sess, text="Session JSON", padding=(8, 6))
    lf_json.grid(row=1, column=0, columnspan=2, sticky="nsew")
    lf_json.columnconfigure(0, weight=1)
    lf_json.rowconfigure(0, weight=1)

    txt = scrolledtext.ScrolledText(lf_json, height=10, wrap=tk.WORD, font=mono, relief=tk.FLAT, padx=6, pady=6)
    txt.grid(row=0, column=0, sticky="nsew")

    def refresh_sessions() -> None:
        tree.delete(*tree.get_children())
        for i, s in enumerate(list_sessions()):
            tag = "odd" if i % 2 else "even"
            tree.insert("", tk.END, values=(s.id, s.updated, s.title), tags=(tag,))

    def on_open(_e: object) -> None:
        sel = tree.selection()
        if not sel:
            return
        sid = tree.item(sel[0], "values")[0]
        sess = load_session(str(sid))
        txt.delete("1.0", tk.END)
        if sess is None:
            txt.insert(tk.END, "session not found")
            return
        txt.insert(tk.END, json.dumps(sess.to_json(), indent=2))

    tree.bind("<Double-1>", on_open)
    ttk.Button(tab_sess, text="Refresh", command=refresh_sessions).grid(row=2, column=1, sticky="e", pady=(6, 0))
    refresh_sessions()

    # --- Usage ---
    tab_use = ttk.Frame(nb, padding=12)
    nb.add(tab_use, text="Usage")
    tab_use.rowconfigure(0, weight=1)
    tab_use.columnconfigure(0, weight=1)

    use_txt = scrolledtext.ScrolledText(tab_use, wrap=tk.NONE, font=mono, relief=tk.FLAT, padx=8, pady=8)
    use_txt.grid(row=0, column=0, sticky="nsew")

    def refresh_usage() -> None:
        use_txt.delete("1.0", tk.END)
        use_txt.insert(tk.END, summarize_usage(since_days=30))

    ttk.Button(tab_use, text="Refresh", command=refresh_usage).grid(row=1, column=0, sticky="e", pady=(8, 0))
    refresh_usage()

    # --- Logs ---
    tab_log = ttk.Frame(nb, padding=12)
    nb.add(tab_log, text="Logs")
    tab_log.rowconfigure(0, weight=1)
    tab_log.columnconfigure(0, weight=1)

    log_txt = scrolledtext.ScrolledText(tab_log, wrap=tk.NONE, font=mono, relief=tk.FLAT, padx=8, pady=8)
    log_txt.grid(row=0, column=0, sticky="nsew")

    def refresh_logs() -> None:
        log_txt.delete("1.0", tk.END)
        p = requests_log_path()
        if not p.is_file():
            log_txt.insert(tk.END, "(no requests log yet)")
            return
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = "\n".join(lines[-400:])
        log_txt.insert(tk.END, tail)

    ttk.Button(tab_log, text="Refresh", command=refresh_logs).grid(row=1, column=0, sticky="e", pady=(8, 0))
    refresh_logs()

    # --- Permissions ---
    tab_perm = ttk.Frame(nb, padding=12)
    nb.add(tab_perm, text="Permissions")
    lf_perm = ttk.LabelFrame(tab_perm, text="Safety", padding=(12, 10))
    lf_perm.grid(row=0, column=0, sticky="nw")
    prof_var = tk.StringVar(value=load_settings().safety_profile)
    ttk.Label(lf_perm, text="Safety profile").grid(row=0, column=0, sticky="w", padx=(0, 12))
    prof = ttk.Combobox(lf_perm, textvariable=prof_var, values=["strict", "standard", "trusted"], width=22)
    prof.grid(row=0, column=1, sticky="w")

    def save_profile() -> None:
        s = load_settings()
        s.safety_profile = prof_var.get().strip() or "standard"
        save_settings(s)
        messagebox.showinfo("tlm", "Saved safety profile.")

    ttk.Button(lf_perm, text="Save", command=save_profile, style="Accent.TButton").grid(
        row=1, column=1, sticky="w", pady=(12, 0)
    )

    foot = ttk.Frame(outer)
    foot.pack(fill=tk.X, pady=(10, 0))
    ttk.Separator(foot, orient=tk.HORIZONTAL).pack(fill=tk.X)
    ttk.Button(foot, text="Close", command=root.destroy).pack(anchor=tk.E, pady=(10, 0))

    root.mainloop()
