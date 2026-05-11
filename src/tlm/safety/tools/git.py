"""Modular wrapper for the 'git' command."""

from __future__ import annotations

from typing import Sequence
from tlm.safety.tools.base import ToolWrapper


class GitWrapper(ToolWrapper):
    @property
    def name(self) -> str:
        return "git"

    def is_readonly(self, argv: Sequence[str]) -> bool:
        if len(argv) < 2:
            return False
        # Common read-only git subcommands
        return argv[1] in {
            "status",
            "diff",
            "log",
            "show",
            "branch",
            "remote",
            "ls-files",
            "rev-parse",
            "tag",
            "describe",
        }

    def validate(self, argv: Sequence[str]) -> tuple[bool, str | None]:
        # Potential future validation: block destructive commands if not in Trusted tier
        return True, None
