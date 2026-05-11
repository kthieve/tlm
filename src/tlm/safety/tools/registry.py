"""Registry for modular system tool wrappers."""

from __future__ import annotations

from typing import Dict, Sequence
from tlm.safety.tools.base import ToolWrapper

_REGISTRY: Dict[str, ToolWrapper] = {}


def register_tool(tool: ToolWrapper) -> None:
    _REGISTRY[tool.name] = tool


def get_tool_wrapper(name: str) -> ToolWrapper | None:
    return _REGISTRY.get(name)


def is_known_tool(name: str) -> bool:
    return name in _REGISTRY


def check_readonly(argv: Sequence[str]) -> bool | None:
    """Check if a command is read-only using the registry. Returns None if tool unknown."""
    if not argv:
        return None
    name = argv[0].split("/")[-1]
    wrapper = get_tool_wrapper(name)
    if wrapper:
        return wrapper.is_readonly(argv)
    return None
