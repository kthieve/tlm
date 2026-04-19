"""Package version from installed metadata (pyproject [project].version)."""

from __future__ import annotations

try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:
    PackageNotFoundError = Exception  # type: ignore[misc,assignment]

    def version(_: str) -> str:  # type: ignore[no-redef]
        return "0.0.0"


def package_version() -> str:
    try:
        return version("tlm")
    except PackageNotFoundError:
        return "0.0.0"
