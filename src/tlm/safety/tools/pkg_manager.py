"""Modular wrapper for package managers (apt, dnf, etc.)."""

from __future__ import annotations

from typing import Sequence
from tlm.safety.tools.base import ToolWrapper


class PackageManagerWrapper(ToolWrapper):
    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def is_readonly(self, argv: Sequence[str]) -> bool:
        # Most package managers are read-only if it's 'search', 'list', 'show', etc.
        if len(argv) < 2:
            return False
        cmd = argv[1]
        return cmd in {"search", "list", "show", "info", "policy", "rdepends"}

    def validate(self, argv: Sequence[str]) -> tuple[bool, str | None]:
        # Enforce --dry-run for non-readonly commands in non-trusted tiers
        if not self.is_readonly(argv):
            if "--dry-run" not in argv and "-s" not in argv:
                return False, f"{self.name} requires --dry-run (or -s) for non-read-only operations"
        return True, None
