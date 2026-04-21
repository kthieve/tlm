"""Interactive terminal UI for `tlm config` (no extra dependencies)."""

from __future__ import annotations

import sys

from tlm.providers.registry import REAL_PROVIDER_IDS
from tlm.self_update import format_config_header_status, format_version_update_status
from tlm.settings import UserSettings, config_file_path, load_settings, merged_api_key, save_settings
from tlm.web.lightpanda_release import (
    RELEASES_PAGE,
    compare_status,
    describe_local_install,
    fetch_latest_release,
    install_latest_to_data_dir,
    preferred_asset_basename,
)


def _mask(s: str, keep: int = 4) -> str:
    if len(s) <= keep:
        return "(set)" if s else "(empty)"
    return s[:keep] + "…"


def _web_lightpanda_menu(s: UserSettings) -> bool:
    """Lightpanda / web submenu. Returns True if settings were changed."""
    dirty = False
    while True:
        print("\n--- Web / Lightpanda ---", flush=True)
        print(f"  web_enabled: {s.web_enabled}", flush=True)
        print(f"  lightpanda_path: {s.lightpanda_path or '(use PATH)'}", flush=True)
        print(f"  web_check_lightpanda_updates (GUI auto-check): {s.web_check_lightpanda_updates}", flush=True)
        print(f"  Local: {describe_local_install(s).replace(chr(10), ' / ')}", flush=True)
        print("  1) Edit flags / path", flush=True)
        print("  2) Check GitHub latest release (read-only)", flush=True)
        print("  3) Download latest binary to ~/.local/share/tlm/bin/lightpanda", flush=True)
        print(f"  4) Show releases URL ({RELEASES_PAGE})", flush=True)
        print("  0) Back to main menu", flush=True)
        try:
            sub = input("\nChoice [0-4]: ").strip().lower()
        except EOFError:
            return dirty
        if sub == "0":
            return dirty
        if sub == "1":
            v = input(f"web_enabled [y/N] ({s.web_enabled}): ").strip().lower()
            if v in ("y", "yes"):
                s.web_enabled = True
                dirty = True
            elif v in ("n", "no"):
                s.web_enabled = False
                dirty = True
            lp = input(
                f"lightpanda_path (empty = PATH only; current [{s.lightpanda_path or ''}]): "
            ).strip()
            if lp:
                s.lightpanda_path = lp
                dirty = True
            elif lp == "" and s.lightpanda_path:
                c = input("Clear lightpanda_path? [y/N]: ").strip().lower()
                if c in ("y", "yes"):
                    s.lightpanda_path = None
                    dirty = True
            ac = input(
                f"web_check_lightpanda_updates (GUI) [y/N] ({s.web_check_lightpanda_updates}): "
            ).strip().lower()
            if ac in ("y", "yes"):
                s.web_check_lightpanda_updates = True
                dirty = True
            elif ac in ("n", "no"):
                s.web_check_lightpanda_updates = False
                dirty = True
        elif sub == "2":
            want = preferred_asset_basename()
            if not want:
                print("No mapped asset for this OS/arch.", flush=True)
                continue
            ok, data = fetch_latest_release(timeout=15.0)
            if ok and isinstance(data, dict):
                print(compare_status(s, data), flush=True)
            else:
                print(f"error: {data}", flush=True)
        elif sub == "3":
            c = input(
                "Download ~120MB+ from GitHub into ~/.local/share/tlm/bin/lightpanda and set path? [y/N]: "
            ).strip().lower()
            if c not in ("y", "yes"):
                continue
            ok, msg, dest = install_latest_to_data_dir(s, timeout=120.0)
            print(msg if ok else f"error: {msg}", flush=True)
            if ok and dest:
                dirty = True
        elif sub == "4":
            print(RELEASES_PAGE, flush=True)
        else:
            print("Unknown choice.", file=sys.stderr)


def run_config_tui() -> int:
    s = load_settings()
    dirty = False
    all_ids = ["stub", *REAL_PROVIDER_IDS]

    while True:
        pid = (s.provider or "openrouter").strip()
        key = merged_api_key(pid, s) or ""
        print("\n=== tlm configuration (TUI) ===", flush=True)
        print(f"  {format_config_header_status(s)}", flush=True)
        print(f"  Config file: {config_file_path()}", flush=True)
        print(f"  1) provider          [{pid}]", flush=True)
        print(f"  2) default model      [{s.model or '(env / provider default)'}]", flush=True)
        print(f"  3) temperature        [{s.temperature}]", flush=True)
        print(f"  4) request timeout s  [{s.timeout}]", flush=True)
        print(f"  5) safety profile     [{s.safety_profile}]", flush=True)
        print(f"  6) API key ({pid})    [{_mask(key)}]", flush=True)
        print("  7) model override for current provider (per-provider)", flush=True)
        print(f"  m) memory enabled      [{s.memory_enabled}]", flush=True)
        print("  w) Web / Lightpanda (`tlm-web`, updates, install)", flush=True)
        print(f"     ready budget chars  [{s.memory_ready_budget_chars}]", flush=True)
        print(f"     auto-harvest every  [{s.memory_auto_harvest_threshold_messages}] msgs", flush=True)
        print(f"     harvest on switch   [{s.memory_harvest_on_switch}]", flush=True)
        print(f"  u) check GitHub updates [{s.check_for_updates}]  repo [{s.github_repo or '(auto)'}]", flush=True)
        print("  v) Version / tlm update status (queries GitHub if possible)", flush=True)
        print("  8) Save and exit", flush=True)
        print("  9) Exit without saving", flush=True)
        print("  g) Open GUI (`tlm config gui`)", flush=True)
        try:
            choice = input("\nChoice [1-9,m,w,u,g,v]: ").strip().lower()
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
        elif choice == "w":
            dirty = dirty or _web_lightpanda_menu(s)
        elif choice == "m":
            v = input(f"memory enabled [Y/n] ({s.memory_enabled}): ").strip().lower()
            if v in ("n", "no"):
                s.memory_enabled = False
                dirty = True
            elif v in ("y", "yes", ""):
                s.memory_enabled = True
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
        elif choice == "v":
            print("\n--- tlm version / update status ---", flush=True)
            print(format_version_update_status(s, query_github=True), flush=True)
            try:
                input("\nPress Enter to continue… ")
            except EOFError:
                pass
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
