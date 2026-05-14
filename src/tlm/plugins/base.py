from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AbilityMetadata:
    name: str
    version: str
    description: str
    entry_point: str  # format: "module:class_name"
    runtime: str = "python"
    author: str | None = None
    path: Path | None = None


class Extension(ABC):
    """Base class for all tlm extensions."""

    def __init__(self, metadata: AbilityMetadata):
        self.metadata = metadata

    def pre_ask(self, query: str, context: dict[str, Any]) -> str | None:
        """
        Executed before the model is called in ask mode.
        Returns a modified query or None to keep original.
        """
        return None

    def post_ask(self, response: str, context: dict[str, Any]) -> str | None:
        """
        Executed after the model returns a response in ask mode.
        Returns a modified response or None to keep original.
        """
        return None

    def register_providers(self) -> list[Any]:
        """Return a list of provider instances to register."""
        return []

    def register_commands(self, parser: Any) -> None:
        """
        Register custom subcommands with the main tlm parser.
        'parser' is typically an argparse._SubParsersAction.
        """
        pass
