"""Interactive terminal UI for `tlm config` (no extra dependencies)."""

from __future__ import annotations

import sys

from tlm.providers.registry import REAL_PROVIDER_IDS
from tlm.settings import config_file_path, load_settings, merged_api_key, save_settings


def _mask(s: str, keep: int = 4) -> str:
    if len(s) <= keep:
        return "(set)" if s else "(empty)"
    return s[:keep] + "…"


def run_config_tui() -> int:
    s = load_settings()
    dirty = False
    all_ids = ["stub", *REAL_PROVIDER_IDS]

    while True:
        pid = (s.provider or "openrouter").strip()
        key = merged_api_key(pid, s) or ""
        print("\n=== tlm configuration (TUI) ===", flush=True)
        print(f"  Config file: {config_file_path()}", flush=True)
        print(f"  1) provider          [{pid}]", flush=True)
        print(f"  2) default model      [{s.model or '(env / provider default)'}]", flush=True)
        print(f"  3) temperature        [{s.temperature}]", flush=True)
        print(f"  4) request timeout s  [{s.timeout}]", flush=True)
        print(f"  5) safety profile     [{s.safety_profile}]", flush=True)
        print(f"  6) API key ({pid})    [{_mask(key)}]", flush=True)
        print("  7) model override for current provider (per-provider)", flush=True)
        print(f"  m) memory enabled      [{s.memory_enabled}]", flush=True)
        print(f"     ready budget chars  [{s.memory_ready_budget_chars}]", flush=True)
        print(f"     auto-harvest every  [{s.memory_auto_harvest_threshold_messages}] msgs", flush=True)
        print(f"     harvest on switch   [{s.memory_harvest_on_switch}]", flush=True)
        print(f"  u) check GitHub updates [{s.check_for_updates}]  repo [{s.github_repo or '(auto)'}]", flush=True)
        print("  8) Save and exit", flush=True)
        print("  9) Exit without saving", flush=True)
        print("  g) Open GUI (`tlm config gui`)", flush=True)
        try:
            choice = input("\nChoice [1-9,m,u,g]: ").strip().lower()
        except EOFError:
            print("\n(use 8 to save, 9 to quit)", file=sys.stderr)
            return 1

        if choice == "1":
            print("Providers:", ", ".join(all_ids))
            v = input(f"provider [{pid}]: ").strip()
            if v:
                s.provider = v
                dirty = True
        elif choice == "2":
            v = input(f"default model [{s.model or ''}]: ").strip()
            s.model = v or None
            dirty = True
        elif choice == "3":
            v = input(f"temperature [{s.temperature}]: ").strip()
            if v:
                try:
                    s.temperature = float(v)
                    dirty = True
                except ValueError:
                    print("invalid number", file=sys.stderr)
        elif choice == "4":
            v = input(f"timeout seconds [{s.timeout}]: ").strip()
            if v:
                try:
                    s.timeout = float(v)
                    dirty = True
                except ValueError:
                    print("invalid number", file=sys.stderr)
        elif choice == "5":
            v = input("safety profile [strict|standard|trusted]: ").strip().lower()
            if v in ("strict", "standard", "trusted"):
                s.safety_profile = v
                dirty = True
            elif v:
                print("unchanged (use strict, standard, or trusted)", file=sys.stderr)
        elif choice == "6":
            v = input("API key (empty to clear from config file; env still wins): ").strip()
            cur = (s.api_keys.get(pid) or s.api_keys.get(pid.replace("-", "_")) or "").strip()
            if v == "" and cur:
                s.api_keys.pop(pid, None)
                s.api_keys.pop(pid.replace("-", "_"), None)
                dirty = True
            elif v:
                s.api_keys[pid] = v
                dirty = True
        elif choice == "7":
            prov = input(f"provider id (default {pid}): ").strip() or pid
            m = input("model for that provider: ").strip()
            if m:
                s.models[prov] = m
                dirty = True
        elif choice == "m":
            v = input(f"memory enabled [y/N] (current {s.memory_enabled}): ").strip().lower()
            if v in ("y", "yes"):
                s.memory_enabled = True
                dirty = True
            elif v in ("n", "no"):
                s.memory_enabled = False
                dirty = True
            v2 = input(f"ready memory budget chars [{s.memory_ready_budget_chars}]: ").strip()
            if v2:
                try:
                    s.memory_ready_budget_chars = int(v2)
                    dirty = True
                except ValueError:
                    print("invalid int", file=sys.stderr)
            v3 = input(
                f"auto-harvest after N new messages [{s.memory_auto_harvest_threshold_messages}]: "
            ).strip()
            if v3:
                try:
                    s.memory_auto_harvest_threshold_messages = int(v3)
                    dirty = True
                except ValueError:
                    print("invalid int", file=sys.stderr)
            v4 = input(f"harvest previous session on switch [y/N] ({s.memory_harvest_on_switch}): ").strip().lower()
            if v4 in ("y", "yes"):
                s.memory_harvest_on_switch = True
                dirty = True
            elif v4 in ("n", "no"):
                s.memory_harvest_on_switch = False
                dirty = True
        elif choice == "u":
            v = input(f"notify on new GitHub releases [y/N] ({s.check_for_updates}): ").strip().lower()
            if v in ("y", "yes"):
                s.check_for_updates = True
                dirty = True
            elif v in ("n", "no"):
                s.check_for_updates = False
                dirty = True
            gr = input(
                f"github_repo owner/slug (empty = use install metadata / env) [{s.github_repo or ''}]: "
            ).strip()
            if gr:
                s.github_repo = gr
                dirty = True
            elif gr == "" and s.github_repo:
                c = input("Clear saved github_repo? [y/N]: ").strip().lower()
                if c in ("y", "yes"):
                    s.github_repo = None
                    dirty = True
        elif choice == "8":
            if dirty:
                save_settings(s)
                print("Saved.", flush=True)
            else:
                print("Nothing to save.", flush=True)
            return 0
        elif choice == "9":
            if dirty:
                c = input("Discard unsaved changes? [y/N]: ").strip().lower()
                if c not in ("y", "yes"):
                    continue
            return 1
        elif choice == "g":
            from tlm.cli import run_gui_safe

            run_gui_safe()
            s = load_settings()  # reload in case GUI changed file
            dirty = False
        else:
            print("Unknown choice.", file=sys.stderr)
