"""Unified web browser installer (Lightpanda or Playwright)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from tlm.settings import UserSettings
from tlm.web import lightpanda_release, playwright_backend

def install_web_browser(
    settings: UserSettings,
    *,
    backend: str,
    timeout: float = 600.0,
    cancel_event: threading.Event | None = None,
    progress: Callable[[int, int | None], None] | None = None,
    text_progress: Callable[[str], None] | None = None,
) -> tuple[bool, str, Path | None]:
    """
    Dispatch to the appropriate browser installer.
    Returns (ok, message, path_if_ok).
    """
    if backend == "playwright":
        if not playwright_backend.is_playwright_available():
            return False, "Playwright package not installed. Run `pip install tlm[web]` first.", None
        
        from tlm.config import browsers_dir
        ok, msg = playwright_backend.install_chromium(progress_cb=text_progress)
        return ok, msg, browsers_dir() if ok else None
    
    # Lightpanda
    return lightpanda_release.install_latest_to_data_dir(
        settings,
        timeout=timeout,
        cancel_event=cancel_event,
        progress=progress
    )

def describe_web_browser_status(settings: UserSettings) -> str:
    """Detailed multi-backend status."""
    from tlm.web import backend as backend_mod
    return backend_mod.describe_web_install(settings)
