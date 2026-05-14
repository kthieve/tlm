from __future__ import annotations

import importlib
import sys
import tomllib
from pathlib import Path
from typing import Any

from tlm.config import abilities_dir
from tlm.plugins.base import AbilityMetadata, Extension


class ExtensionManager:
    """Discovers, loads, and dispatches hooks for tlm extensions."""

    def __init__(self, abilities_path: Path | None = None):
        self.extensions: list[Extension] = []
        self.abilities_path = abilities_path or abilities_dir()

    def discover(self) -> list[AbilityMetadata]:
        """Find all abilities with an ability.toml in the abilities directory."""
        abilities = []
        if not self.abilities_path.exists():
            return []

        for item in self.abilities_path.iterdir():
            if item.is_dir():
                toml_path = item / "ability.toml"
                if toml_path.exists():
                    try:
                        with open(toml_path, "rb") as f:
                            data = tomllib.load(f)
                            meta = AbilityMetadata(
                                name=data["name"],
                                version=data["version"],
                                description=data.get("description", ""),
                                entry_point=data["entry_point"],
                                runtime=data.get("runtime", "python"),
                                author=data.get("author"),
                                path=item,
                            )
                            abilities.append(meta)
                    except (KeyError, tomllib.TOMLDecodeError):
                        continue
        return abilities

    def load_extensions(self) -> None:
        """Load all discovered extensions into memory."""
        metas = self.discover()
        for meta in metas:
            if meta.path is None:
                continue

            try:
                # Add ability path to sys.path for dynamic loading
                if str(meta.path) not in sys.path:
                    sys.path.insert(0, str(meta.path))

                if ":" not in meta.entry_point:
                    raise ValueError(f"Invalid entry_point format: {meta.entry_point}")

                module_path, class_name = meta.entry_point.split(":")
                module = importlib.import_module(module_path)
                cls = getattr(module, class_name)

                if not issubclass(cls, Extension):
                    raise TypeError(f"{class_name} is not a subclass of Extension")

                ext = cls(meta)
                self.extensions.append(ext)
            except Exception as e:
                print(f"tlm: error loading extension '{meta.name}': {e}", file=sys.stderr)

    def dispatch_pre_ask(self, query: str, context: dict[str, Any]) -> str:
        """Run pre_ask hooks on all extensions."""
        current_query = query
        for ext in self.extensions:
            modified = ext.pre_ask(current_query, context)
            if modified is not None:
                current_query = modified
        return current_query

    def dispatch_post_ask(self, response: str, context: dict[str, Any]) -> str:
        """Run post_ask hooks on all extensions."""
        current_response = response
        for ext in self.extensions:
            modified = ext.post_ask(current_response, context)
            if modified is not None:
                current_response = modified
        return current_response
