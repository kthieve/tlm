"""Web backend selection and abstraction."""

from __future__ import annotations

import sys
import os
from tlm.settings import UserSettings
from tlm.web import lightpanda, playwright_backend

def resolve_web_backend(settings: UserSettings) -> str:
    """Return 'lightpanda' or 'playwright' based on config and platform."""
    pref = (settings.web_backend or "auto").lower().strip()
    
    if pref == "lightpanda":
        return "lightpanda"
    if pref == "playwright":
        return "playwright"
    
    # Auto selection
    if sys.platform == "win32":
        if playwright_backend.is_playwright_available():
            return "playwright"
        return "lightpanda"  # Might be in WSL or path
    
    # Linux/macOS
    lp = lightpanda.resolve_binary(settings)
    if lp:
        return "lightpanda"
    
    if playwright_backend.is_playwright_available():
        return "playwright"
        
    return "lightpanda"  # Default fallback

def build_run_fn(settings: UserSettings, backend: str | None = None) -> Callable[[list[str]], tuple[int, str]]:
    """Build the appropriate fetch callable for runner.py."""
    if backend is None:
        backend = resolve_web_backend(settings)
        
    if backend == "playwright":
        return playwright_backend.build_playwright_run_fn(settings)
    
    # Default to lightpanda subprocess runner
    from tlm.ask_tools import _run_argv
    lp_env = web_env(settings, backend="lightpanda")
    
    def lp_run(argv: list[str]) -> tuple[int, str]:
        from tlm.ask_tools import _run_argv
        try:
            # We use a large timeout because lightpanda internally handles its own timeout
            # and we want to capture its output even if it's slow.
            return _run_argv(argv, timeout=settings.timeout + 10, env=lp_env)
        except Exception as e:
            return -1, f"error: lightpanda execution failed: {e}"
            
    return lp_run

def web_env(settings: UserSettings, backend: str | None = None) -> dict[str, str]:
    """Environment variables for the active backend."""
    if backend is None:
        backend = resolve_web_backend(settings)
        
    env = os.environ.copy()
    if backend == "lightpanda":
        if settings.web_disable_lightpanda_telemetry:
            env["LIGHTPANDA_DISABLE_TELEMETRY"] = "true"
    return env

def describe_web_install(settings: UserSettings) -> str:
    """Human-readable status for the active/available backends."""
    backend = resolve_web_backend(settings)
    lp_status = lightpanda.resolve_binary(settings)
    pw_status = playwright_backend.is_playwright_available()
    
    lines = []
    if sys.platform == "win32":
        lines.append("Platform: Windows")
    else:
        lines.append(f"Platform: {sys.platform}")
        
    lines.append(f"Active Backend: {backend}")
    
    if lp_status:
        lines.append(f"Lightpanda: found at {lp_status}")
    else:
        lines.append("Lightpanda: not found on PATH")
        
    lines.append(playwright_backend.describe_playwright_install())
    
    return "\n".join(lines)
