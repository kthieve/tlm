"""First-run interactive setup wizard (linear prompts)."""

from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

from tlm.config import data_dir, sessions_dir, state_dir
from tlm.providers.openai_compat import DEFAULT_MODELS
from tlm.providers.registry import list_provider_ids, normalize_provider_id
from tlm.settings import (
    UserSettings,
    config_dir,
    config_file_path,
    load_settings,
    merged_api_key,
    save_settings,
)

SETUP_VERSION = 1


def setup_marker_path() -> Path:
    return data_dir() / "setup_complete.json"


def is_setup_complete() -> bool:
    p = setup_marker_path()
    if not p.is_file():
        return False
    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return False
        return int(data.get("version", 0)) >= SETUP_VERSION
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return False


def write_setup_marker() -> None:
    p = setup_marker_path()
    p.write_text(json.dumps({"version": SETUP_VERSION}) + "\n", encoding="utf-8")


def ensure_xdg_dirs() -> None:
    config_dir()
    data_dir()
    sessions_dir()
    state_dir()


def _eof() -> None:
    print("\n(error: end of input; run `tlm init --wizard` with a TTY to finish setup.)", file=sys.stderr)


def _provider_prompt_value(raw: str, all_ids: list[str]) -> str | None:
    v = raw.strip()
    if not v:
        return None
    if v.isdigit():
        idx = int(v)
        if 1 <= idx <= len(all_ids):
            return all_ids[idx - 1]
        return None
    pid = normalize_provider_id(v)
    if pid in all_ids:
        return pid
    return None


def _print_provider_menu(all_ids: list[str], selected: str | None = None) -> None:
    for i, pid in enumerate(all_ids, start=1):
        marker = " (selected)" if selected == pid else ""
        print(f"  {i}) {pid}{marker}")


