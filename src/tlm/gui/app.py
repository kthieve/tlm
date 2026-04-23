"""Tkinter configuration UI: keys, sessions, usage, logs, permissions."""

from __future__ import annotations

import json
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

import os

from tlm import __version__
from tlm.harvest import apply_harvest_items, extract_harvest_items
from tlm.memory import (
    STORAGE_RULES_TEXT,
    add_longterm,
    delete_longterm,
    iter_longterm,
    load_ready,
    save_ready,
)
from tlm.providers.registry import REAL_PROVIDER_IDS, get_provider
from tlm.self_update import format_version_update_status
from tlm.safety.permissions import load_permissions_file, permissions_file_path, save_permissions_file
from tlm.safety.profiles import SafetyProfile, normalize_profile
from tlm.session import (
    delete_session,
    list_sessions,
    load_session,
    rename_session,
    write_last_session_id,
)
from tlm.settings import load_settings, save_settings
from tlm.web.lightpanda_release import (
    RELEASES_PAGE,
    compare_status,
    describe_local_install,
    fetch_latest_release,
    install_latest_to_data_dir,
    preferred_asset_basename,
    try_add_tlm_data_bin_to_path_rc,
)
from tlm.telemetry import requests_log_path, summarize_usage
from tlm.telemetry.log import scrub_text_line

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
    lf_keys.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
    tab_keys.rowconfigure(0, weight=0)

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

    # --- Web / Lightpanda ---
    tab_web = ttk.Frame(nb, padding=12)
    nb.add(tab_web, text="Web / Lightpanda")
    tab_web.columnconfigure(0, weight=1)
    tab_web.rowconfigure(1, weight=1)

    ws = load_settings()
    web_en_var = tk.BooleanVar(value=bool(ws.web_enabled))
    lp_path_var = tk.StringVar(value=ws.lightpanda_path or "")
    web_ua_var = tk.StringVar(value=ws.web_user_agent or "")
    web_ua_suffix_var = tk.StringVar(value=ws.web_user_agent_suffix or "")
    web_auto_check_var = tk.BooleanVar(value=bool(ws.web_check_lightpanda_updates))

    lf_web = ttk.LabelFrame(tab_web, text="Ask mode — `tlm-web` / `tlm web`", padding=(12, 10))
    lf_web.grid(row=0, column=0, sticky="ew")
    lf_web.columnconfigure(1, weight=1)
    ttk.Checkbutton(
        lf_web,
        text="web_enabled (allow Lightpanda fetches in ask mode)",
        variable=web_en_var,
    ).grid(row=0, column=0, columnspan=3, sticky="w")
    ttk.Label(lf_web, text="lightpanda_path").grid(row=1, column=0, sticky="w", pady=(10, 0))
    ttk.Entry(lf_web, textvariable=lp_path_var, width=52).grid(row=1, column=1, sticky="we", pady=(10, 0))

    def browse_lightpanda() -> None:
        p = filedialog.askopenfilename(title="Select lightpanda binary")
        if p:
            lp_path_var.set(p)

    ttk.Button(lf_web, text="Browse…", command=browse_lightpanda).grid(
        row=1, column=2, sticky="w", padx=(8, 0), pady=(10, 0)
    )
    ttk.Checkbutton(
        lf_web,
        text="Auto-check GitHub release when opening this tab",
        variable=web_auto_check_var,
    ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
    ttk.Label(lf_web, text="web_user_agent").grid(row=3, column=0, sticky="w", pady=(10, 0))
    ttk.Entry(lf_web, textvariable=web_ua_var, width=52).grid(row=3, column=1, sticky="we", pady=(10, 0))
    ttk.Label(lf_web, text="web_user_agent_suffix").grid(row=4, column=0, sticky="w", pady=(8, 0))
    ttk.Entry(lf_web, textvariable=web_ua_suffix_var, width=52).grid(row=4, column=1, sticky="we", pady=(8, 0))
    ttk.Label(
        lf_web,
        text="Compatibility passthrough only. Does not bypass anti-bot checks.",
    ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))

    lf_status = ttk.LabelFrame(tab_web, text="Status & updates (GitHub)", padding=(12, 10))
    lf_status.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
    lf_status.columnconfigure(0, weight=1)
    lf_status.rowconfigure(0, weight=1)
    lp_status = scrolledtext.ScrolledText(
        lf_status, wrap=tk.WORD, font=mono, height=10, relief=tk.FLAT, padx=8, pady=8
    )
    lp_status.grid(row=0, column=0, sticky="nsew")

    def save_web_settings() -> None:
        s = load_settings()
        s.web_enabled = bool(web_en_var.get())
        lp_p = lp_path_var.get().strip()
        s.lightpanda_path = lp_p if lp_p else None
        ua = web_ua_var.get().strip()
        uas = web_ua_suffix_var.get().strip()
        s.web_user_agent = ua or None
        s.web_user_agent_suffix = uas or None
        s.web_check_lightpanda_updates = bool(web_auto_check_var.get())
        save_settings(s)
        messagebox.showinfo("tlm", "Saved web settings to config.toml.")

    def refresh_lp_status() -> None:
        s = load_settings()
        s.web_enabled = bool(web_en_var.get())
        s.lightpanda_path = lp_path_var.get().strip() or None
        lines = [describe_local_install(s), ""]
        want = preferred_asset_basename()
        if not want:
            lines.append(
                f"This OS/arch has no mapped GitHub asset (got {want or 'unknown'}). Open releases to pick a build."
            )
        else:
            ok, data = fetch_latest_release(timeout=15.0)
            if ok and isinstance(data, dict):
                lines.append(compare_status(s, data))
            else:
                lines.append(f"Could not reach GitHub: {data}")
        lp_status.delete("1.0", tk.END)
        lp_status.insert(tk.END, "\n".join(lines))

    def download_lightpanda_gui() -> None:
        if not messagebox.askyesno(
            "tlm",
            "Download the latest Lightpanda binary for this OS from GitHub into your tlm data directory "
            "and set lightpanda_path? (~/.local/share/tlm/bin/lightpanda)",
        ):
            return

        def _fmt_bytes(n: int) -> str:
            if n < 1024:
                return f"{n} B"
            if n < 1024 * 1024:
                return f"{n / 1024:.1f} KiB"
            return f"{n / (1024 * 1024):.1f} MiB"

        dlg = tk.Toplevel(root)
        dlg.title("Downloading Lightpanda")
        dlg.transient(root)
        dlg.resizable(False, False)
        dlg.grab_set()
        cancel_ev = threading.Event()
        fr = ttk.Frame(dlg, padding=20)
        fr.pack(fill=tk.BOTH, expand=True)
        lbl_prog = ttk.Label(fr, text="Starting…", justify=tk.CENTER)
        lbl_prog.pack(pady=(0, 8))
        pb = ttk.Progressbar(fr, mode="indeterminate", length=320)
        pb.pack(pady=(0, 8))
        pb.start(14)
        btn_fr = ttk.Frame(fr)
        btn_fr.pack(fill=tk.X)
        ttk.Label(
            btn_fr,
            text="Partial downloads resume next time. Cancel keeps the .partial file.",
            font=("TkDefaultFont", 8),
            foreground="#555",
        ).pack(anchor="w", pady=(0, 6))

        outcome: list[tuple[bool, str, Path | None] | BaseException] = []

        def apply_progress(n: int, total: int | None) -> None:
            lbl_prog.configure(text=f"{_fmt_bytes(n)} / {_fmt_bytes(total) if total else '…'}")
            if total and total > 0:
                pb.stop()
                pb.configure(mode="determinate", maximum=100.0, value=min(100.0, 100.0 * n / total))
            else:
                if pb.cget("mode") == "determinate":
                    pb.configure(mode="indeterminate")
                    pb.start(14)

        def schedule_progress(n: int, total: int | None) -> None:
            root.after(0, lambda: apply_progress(n, total))

        def worker() -> None:
            try:
                s = load_settings()
                s.web_enabled = bool(web_en_var.get())
                s.lightpanda_path = lp_path_var.get().strip() or None
                outcome.append(
                    install_latest_to_data_dir(
                        s,
                        timeout=600.0,
                        cancel_event=cancel_ev,
                        progress=schedule_progress,
                    )
                )
            except BaseException as e:  # noqa: BLE001 — surface any failure in GUI
                outcome.append(e)

        def do_cancel() -> None:
            cancel_ev.set()
            lbl_prog.configure(text="Cancelling…")

        ttk.Button(btn_fr, text="Cancel", command=do_cancel).pack(side=tk.RIGHT)

        def on_close() -> None:
            do_cancel()

        dlg.protocol("WM_DELETE_WINDOW", on_close)

        threading.Thread(target=worker, daemon=True).start()

        def finish() -> None:
            pb.stop()
            dlg.grab_release()
            dlg.destroy()
            if not outcome:
                messagebox.showerror("tlm", "Download finished with no result (unexpected).")
                return
            raw = outcome[0]
            if isinstance(raw, BaseException):
                messagebox.showerror("tlm", f"Download failed: {raw}")
                return
            ok, msg, dest = raw
            if ok and dest:
                lp_path_var.set(str(dest))
                save_web_settings()
                messagebox.showinfo("tlm", msg)
                refresh_lp_status()
                pdir = dest.parent
                if messagebox.askyesno(
                    "tlm",
                    f"Add {pdir} to your PATH in ~/.bashrc or ~/.zshrc (based on $SHELL)?\n"
                    "New terminals will find `lightpanda` without `lightpanda_path` in config.",
                ):
                    ok_p, pmsg = try_add_tlm_data_bin_to_path_rc()
                    (messagebox.showinfo if ok_p else messagebox.showerror)("tlm", pmsg)
            elif "cancelled" in msg.lower():
                messagebox.showwarning("tlm", msg)
            else:
                messagebox.showerror("tlm", msg)

        def poll() -> None:
            if outcome:
                finish()
            else:
                dlg.update_idletasks()
                dlg.after(80, poll)

        dlg.after(80, poll)

    wf = ttk.Frame(tab_web)
    wf.grid(row=2, column=0, sticky="ew", pady=(10, 0))
    ttk.Button(wf, text="Save web settings", command=save_web_settings, style="Accent.TButton").pack(
        side=tk.LEFT, padx=(0, 8)
    )
    ttk.Button(wf, text="Refresh status", command=refresh_lp_status).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(wf, text="Download / update binary", command=download_lightpanda_gui).pack(
        side=tk.LEFT, padx=(0, 8)
    )
    ttk.Button(wf, text="Open releases page", command=lambda: webbrowser.open(RELEASES_PAGE)).pack(
        side=tk.LEFT
    )

    def add_tlm_bin_to_path() -> None:
        ok_p, pmsg = try_add_tlm_data_bin_to_path_rc()
        (messagebox.showinfo if ok_p else messagebox.showerror)("tlm", pmsg)

    ttk.Button(wf, text="Add data bin to PATH (shell rc)", command=add_tlm_bin_to_path).pack(
        side=tk.LEFT, padx=(0, 8)
    )
    ttk.Label(
        wf,
        text="(After install: so `lightpanda` is on PATH; uses ~/.bashrc or ~/.zshrc.)",
        font=("TkDefaultFont", 8),
        foreground="#555",
    ).pack(side=tk.LEFT, padx=(0, 0))

    def on_notebook_tab_change(_e: object) -> None:
        try:
            tab_id = nb.select()
            label = nb.tab(tab_id, "text")
        except tk.TclError:
            return
        if label == "Web / Lightpanda" and web_auto_check_var.get():
            root.after(100, refresh_lp_status)
        if label == "About":
            root.after(50, lambda: refresh_about(online=False))

    nb.bind("<<NotebookTabChanged>>", on_notebook_tab_change)

    # --- About (version / tlm GitHub update status) ---
    tab_about = ttk.Frame(nb, padding=12)
    nb.add(tab_about, text="About")
    tab_about.columnconfigure(0, weight=1)
    ttk.Label(
        tab_about,
        text="Installed version, install kind, and optional check for a newer GitHub release (same logic as `tlm update`).",
    ).grid(row=0, column=0, sticky="w")
    about_body = scrolledtext.ScrolledText(tab_about, height=14, wrap=tk.WORD, font=mono)
    about_body.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
    tab_about.rowconfigure(1, weight=1)

    def refresh_about(*, online: bool = False) -> None:
        txt = format_version_update_status(load_settings(), query_github=online)
        about_body.configure(state=tk.NORMAL)
        about_body.delete("1.0", tk.END)
        about_body.insert(tk.END, txt)
        about_body.configure(state=tk.DISABLED)

    ab_fr = ttk.Frame(tab_about)
    ab_fr.grid(row=2, column=0, sticky="ew", pady=(8, 0))
    ttk.Button(
        ab_fr,
        text="Refresh (query GitHub for latest release tag)",
        command=lambda: refresh_about(online=True),
    ).pack(side=tk.LEFT)
    refresh_about(online=False)

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

    cols = ("keyword", "id", "updated", "title")
    tree = ttk.Treeview(lf_list, columns=cols, show="headings", height=9)
    for c, w in zip(cols, (100, 220, 160, 200), strict=False):
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
            tree.insert("", tk.END, values=(s.keyword, s.id, s.updated, s.title), tags=(tag,))

    def _selected_sid() -> str | None:
        sel = tree.selection()
        if not sel:
            return None
        return str(tree.item(sel[0], "values")[1])

    def on_open(_e: object) -> None:
        sid = _selected_sid()
        if not sid:
            return
        sess = load_session(sid)
        txt.delete("1.0", tk.END)
        if sess is None:
            txt.insert(tk.END, "session not found")
            return
        txt.insert(tk.END, json.dumps(sess.to_json(), indent=2))

    def sess_resume() -> None:
        sid = _selected_sid()
        if not sid:
            return
        write_last_session_id(sid)
        messagebox.showinfo("tlm", f"Active session set to {sid[:8]}…")

    def sess_delete() -> None:
        sid = _selected_sid()
        if not sid or not messagebox.askyesno("tlm", "Delete this session?"):
            return
        if delete_session(sid):
            refresh_sessions()
            txt.delete("1.0", tk.END)

    def sess_rename() -> None:
        sid = _selected_sid()
        if not sid:
            return
        title = simpledialog.askstring("tlm", "New title:", parent=root)
        if title and rename_session(sid, title):
            refresh_sessions()

    def sess_harvest() -> None:
        sid = _selected_sid()
        if not sid:
            return
        sess = load_session(sid)
        if sess is None:
            return
        st = load_settings()
        try:
            prov = get_provider(st.provider, settings=st)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("tlm", str(e))
            return
        items = extract_harvest_items(prov, sess)
        if not items:
            messagebox.showinfo("tlm", "Nothing to harvest.")
            return
        if not messagebox.askyesno("tlm", f"Store {len(items)} item(s) to long-term memory?"):
            return
        apply_harvest_items(items, source_session=sess.id, settings=st, push_ready_summary=True)
        from datetime import datetime, timezone

        sess.last_harvested_at = datetime.now(timezone.utc).isoformat()
        sess.message_count_at_last_harvest = len(sess.messages)
        from tlm.session import save_session

        save_session(sess)
        messagebox.showinfo("tlm", "Harvest saved.")

    tree.bind("<Double-1>", on_open)
    bf_sess = ttk.Frame(tab_sess)
    bf_sess.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
    ttk.Button(bf_sess, text="Resume", command=sess_resume).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(bf_sess, text="Delete", command=sess_delete).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(bf_sess, text="Rename", command=sess_rename).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(bf_sess, text="Harvest", command=sess_harvest).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(bf_sess, text="Refresh", command=refresh_sessions).pack(side=tk.RIGHT)
    refresh_sessions()

    # --- Memory ---
    tab_mem = ttk.Frame(nb, padding=12)
    nb.add(tab_mem, text="Memory")
    tab_mem.columnconfigure(0, weight=1)
    tab_mem.rowconfigure(1, weight=1)
    tab_mem.rowconfigure(2, weight=1)

    lf_rules = ttk.LabelFrame(tab_mem, text="Storage rules", padding=(8, 6))
    lf_rules.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
    lf_rules.columnconfigure(0, weight=1)
    rules_txt = scrolledtext.ScrolledText(lf_rules, height=6, wrap=tk.WORD, font=small_font, relief=tk.FLAT)
    rules_txt.grid(row=0, column=0, sticky="nsew")
    rules_txt.insert(tk.END, STORAGE_RULES_TEXT)
    rules_txt.configure(state=tk.DISABLED)

    lf_ready = ttk.LabelFrame(tab_mem, text="Ready memory (injected into ask)", padding=(8, 6))
    lf_ready.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
    lf_ready.columnconfigure(0, weight=1)
    lf_ready.rowconfigure(0, weight=1)
    ready_edit = scrolledtext.ScrolledText(lf_ready, height=8, wrap=tk.WORD, font=mono, relief=tk.FLAT)

    def refresh_ready_editor() -> None:
        ready_edit.delete("1.0", tk.END)
        ready_edit.insert(tk.END, "\n".join(load_ready()))

    def save_ready_gui() -> None:
        st = load_settings()
        lines = [ln.strip() for ln in ready_edit.get("1.0", tk.END).splitlines() if ln.strip()]
        from tlm.memory import is_safe_to_store

        bad = [ln for ln in lines if not is_safe_to_store(ln)[0]]
        if bad:
            messagebox.showerror("tlm", f"Rejected unsafe lines: {bad[:3]}…")
            return
        save_ready(lines, budget_chars=st.memory_ready_budget_chars)
        messagebox.showinfo("tlm", "Saved ready memory.")

    ready_edit.grid(row=0, column=0, sticky="nsew")
    ttk.Button(lf_ready, text="Save ready memory", command=save_ready_gui).grid(row=1, column=0, sticky="e", pady=(6, 0))
    refresh_ready_editor()

    lf_lt = ttk.LabelFrame(tab_mem, text="Long-term memory", padding=(8, 6))
    lf_lt.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
    lf_lt.columnconfigure(0, weight=1)
    lf_lt.rowconfigure(0, weight=1)
    lt_cols = ("text", "tags", "source", "created", "id")
    lt_tree = ttk.Treeview(lf_lt, columns=lt_cols, show="headings", height=7)
    for c, w in zip(lt_cols, (280, 80, 80, 140, 0), strict=False):
        lt_tree.heading(c, text=c.title())
        lt_tree.column(c, width=w if w else 1, stretch=True)
    lt_tree.grid(row=0, column=0, sticky="nsew")
    ltsb = ttk.Scrollbar(lf_lt, orient=tk.VERTICAL, command=lt_tree.yview)
    ltsb.grid(row=0, column=1, sticky="ns")
    lt_tree.configure(yscrollcommand=ltsb.set)

    def refresh_longterm() -> None:
        lt_tree.delete(*lt_tree.get_children())
        for e in iter_longterm():
            lt_tree.insert(
                "",
                tk.END,
                values=(e.text[:200], ",".join(e.tags), e.source_session or "", e.created, e.id),
            )

    def lt_add() -> None:
        t = simpledialog.askstring("tlm", "New memory line:", parent=root)
        if t and add_longterm(t, tags=["gui"], source_session=None):
            refresh_longterm()
        elif t:
            messagebox.showerror("tlm", "Rejected (unsafe or duplicate).")

    def lt_delete() -> None:
        sel = lt_tree.selection()
        if not sel:
            return
        eid = str(lt_tree.item(sel[0], "values")[4])
        if delete_longterm(eid):
            refresh_longterm()

    lbf = ttk.Frame(lf_lt)
    lbf.grid(row=1, column=0, sticky="e", pady=(6, 0))
    ttk.Button(lbf, text="Add", command=lt_add).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(lbf, text="Delete", command=lt_delete).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(lbf, text="Refresh", command=refresh_longterm).pack(side=tk.RIGHT)
    refresh_longterm()

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
        tail = "\n".join(scrub_text_line(ln) for ln in lines[-400:])
        log_txt.insert(tk.END, tail)

    ttk.Button(tab_log, text="Refresh", command=refresh_logs).grid(row=1, column=0, sticky="e", pady=(8, 0))
    refresh_logs()

    # --- Permissions ---
    tab_perm = ttk.Frame(nb, padding=12)
    nb.add(tab_perm, text="Permissions")
    tab_perm.columnconfigure(0, weight=1)
    tab_perm.rowconfigure(2, weight=1)

    if os.geteuid() == 0:
        ttk.Label(
            tab_perm,
            text="Warning: GUI running as root — use least privilege when possible.",
            foreground="#b91c1c",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

    lf_prof = ttk.LabelFrame(tab_perm, text="Safety profile (config.toml)", padding=(12, 10))
    lf_prof.grid(row=1, column=0, sticky="ew", pady=(0, 8))
    prof_var = tk.StringVar(value=load_settings().safety_profile)
    ttk.Label(lf_prof, text="Profile").grid(row=0, column=0, sticky="w", padx=(0, 12))
    prof = ttk.Combobox(lf_prof, textvariable=prof_var, values=["strict", "standard", "trusted"], width=22)
    prof.grid(row=0, column=1, sticky="w")
    rp = normalize_profile(prof_var.get())
    root_note = (
        "Root policy: strict/standard block system paths; trusted requires typing the exact phrase in the CLI."
        if rp != SafetyProfile.trusted
        else "Root policy: trusted — system paths require the CLI phrase gate."
    )
    ttk.Label(lf_prof, text=root_note, wraplength=720).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def save_profile() -> None:
        s = load_settings()
        s.safety_profile = prof_var.get().strip() or "standard"
        save_settings(s)
        messagebox.showinfo("tlm", "Saved safety profile.")

    ttk.Button(lf_prof, text="Save profile", command=save_profile, style="Accent.TButton").grid(
        row=2, column=1, sticky="e", pady=(12, 0)
    )

    lf_pe = ttk.LabelFrame(tab_perm, text=f"permissions.toml — {permissions_file_path()}", padding=(12, 10))
    lf_pe.grid(row=2, column=0, sticky="nsew")
    lf_pe.columnconfigure(0, weight=1)
    lf_pe.columnconfigure(1, weight=1)

    net_var = tk.StringVar(value="ask")
    sbox_var = tk.StringVar(value="auto")
    lb_rw = tk.Listbox(lf_pe, height=8, font=mono)
    lb_ro = tk.Listbox(lf_pe, height=8, font=mono)
    lb_eg = tk.Listbox(lf_pe, height=5, font=mono)

    def reload_perm_lists() -> None:
        pf = load_permissions_file()
        net_var.set(pf.network_mode)
        sbox_var.set(pf.sandbox_engine)
        lb_rw.delete(0, tk.END)
        for x in pf.allow_paths:
            lb_rw.insert(tk.END, x)
        lb_ro.delete(0, tk.END)
        for x in pf.read_paths:
            lb_ro.insert(tk.END, x)
        lb_eg.delete(0, tk.END)
        for x in pf.escape_grants:
            lb_eg.insert(tk.END, x)

    ttk.Label(lf_pe, text="Network mode").grid(row=0, column=0, sticky="w")
    ttk.Combobox(
        lf_pe, textvariable=net_var, values=["off", "ask", "on"], width=14, state="readonly"
    ).grid(row=0, column=1, sticky="w")
    ttk.Label(lf_pe, text="Sandbox engine").grid(row=1, column=0, sticky="w", pady=(4, 0))
    ttk.Combobox(
        lf_pe,
        textvariable=sbox_var,
        values=["auto", "bwrap", "firejail", "off"],
        width=14,
        state="readonly",
    ).grid(row=1, column=1, sticky="w", pady=(4, 0))

    ttk.Label(lf_pe, text="Free (read & write)").grid(row=2, column=0, sticky="w", pady=(10, 0))
    ttk.Label(lf_pe, text="Free (read only)").grid(row=2, column=1, sticky="w", pady=(10, 0))
    lb_rw.grid(row=3, column=0, sticky="nsew", padx=(0, 6))
    lb_ro.grid(row=3, column=1, sticky="nsew")

    def add_rw() -> None:
        d = filedialog.askdirectory(parent=root)
        if not d:
            return
        pf = load_permissions_file()
        r = str(Path(d).resolve())
        if r not in pf.allow_paths:
            pf.allow_paths.append(r)
        save_permissions_file(pf)
        reload_perm_lists()

    def add_ro() -> None:
        d = filedialog.askdirectory(parent=root)
        if not d:
            return
        pf = load_permissions_file()
        r = str(Path(d).resolve())
        if r not in pf.read_paths:
            pf.read_paths.append(r)
        save_permissions_file(pf)
        reload_perm_lists()

    def del_rw() -> None:
        sel = lb_rw.curselection()
        if not sel:
            return
        p = lb_rw.get(sel[0])
        pf = load_permissions_file()
        pf.allow_paths = [x for x in pf.allow_paths if x != p]
        save_permissions_file(pf)
        reload_perm_lists()

    def del_ro() -> None:
        sel = lb_ro.curselection()
        if not sel:
            return
        p = lb_ro.get(sel[0])
        pf = load_permissions_file()
        pf.read_paths = [x for x in pf.read_paths if x != p]
        save_permissions_file(pf)
        reload_perm_lists()

    bf_rw = ttk.Frame(lf_pe)
    bf_rw.grid(row=4, column=0, sticky="ew", pady=(6, 0))
    ttk.Button(bf_rw, text="Add (browse)", command=add_rw).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(bf_rw, text="Remove", command=del_rw).pack(side=tk.LEFT)

    bf_ro = ttk.Frame(lf_pe)
    bf_ro.grid(row=4, column=1, sticky="ew", pady=(6, 0))
    ttk.Button(bf_ro, text="Add (browse)", command=add_ro).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(bf_ro, text="Remove", command=del_ro).pack(side=tk.LEFT)

    ttk.Label(lf_pe, text="Persisted escape grants").grid(row=5, column=0, columnspan=2, sticky="w", pady=(12, 0))
    lb_eg.grid(row=6, column=0, columnspan=2, sticky="ew")

    def del_eg() -> None:
        sel = lb_eg.curselection()
        if not sel:
            return
        p = lb_eg.get(sel[0])
        pf = load_permissions_file()
        pf.escape_grants = [x for x in pf.escape_grants if x != p]
        save_permissions_file(pf)
        reload_perm_lists()

    ttk.Button(lf_pe, text="Remove selected escape grant", command=del_eg).grid(
        row=7, column=1, sticky="e", pady=(6, 0)
    )

    def save_perm_file() -> None:
        pf = load_permissions_file()
        pf.network_mode = net_var.get().strip() or "ask"
        pf.sandbox_engine = sbox_var.get().strip() or "auto"
        save_permissions_file(pf)
        messagebox.showinfo("tlm", "Saved permissions.toml settings.")

    ttk.Button(lf_pe, text="Save network/sandbox", command=save_perm_file, style="Accent.TButton").grid(
        row=8, column=1, sticky="e", pady=(12, 0)
    )
    reload_perm_lists()

    foot = ttk.Frame(outer)
    foot.pack(fill=tk.X, pady=(10, 0))
    ttk.Separator(foot, orient=tk.HORIZONTAL).pack(fill=tk.X)
    ttk.Button(foot, text="Close", command=root.destroy).pack(anchor=tk.E, pady=(10, 0))

    root.mainloop()
