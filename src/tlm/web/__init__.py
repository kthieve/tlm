"""Optional web fetch helpers (Lightpanda CLI)."""

from tlm.web.lightpanda import (
    build_fetch_argv,
    resolve_binary,
    search_url_for_query,
    validate_url,
)
from tlm.web.backend import resolve_web_backend, build_run_fn, web_env

__all__ = [
    "build_fetch_argv",
    "resolve_binary",
    "search_url_for_query",
    "validate_url",
    "resolve_web_backend",
    "build_run_fn",
    "web_env",
]
