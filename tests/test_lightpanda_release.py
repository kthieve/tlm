"""Lightpanda GitHub release helpers (no network by default)."""

from __future__ import annotations

import json
import threading
from unittest.mock import patch

from tlm.settings import UserSettings
from tlm.web.lightpanda_release import (
    download_release_binary,
    fetch_latest_release,
    pick_asset_download_url,
    preferred_asset_basename,
)


def test_preferred_asset_on_linux_x86() -> None:
    import sys

    with patch.object(sys, "platform", "linux"):
        with patch("tlm.web.lightpanda_release.platform.machine", return_value="x86_64"):
            assert preferred_asset_basename() == "lightpanda-x86_64-linux"


def test_pick_asset_download_url() -> None:
    release = {
        "tag_name": "nightly",
        "assets": [
            {
                "name": "lightpanda-x86_64-linux",
                "browser_download_url": (
                    "https://github.com/lightpanda-io/browser/releases/download/nightly/"
                    "lightpanda-x86_64-linux"
                ),
            }
        ],
    }
    url, tag = pick_asset_download_url(release, "lightpanda-x86_64-linux")
    assert tag == "nightly"
    assert url and "lightpanda-x86_64-linux" in url


def test_fetch_latest_release_mocked() -> None:
    payload = {"tag_name": "nightly", "assets": []}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def read(self):
            return json.dumps(payload).encode()

    with patch("tlm.web.lightpanda_release.urlopen", return_value=_Resp()):
        ok, data = fetch_latest_release(timeout=5.0)
    assert ok is True
    assert isinstance(data, dict)
    assert data.get("tag_name") == "nightly"


def test_download_release_binary_200(tmp_path, monkeypatch) -> None:
    from tlm.web import lightpanda_release as lr

    url = (
        "https://github.com/lightpanda-io/browser/releases/download/nightly/lightpanda-x86_64-linux"
    )
    dest = tmp_path / "lightpanda"
    body = b"x" * 5000
    prog: list[tuple[int, int | None]] = []

    class Resp:
        status = 200

        def __init__(self) -> None:
            self._b = body
            self.headers = {"Content-Length": str(len(body))}

        def read(self, n: int = -1) -> bytes:
            if not self._b:
                return b""
            if n is None or n < 0:
                out = self._b
                self._b = b""
                return out
            out = self._b[:n]
            self._b = self._b[n:]
            return out

        def close(self) -> None:
            return None

        def getcode(self) -> int:
            return self.status

    monkeypatch.setattr(lr, "urlopen", lambda *a, **k: Resp())

    ok, err = lr.download_release_binary(
        url, dest, timeout=5.0, progress=lambda n, t: prog.append((n, t))
    )
    assert ok is True
    assert err == ""
    assert dest.read_bytes() == body
    assert (dest.stat().st_mode & 0o777) == 0o755
    assert prog and prog[-1] == (len(body), len(body))


def test_download_release_binary_cancel(tmp_path, monkeypatch) -> None:
    from tlm.web import lightpanda_release as lr

    url = (
        "https://github.com/lightpanda-io/browser/releases/download/nightly/lightpanda-x86_64-linux"
    )
    dest = tmp_path / "lightpanda"
    cancel = threading.Event()
    cancel.set()

    class Resp:
        status = 200
        headers = {"Content-Length": "99999"}
        _b = b"abc"

        def read(self, n: int = -1) -> bytes:
            return b""

        def close(self) -> None:
            return None

        def getcode(self) -> int:
            return self.status

    monkeypatch.setattr(lr, "urlopen", lambda *a, **k: Resp())
    ok, err = lr.download_release_binary(url, dest, timeout=5.0, cancel_event=cancel)
    assert ok is False
    assert "cancelled" in err.lower()


def test_download_release_binary_resume_206(tmp_path, monkeypatch) -> None:
    from tlm.web import lightpanda_release as lr

    url = (
        "https://github.com/lightpanda-io/browser/releases/download/nightly/lightpanda-x86_64-linux"
    )
    dest = tmp_path / "lightpanda"
    part, marker = lr._partial_paths(dest)
    part.write_bytes(b"abc")
    marker.write_text(url, encoding="utf-8")
    tail = b"defghij"  # bytes 3..9 inclusive => 7 bytes, total 10

    class Resp:
        status = 206
        headers = {"Content-Range": "bytes 3-9/10", "Content-Length": str(len(tail))}

        def __init__(self) -> None:
            self._b = tail

        def read(self, n: int = -1) -> bytes:
            if not self._b:
                return b""
            if n is None or n < 0:
                out = self._b
                self._b = b""
                return out
            out = self._b[:n]
            self._b = self._b[n:]
            return out

        def close(self) -> None:
            return None

        def getcode(self) -> int:
            return self.status

    monkeypatch.setattr(lr, "urlopen", lambda *a, **k: Resp())
    ok, err = lr.download_release_binary(url, dest, timeout=5.0)
    assert ok is True
    assert dest.read_bytes() == b"abcdefghij"
    assert not marker.is_file()


def test_compare_status_uses_resolve(monkeypatch) -> None:
    from tlm.web import lightpanda_release as lr

    monkeypatch.setattr(lr, "resolve_binary", lambda _s: "/bin/lightpanda")
    monkeypatch.setattr(lr, "local_lightpanda_version", lambda _p: "lightpanda 0.0-test")
    s = UserSettings(web_enabled=True)
    text = lr.compare_status(s, {"tag_name": "nightly", "assets": []})
    assert "nightly" in text
    assert "/bin/lightpanda" in text
