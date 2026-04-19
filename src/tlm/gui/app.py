"""Tkinter configuration UI (API keys, history, logs) — skeleton."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from tlm import __version__
from tlm.providers.registry import list_provider_ids


def run_gui() -> None:
    root = tk.Tk()
    root.title(f"tlm — configuration ({__version__})")
    root.minsize(480, 320)

    frm = ttk.Frame(root, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)

    ttk.Label(frm, text="tlm configuration", font=("TkDefaultFont", 14, "bold")).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(
        frm,
        text="Providers: " + ", ".join(list_provider_ids()),
        wraplength=440,
    ).grid(row=1, column=0, sticky="w", pady=(8, 0))

    ttk.Label(
        frm,
        text="Next: chat history, keys, token graphs, request log — see AGENT_TODO.md.",
        wraplength=440,
    ).grid(row=2, column=0, sticky="w", pady=(12, 0))

    ttk.Button(frm, text="Close", command=root.destroy).grid(row=3, column=0, sticky="e", pady=16)

    root.mainloop()
