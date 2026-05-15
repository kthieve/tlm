"""Playwright-based web fetch backend for Windows and cross-platform fallback."""

from __future__ import annotations

import sys
import os
import subprocess
from typing import Callable

from tlm.settings import UserSettings
from tlm.config import browsers_dir

# Lazy imports for playwright to avoid startup delay when not used
_pw_sync = None
_md = None

def _ensure_pw():
    global _pw_sync
    if _pw_sync is None:
        from playwright.sync_api import sync_playwright
        _pw_sync = sync_playwright

def _ensure_md():
    global _md
    if _md is None:
        from markdownify import markdownify
        _md = markdownify

def is_playwright_available() -> bool:
    try:
        import playwright
        import markdownify
        return True
    except ImportError:
        return False

def is_chromium_installed() -> bool:
    if not is_playwright_available():
        return False
    
    # Check if Chromium executable exists in our portable browsers_dir
    b_dir = browsers_dir()
    # Playwright usually creates a subdirectory like 'chromium-1123'
    # We check if anything is in browsers_dir
    if not any(b_dir.iterdir()):
        return False
        
    return True

def install_chromium(progress_cb: Callable[[str], None] | None = None) -> tuple[bool, str]:
    if progress_cb:
        progress_cb("Installing Chromium into tlm data directory (this may take a few minutes)...")
    try:
        # We set PLAYWRIGHT_BROWSERS_PATH to our portable directory
        env = os.environ.copy()
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_dir())
        
        proc = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            check=False,
            env=env
        )
        if proc.returncode == 0:
            return True, f"Chromium installed successfully to {browsers_dir()}."
        return False, f"Installation failed (code {proc.returncode}): {proc.stderr}"
    except Exception as e:
        return False, f"Installation error: {e}"

def playwright_fetch(
    url: str,
    *,
    dump: str = "markdown",
    timeout_ms: int = 30000,
    user_agent: str | None = None,
) -> tuple[int, str]:
    """Fetch URL and return (exit_code, body)."""
    if not is_playwright_available():
        return 1, "error: playwright or markdownify not installed. Run `pip install tlm[web]`."

    _ensure_pw()
    _ensure_md()

    try:
        # Ensure Playwright looks in our portable directory
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_dir())
        
        with _pw_sync() as p:
            browser = p.chromium.launch(headless=True)
            context_args = {}
            if user_agent:
                context_args["user_agent"] = user_agent
            
            context = browser.new_context(**context_args)
            page = context.new_page()
            
            try:
                page.goto(url, timeout=timeout_ms)
                # Wait for load state to be sure
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception as e:
                # If networkidle fails, we still try to get what we have
                pass

            html = page.content()
            browser.close()

            if dump == "markdown":
                body = _md(html)
            else:
                body = html
            
            return 0, body
    except Exception as e:
        return 1, f"error: playwright fetch failed: {e}"

def build_playwright_run_fn(settings: UserSettings) -> Callable[[list[str]], tuple[int, str]]:
    """Return a RunArgvFn-compatible callable for runner.py."""
    def run_fn(argv: list[str]) -> tuple[int, str]:
        # runner.py passes argv=[binary, 'fetch', ..., url]
        # We extract the URL from the last element
        if not argv or len(argv) < 1:
            return 1, "error: empty argv"
        url = argv[-1]
        
        dump = "markdown"
        if "--dump" in argv:
            idx = argv.index("--dump")
            if idx + 1 < len(argv):
                dump = argv[idx + 1]

        timeout_ms = int(settings.timeout * 1000)
        ua = settings.web_user_agent
        
        return playwright_fetch(url, dump=dump, timeout_ms=timeout_ms, user_agent=ua)
    
    return run_fn

def describe_playwright_install() -> str:
    if not is_playwright_available():
        return "Playwright: not installed (`pip install tlm[web]`)"
    
    b_dir = browsers_dir()
    if is_chromium_installed():
        return f"Playwright: Chromium installed in {b_dir}"
    return f"Playwright: ready (Chromium not found in {b_dir})"
