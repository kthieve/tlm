"""FLTK configuration UI (optional; install tlm[gui-fltk] + system FLTK)."""

from __future__ import annotations

import json
import threading
import webbrowser

from tlm import __version__
from tlm.self_update import format_version_update_status
from tlm.memory import STORAGE_RULES_TEXT, iter_longterm, load_ready, save_ready
from tlm.providers.registry import REAL_PROVIDER_IDS, get_provider
from tlm.session import list_sessions, load_session, write_last_session_id
from tlm.settings import load_settings, save_settings
from tlm.web.lightpanda_release import (
    RELEASES_PAGE,
    compare_status,
    describe_local_install,
    fetch_latest_release,
    install_latest_to_data_dir,
    preferred_asset_basename,
)
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
        FL_ALIGN_LEFT,
        FL_ALIGN_TOP,
        FL_SECRET_INPUT,
        FL_WHEN_CHANGED,
        Fl,
        Fl_Browser,
        Fl_Box,
        Fl_Button,
        Fl_Check_Button,
        Fl_Choice,
        Fl_Double_Window,
        Fl_Group,
        Fl_Input,
        Fl_Multiline_Input,
        Fl_Progress,
        Fl_Tabs,
        Fl_Window,
        fl_alert,
        fl_choice,
    )

    provider_ids = ["stub", *REAL_PROVIDER_IDS]

    class FltkConfig:
        def __init__(self) -> None:
            self.settings = load_settings()
            self.win = Fl_Window(720, 520, f"tlm — configuration ({__version__})")
            self.win.size_range(640, 400, 0, 0)
            self.win.begin()

            tabs = Fl_Tabs(8, 8, 704, 460)
            tabs.when(FL_WHEN_CHANGED)
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

            # Web / Lightpanda
            gw = Fl_Group(8, 35, 704, 425, "Web / Lightpanda")
            self._gw_web = gw
            gw.begin()
            self.web_en = Fl_Check_Button(20, 52, 380, 22, "web_enabled (ask / tlm-web)")
            self.web_en.value(1 if self.settings.web_enabled else 0)
            Fl_Box(20, 78, 120, 22, "lightpanda path")
            self.lp_path_in = Fl_Input(140, 76, 530, 22)
            self.lp_path_in.value(self.settings.lightpanda_path or "")
            self.lp_auto = Fl_Check_Button(20, 104, 420, 22, "Auto-check GitHub when opening this tab")
            self.lp_auto.value(1 if self.settings.web_check_lightpanda_updates else 0)
            Fl_Box(20, 132, 200, 18, "Status (Refresh queries GitHub)")
            self.lp_status = Fl_Multiline_Input(20, 152, 660, 230)
            self.lp_status.value("")
            bw1 = Fl_Button(20, 392, 110, 28, "Save web")
            bw1.callback(self._save_web_fltk)
            bw2 = Fl_Button(140, 392, 100, 28, "Refresh")
            bw2.callback(self._refresh_lp_fltk)
            bw3 = Fl_Button(250, 392, 160, 28, "Download binary")
            bw3.callback(self._download_lp_fltk)
            bw4 = Fl_Button(420, 392, 140, 28, "Open releases")
            bw4.callback(self._open_lp_releases)
            gw.end()

            # Sessions
            gs = Fl_Group(8, 35, 704, 425, "Sessions")
            gs.begin()
            self.sess_browser = Fl_Browser(20, 55, 660, 170)
            self.sess_browser.callback(self._on_sess_pick)
            self.sess_browser.when(FL_WHEN_CHANGED)
            self.sess_json = Fl_Multiline_Input(20, 235, 660, 195)
            br = Fl_Button(580, 438, 100, 28, "Refresh")
            br.callback(self._refresh_sessions)
            bres = Fl_Button(460, 438, 110, 28, "Set active")
            bres.callback(self._sess_resume)
            gs.end()

            # Memory (view/edit ready + list long-term; rules text)
            gm = Fl_Group(8, 35, 704, 425, "Memory")
            gm.begin()
            Fl_Box(20, 55, 660, 20, "Rules (see README); ready memory = short injected facts")
            self.mem_rules = Fl_Multiline_Input(20, 78, 660, 72)
            self.mem_rules.value(STORAGE_RULES_TEXT)
            Fl_Box(20, 155, 200, 20, "Ready (one line per fact)")
            self.mem_ready = Fl_Multiline_Input(20, 178, 660, 90)
            Fl_Box(20, 275, 200, 20, "Long-term (read-only list)")
            self.mem_lt = Fl_Browser(20, 298, 660, 100)
            bm = Fl_Button(480, 408, 100, 28, "Save ready")
            bm.callback(self._save_ready_fltk)
            bmr = Fl_Button(590, 408, 90, 28, "Refresh")
            bmr.callback(self._refresh_memory_fltk)
            gm.end()

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

            # About / version & tlm GitHub update status
            gabout = Fl_Group(8, 35, 704, 425, "About")
            self._gw_about = gabout
            gabout.begin()
            Fl_Box(20, 52, 660, 22, "Version, install kind, and latest GitHub tag (Refresh queries the network).")
            self.about_txt = Fl_Multiline_Input(20, 78, 660, 320)
            ba = Fl_Button(20, 408, 300, 28, "Refresh (query GitHub)")
            ba.callback(self._refresh_about_fltk)
            gabout.end()

            tabs.end()

            close = Fl_Button(620, 478, 90, 28, "Close")
            close.callback(self._close)

            self.win.end()

            self._refresh_sessions()
            self._refresh_memory_fltk()
            self._refresh_usage()
            self._refresh_logs()
            self._load_key_for_provider()

            self._tabs = tabs
            tabs.callback(self._on_tabs_fltk)
            self._about_fill(False)
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

        def _save_web_fltk(self, *_a: object) -> None:
            s = load_settings()
            s.web_enabled = bool(int(self.web_en.value()))
            lp = self.lp_path_in.value().strip()
            s.lightpanda_path = lp if lp else None
            s.web_check_lightpanda_updates = bool(int(self.lp_auto.value()))
            save_settings(s)
            fl_alert("tlm: Saved web settings.")

        def _refresh_lp_fltk(self, *_a: object) -> None:
            s = load_settings()
            s.web_enabled = bool(int(self.web_en.value()))
            s.lightpanda_path = self.lp_path_in.value().strip() or None
            lines = [describe_local_install(s), ""]
            want = preferred_asset_basename()
            if not want:
                lines.append("No mapped GitHub asset for this platform.")
            else:
                ok, data = fetch_latest_release(timeout=15.0)
                if ok and isinstance(data, dict):
                    lines.append(compare_status(s, data))
                else:
                    lines.append(f"GitHub error: {data}")
            self.lp_status.value("\n".join(lines))

        def _download_lp_fltk(self, *_a: object) -> None:
            if fl_choice(
                "Download latest Lightpanda for this OS into ~/.local/share/tlm/bin ?",
                "OK",
                "Cancel",
                None,
            ) != 0:
                return

            cancel_ev = threading.Event()
            state: dict[str, object] = {
                "done": False,
                "err": None,
                "result": None,
                "got": 0,
                "tot": None,
            }

            def _fmt_b(n: int) -> str:
                if n < 1024:
                    return f"{n} B"
                if n < 1024 * 1024:
                    return f"{n / 1024:.1f} KiB"
                return f"{n / (1024 * 1024):.1f} MiB"

            def prog_cb(n: int, t: int | None) -> None:
                state["got"], state["tot"] = n, t

            def worker() -> None:
                try:
                    s = load_settings()
                    s.web_enabled = bool(int(self.web_en.value()))
                    s.lightpanda_path = self.lp_path_in.value().strip() or None
                    state["result"] = install_latest_to_data_dir(
                        s,
                        timeout=600.0,
                        cancel_event=cancel_ev,
                        progress=prog_cb,
                    )
                except BaseException as e:  # noqa: BLE001
                    state["err"] = e
                finally:
                    state["done"] = True

            win_dl = Fl_Double_Window(460, 168, "tlm — downloading Lightpanda")
            win_dl.set_modal()
            bx = Fl_Box(20, 10, 420, 36, "")
            bx.align(FL_ALIGN_LEFT | FL_ALIGN_TOP)
            pr = Fl_Progress(20, 52, 420, 22)
            pr.minimum(1.0)
            pr.maximum(0.0)
            Fl_Box(20, 78, 420, 28, "Partial download resumes next time (same URL). Cancel keeps .partial.")
            bc = Fl_Button(320, 118, 120, 28, "Cancel")

            def on_cancel(*_a: object) -> None:
                cancel_ev.set()
                bx.label("Cancelling…")

            bc.callback(on_cancel)
            win_dl.end()

            def poll_cb(*_args: object) -> None:
                if not state["done"]:
                    got = int(state["got"] or 0)
                    tot = state["tot"]
                    if tot and int(tot) > 0:
                        pr.minimum(0.0)
                        pr.maximum(100.0)
                        pr.value(min(100.0, 100.0 * got / int(tot)))
                    else:
                        pr.minimum(1.0)
                        pr.maximum(0.0)
                    tlab = _fmt_b(int(tot)) if tot else "…"
                    bx.label(f"{_fmt_b(got)} / {tlab}")
                    Fl.repeat_timeout(0.08, poll_cb)
                    return
                win_dl.hide()
                err = state["err"]
                if err is not None:
                    fl_alert(f"tlm: Download failed: {err}")
                    return
                raw = state["result"]
                if not isinstance(raw, tuple) or len(raw) != 3:
                    fl_alert("tlm: Download finished with no result (unexpected).")
                    return
                ok, msg, dest = raw
                if ok and dest:
                    self.lp_path_in.value(str(dest))
                    self._save_web_fltk()
                    self._refresh_lp_fltk()
                    fl_alert(msg)
                elif "cancelled" in str(msg).lower():
                    fl_alert(f"tlm: {msg}")
                else:
                    fl_alert(f"tlm: {msg}")

            threading.Thread(target=worker, daemon=True).start()
            win_dl.show()
            Fl.add_timeout(0.08, poll_cb)

        def _open_lp_releases(self, *_a: object) -> None:
            webbrowser.open(RELEASES_PAGE)

        def _on_tabs_fltk(self, *_a: object) -> None:
            try:
                g = self._tabs
                if g.value() == self._gw_web and bool(int(self.lp_auto.value())):
                    self._refresh_lp_fltk()
                if g.value() == self._gw_about:
                    self._about_fill(False)
            except (TypeError, ValueError, AttributeError):
                pass

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
                self.sess_browser.add(f"{s.keyword}\t{s.id}\t{s.updated}\t{s.title}")
            self.sess_json.value("")

        def _sess_resume(self, *_a: object) -> None:
            line = int(self.sess_browser.value())
            if line < 1:
                return
            text = self.sess_browser.text(line)
            parts = text.split("\t")
            sid = parts[1].strip() if len(parts) > 1 else parts[0].strip()
            write_last_session_id(sid)
            fl_alert("tlm: Active session updated.")

        def _refresh_memory_fltk(self, *_a: object) -> None:
            self.mem_ready.value("\n".join(load_ready()))
            self.mem_lt.clear()
            for e in iter_longterm():
                self.mem_lt.add(f"{e.text[:120]}\t{','.join(e.tags)}\t{e.id}")

        def _save_ready_fltk(self, *_a: object) -> None:
            st = load_settings()
            lines = [ln.strip() for ln in self.mem_ready.value().splitlines() if ln.strip()]
            from tlm.memory import is_safe_to_store

            for ln in lines:
                if not is_safe_to_store(ln)[0]:
                    fl_alert(f"tlm: unsafe line rejected: {ln[:80]}")
                    return
            save_ready(lines, budget_chars=st.memory_ready_budget_chars)
            fl_alert("tlm: Saved ready memory.")

        def _on_sess_pick(self, *_a: object) -> None:
            line = int(self.sess_browser.value())
            if line < 1:
                return
            text = self.sess_browser.text(line)
            parts = text.split("\t")
            sid = parts[1].strip() if len(parts) > 1 else parts[0].strip()
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

        def _about_fill(self, online: bool) -> None:
            self.about_txt.value(format_version_update_status(load_settings(), query_github=online))

        def _refresh_about_fltk(self, *_a: object) -> None:
            self._about_fill(True)

    FltkConfig()
