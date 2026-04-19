"""Tkinter configuration UI: keys, sessions, usage, logs, permissions."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from tlm import __version__
from tlm.providers.registry import REAL_PROVIDER_IDS, get_provider
from tlm.session import list_sessions, load_session
from tlm.settings import load_settings, save_settings
from tlm.telemetry import requests_log_path, summarize_usage


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
    root.minsize(720, 480)

    nb = ttk.Notebook(root)
    nb.pack(fill=tk.BOTH, expand=True)

    # --- Keys ---
    tab_keys = ttk.Frame(nb, padding=8)
    nb.add(tab_keys, text="Keys")
    settings = load_settings()
    prov_var = tk.StringVar(value=settings.provider or "openrouter")
    key_var = tk.StringVar()

    def load_key_for_provider(*_a: object) -> None:
        pid = prov_var.get().strip()
        s = load_settings()
        v = s.api_keys.get(pid, "") or _maybe_keyring_get(pid) or ""
        key_var.set(v)

    ttk.Label(tab_keys, text="Provider").grid(row=0, column=0, sticky="w")
    prov_box = ttk.Combobox(
        tab_keys, textvariable=prov_var, values=["stub", *REAL_PROVIDER_IDS], state="readonly", width=28
    )
    prov_box.grid(row=0, column=1, sticky="w")
    prov_box.bind("<<ComboboxSelected>>", load_key_for_provider)

    ttk.Label(tab_keys, text="API key").grid(row=1, column=0, sticky="nw")
    ent = ttk.Entry(tab_keys, textvariable=key_var, width=56, show="*")
    ent.grid(row=1, column=1, sticky="we")
    tab_keys.columnconfigure(1, weight=1)

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

    bf = ttk.Frame(tab_keys)
    bf.grid(row=2, column=1, sticky="e", pady=8)
    ttk.Button(bf, text="Save", command=save_keys).pack(side=tk.RIGHT, padx=4)
    ttk.Button(bf, text="Test connection", command=test_keys).pack(side=tk.RIGHT, padx=4)
    load_key_for_provider()

    # --- Sessions ---
    tab_sess = ttk.Frame(nb, padding=8)
    nb.add(tab_sess, text="Sessions")
    tab_sess.grid_columnconfigure(0, weight=1)
    tab_sess.grid_rowconfigure(0, weight=2)
    tab_sess.grid_rowconfigure(1, weight=1)
    cols = ("id", "updated", "title")
    tree = ttk.Treeview(tab_sess, columns=cols, show="headings", height=8)
    for c, w in zip(cols, (280, 160, 220), strict=False):
        tree.heading(c, text=c)
        tree.column(c, width=w, stretch=True)
    tree.grid(row=0, column=0, sticky="nsew")
    sb = ttk.Scrollbar(tab_sess, orient=tk.VERTICAL, command=tree.yview)
    sb.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=sb.set)
    txt = scrolledtext.ScrolledText(tab_sess, height=8, wrap=tk.WORD)
    txt.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))

    def refresh_sessions() -> None:
        tree.delete(*tree.get_children())
        for s in list_sessions():
            tree.insert("", tk.END, values=(s.id, s.updated, s.title))

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
    ttk.Button(tab_sess, text="Refresh", command=refresh_sessions).grid(row=2, column=0, sticky="e", pady=4)
    refresh_sessions()

    # --- Usage ---
    tab_use = ttk.Frame(nb, padding=8)
    nb.add(tab_use, text="Usage")
    use_txt = scrolledtext.ScrolledText(tab_use, wrap=tk.NONE)
    use_txt.pack(fill=tk.BOTH, expand=True)

    def refresh_usage() -> None:
        use_txt.delete("1.0", tk.END)
        use_txt.insert(tk.END, summarize_usage(since_days=30))

    ttk.Button(tab_use, text="Refresh", command=refresh_usage).pack(anchor="e")
    refresh_usage()

    # --- Logs ---
    tab_log = ttk.Frame(nb, padding=8)
    nb.add(tab_log, text="Logs")
    log_txt = scrolledtext.ScrolledText(tab_log, wrap=tk.NONE)
    log_txt.pack(fill=tk.BOTH, expand=True)

    def refresh_logs() -> None:
        log_txt.delete("1.0", tk.END)
        p = requests_log_path()
        if not p.is_file():
            log_txt.insert(tk.END, "(no requests log yet)")
            return
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = "\n".join(lines[-400:])
        log_txt.insert(tk.END, tail)

    ttk.Button(tab_log, text="Refresh", command=refresh_logs).pack(anchor="e")
    refresh_logs()

    # --- Permissions ---
    tab_perm = ttk.Frame(nb, padding=8)
    nb.add(tab_perm, text="Permissions")
    prof_var = tk.StringVar(value=load_settings().safety_profile)
    ttk.Label(tab_perm, text="Safety profile").grid(row=0, column=0, sticky="w")
    prof = ttk.Combobox(tab_perm, textvariable=prof_var, values=["strict", "standard", "trusted"], width=20)
    prof.grid(row=0, column=1, sticky="w")

    def save_profile() -> None:
        s = load_settings()
        s.safety_profile = prof_var.get().strip() or "standard"
        save_settings(s)
        messagebox.showinfo("tlm", "Saved safety profile.")

    ttk.Button(tab_perm, text="Save", command=save_profile).grid(row=1, column=1, sticky="w", pady=8)

    ttk.Button(root, text="Close", command=root.destroy).pack(anchor="e", padx=8, pady=8)
    root.mainloop()