def run_setup_wizard(settings: UserSettings) -> tuple[UserSettings | None, int]:
    """
    Linear setup prompts. On success, saves settings and writes the setup marker.
    Returns (updated settings or None, exit code). None + 1 means aborted (EOF).
    """
    if not sys.stdin.isatty():
        print("error: setup wizard needs an interactive terminal (TTY).", file=sys.stderr)
        print("hint: run `tlm init --wizard` in a terminal.", file=sys.stderr)
        return None, 2

    s = deepcopy(settings)
    cfg = config_file_path()
    all_ids = list_provider_ids()
    print("\n=== tlm setup ===", flush=True)
    print(f"Config file: {cfg}", flush=True)
    print("Answer prompts below; Enter accepts [bracketed] defaults.\n", flush=True)

    try:
        cur = (s.provider or "openrouter").strip()
        default_pid = normalize_provider_id(cur)
        if default_pid not in all_ids:
            default_pid = "openrouter"
        print("Providers (choose number or provider id):")
        _print_provider_menu(all_ids, selected=default_pid)
        v = input(f"Active provider [{default_pid}]: ").strip()
        chosen = _provider_prompt_value(v, all_ids)
        if v and chosen is None:
            print("error: unknown provider selection. Use a menu number or provider id.", file=sys.stderr)
            return None, 2
        pid = chosen or default_pid
        s.provider = pid

        print("\nAPI key setup (you can configure multiple providers).", flush=True)
        print("Pick a provider number to add/update a key, or press Enter when done.", flush=True)
        while True:
            _print_provider_menu(all_ids, selected=s.provider)
            raw_sel = input("Provider for API key [Enter to continue]: ").strip()
            if not raw_sel:
                break
            key_pid = _provider_prompt_value(raw_sel, all_ids)
            if key_pid is None:
                print("Invalid selection. Use menu number or provider id.", flush=True)
                continue
            if key_pid == "stub":
                print("Provider `stub` needs no API key.", flush=True)
                continue
            key = input(f"API key for {key_pid} (leave empty to skip): ").strip()
            if key:
                s.api_keys[key_pid] = key
                print(f"Saved key for {key_pid}.", flush=True)

        suggested = DEFAULT_MODELS.get(pid, "gpt-4o-mini")
        dm = s.model or suggested
        mv = input(f"Default model [{dm}]: ").strip()
        if mv:
            s.model = mv

        sp = (s.safety_profile or "standard").strip().lower()
        if sp not in ("strict", "standard", "trusted"):
            sp = "standard"
        v5 = input(f"Safety profile strict|standard|trusted [{sp}]: ").strip().lower()
        if v5 in ("strict", "standard", "trusted"):
            s.safety_profile = v5
        else:
            s.safety_profile = sp

        mem = "y" if s.memory_enabled else "n"
        v6 = input(f"Enable ready/long-term memory features? [Y/n] ({mem}): ").strip().lower()
        if v6 in ("n", "no"):
            s.memory_enabled = False
        elif v6 in ("y", "yes", ""):
            s.memory_enabled = True

        webdef = "y" if s.web_enabled else "n"
        print(
            "\nWeb in ask mode: model can use fenced `tlm-web` blocks (search/fetch) via the "
            "**Lightpanda** browser CLI — install from https://github.com/lightpanda-io/browser",
            flush=True,
        )
        v7 = input(f"Enable web tools (`web_enabled`)? [y/N] (current: {webdef}): ").strip().lower()
        if v7 in ("y", "yes"):
            s.web_enabled = True
        elif v7 in ("n", "no"):
            s.web_enabled = False
        # Enter alone: leave s.web_enabled unchanged
        if s.web_enabled:
            cur_lp = (s.lightpanda_path or "").strip()
            v_lp = input(
                f"Path to `lightpanda` binary (Enter = search PATH; current [{cur_lp or 'PATH'}]): "
            ).strip()
            if v_lp:
                s.lightpanda_path = v_lp
            vac = input(
                "In the config GUI, auto-check Lightpanda on GitHub when opening the Web tab? [y/N]: "
            ).strip().lower()
            if vac in ("y", "yes"):
                s.web_check_lightpanda_updates = True
            elif vac in ("n", "no"):
                s.web_check_lightpanda_updates = False

        print("\n--- summary ---", flush=True)
        print(f"  provider:        {s.provider}", flush=True)
        print(f"  model:           {s.model or '(provider default)'}", flush=True)
        print(f"  safety_profile:  {s.safety_profile}", flush=True)
        print(f"  memory_enabled:  {s.memory_enabled}", flush=True)
        print(f"  web_enabled:     {s.web_enabled}", flush=True)
        if s.lightpanda_path:
            print(f"  lightpanda_path: {s.lightpanda_path}", flush=True)
        if s.web_enabled:
            print(f"  web_check_lightpanda_updates: {s.web_check_lightpanda_updates}", flush=True)
        key_ok = bool(merged_api_key(normalize_provider_id((s.provider or "openrouter").strip()), s))
        print(f"  API key set:     {key_ok}", flush=True)

        c = input("\nSave this configuration? [Y/n]: ").strip().lower()
        if c in ("n", "no"):
            print("Not saved. You can run `tlm init --wizard` or `tlm config` later.", flush=True)
            return load_settings(), 0

        save_settings(s)
        write_setup_marker()
        print(f"Saved {cfg}", flush=True)
        return s, 0
    except EOFError:
        _eof()
        return None, 1


def maybe_first_run_wizard() -> UserSettings:
    """If first-run setup has not been completed, run the wizard (TTY, non-CI only)."""
    if is_setup_complete():
        return load_settings()
    if os.environ.get("CI") or os.environ.get("DEBIAN_FRONTEND") == "noninteractive":
        return load_settings()
    if not sys.stdin.isatty():
        return load_settings()

    ensure_xdg_dirs()
    if not config_file_path().is_file():
        save_settings(UserSettings(provider="openrouter", safety_profile="standard"))

    s0 = load_settings()
    out, code = run_setup_wizard(s0)
    if code != 0 or out is None:
        return load_settings()
    return load_settings()
