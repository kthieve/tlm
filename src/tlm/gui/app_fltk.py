"""FLTK configuration UI (optional; install tlm[gui-fltk] + system FLTK)."""

from __future__ import annotations

import json

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


def run_gui_fltk() -> None:
    from fltk import (  # type: ignore[import-not-found]
        FL_SECRET_INPUT,
        FL_WHEN_CHANGED,
        Fl,
        Fl_Browser,
        Fl_Box,
        Fl_Button,
        Fl_Choice,
        Fl_Group,
        Fl_Input,
        Fl_Multiline_Input,
        Fl_Tabs,
        Fl_Window,
        fl_alert,
    )

    provider_ids = ["stub", *REAL_PROVIDER_IDS]

    class FltkConfig:
        def __init__(self) -> None:
            self.settings = load_settings()
            self.win = Fl_Window(720, 520, f"tlm — configuration ({__version__})")
            self.win.size_range(640, 400, 0, 0)
            self.win.begin()

            tabs = Fl_Tabs(8, 8, 704, 460)
            tabs.begin()

            # Keys
            gk = Fl_Group(8, 35, 704, 425, "Keys")
            gk.begin()
            Fl_Box(20, 55, 80, 24, "Provider")
            self.prov = Fl_Choice(110, 55, 260, 24)
            for pid in provider_ids:
                self.prov.add(pid)
            cur = (self.settings.provider or "openrouter").strip()
            try:
                self.prov.value(provider_ids.index(cur))
            except ValueError:
                self.prov.value(0)
            self.prov.callback(self._on_prov_change)
            self.prov.when(FL_WHEN_CHANGED)

            Fl_Box(20, 92, 80, 24, "API key")
            self.key_in = Fl_Input(110, 90, 560, 24)
            self.key_in.type(FL_SECRET_INPUT)

            bs = Fl_Button(400, 125, 90, 28, "Save")
            bs.callback(self._save_keys)
            bt = Fl_Button(500, 125, 160, 28, "Test connection")
            bt.callback(self._test_keys)
            gk.end()

            # Sessions
            gs = Fl_Group(8, 35, 704, 425, "Sessions")
            gs.begin()
            self.sess_browser = Fl_Browser(20, 55, 660, 170)
            self.sess_browser.callback(self._on_sess_pick)
            self.sess_browser.when(FL_WHEN_CHANGED)
            self.sess_json = Fl_Multiline_Input(20, 235, 660, 195)
            br = Fl_Button(580, 438, 100, 28, "Refresh")
            br.callback(self._refresh_sessions)
            gs.end()

            # Usage
            gu = Fl_Group(8, 35, 704, 425, "Usage")
            gu.begin()
            self.use_txt = Fl_Multiline_Input(20, 55, 660, 380)
            ur = Fl_Button(580, 445, 100, 28, "Refresh")
            ur.callback(self._refresh_usage)
            gu.end()

            # Logs
            gl = Fl_Group(8, 35, 704, 425, "Logs")
            gl.begin()
            self.log_txt = Fl_Multiline_Input(20, 55, 660, 380)
            lr = Fl_Button(580, 445, 100, 28, "Refresh")
            lr.callback(self._refresh_logs)
            gl.end()

            # Permissions
            gp = Fl_Group(8, 35, 704, 425, "Permissions")
            gp.begin()
            Fl_Box(20, 60, 120, 24, "Safety profile")
            self.prof = Fl_Choice(150, 58, 200, 24)
            for p in ("strict", "standard", "trusted"):
                self.prof.add(p)
            prof = load_settings().safety_profile
            try:
                self.prof.value(("strict", "standard", "trusted").index(prof))
            except ValueError:
                self.prof.value(1)
            ps = Fl_Button(150, 100, 100, 28, "Save")
            ps.callback(self._save_profile)
            gp.end()

            tabs.end()

            close = Fl_Button(620, 478, 90, 28, "Close")
            close.callback(self._close)

            self.win.end()

            self._refresh_sessions()
            self._refresh_usage()
            self._refresh_logs()
            self._load_key_for_provider()

            self.win.show()
            Fl.run()

        def _close(self, *_a: object) -> None:
            self.win.hide()
            Fl.quit()

        def _provider_id(self) -> str:
            i = int(self.prov.value())
            if 0 <= i < len(provider_ids):
                return provider_ids[i]
            return "openrouter"

        def _on_prov_change(self, *_a: object) -> None:
            self._load_key_for_provider()

        def _load_key_for_provider(self) -> None:
            pid = self._provider_id()
            s = load_settings()
            v = s.api_keys.get(pid, "") or _maybe_keyring_get(pid) or ""
            self.key_in.value(v)

        def _save_keys(self, *_a: object) -> None:
            s = load_settings()
            pid = self._provider_id()
            s.provider = pid
            if self.key_in.value().strip():
                s.api_keys[pid] = self.key_in.value().strip()
                _maybe_keyring_set(pid, self.key_in.value().strip())
            save_settings(s)
            fl_alert("tlm: Saved config.toml (and keyring if available).")

        def _test_keys(self, *_a: object) -> None:
            s = load_settings()
            s.provider = self._provider_id()
            if self.key_in.value().strip():
                s.api_keys[s.provider] = self.key_in.value().strip()
            try:
                p = get_provider(s.provider, settings=s)
                out = p.complete("Reply with the single word: ok", system="You are a connection test.")
                fl_alert(out[:400])
            except Exception as e:  # noqa: BLE001
                fl_alert(f"tlm: {e}")

        def _refresh_sessions(self, *_a: object) -> None:
            self.sess_browser.clear()
            for s in list_sessions():
                self.sess_browser.add(f"{s.id}\t{s.updated}\t{s.title}")
            self.sess_json.value("")

        def _on_sess_pick(self, *_a: object) -> None:
            line = int(self.sess_browser.value())
            if line < 1:
                return
            text = self.sess_browser.text(line)
            sid = text.split("\t", 1)[0].strip()
            sess = load_session(str(sid))
            if sess is None:
                self.sess_json.value("session not found")
                return
            self.sess_json.value(json.dumps(sess.to_json(), indent=2))

        def _refresh_usage(self, *_a: object) -> None:
            self.use_txt.value(summarize_usage(since_days=30))

        def _refresh_logs(self, *_a: object) -> None:
            p = requests_log_path()
            if not p.is_file():
                self.log_txt.value("(no requests log yet)")
                return
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            self.log_txt.value("\n".join(lines[-400:]))

        def _save_profile(self, *_a: object) -> None:
            s = load_settings()
            labels = ("strict", "standard", "trusted")
            i = int(self.prof.value())
            s.safety_profile = labels[i] if 0 <= i < 3 else "standard"
            save_settings(s)
            fl_alert("tlm: Saved safety profile.")

    FltkConfig()
