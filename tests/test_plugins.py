import sys
import tempfile
from pathlib import Path
from tlm.plugins.manager import ExtensionManager


def test_discovery_and_loading():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        plugin_dir = tmp_path / "hello_plugin"
        plugin_dir.mkdir()

        # Create ability.toml
        (plugin_dir / "ability.toml").write_text(
            'name = "hello"\n'
            'version = "0.1.0"\n'
            'entry_point = "main:HelloExtension"\n',
            encoding="utf-8",
        )

        # Create main.py
        (plugin_dir / "main.py").write_text(
            "from tlm.plugins.base import Extension\n"
            "class HelloExtension(Extension):\n"
            "    def pre_ask(self, query, context):\n"
            '        return f"HELLO {query}"\n',
            encoding="utf-8",
        )

        manager = ExtensionManager(abilities_path=tmp_path)
        abilities = manager.discover()
        assert len(abilities) == 1
        assert abilities[0].name == "hello"

        # Load it
        manager.load_extensions()
        assert len(manager.extensions) == 1

        # Test hook dispatch
        modified_query = manager.dispatch_pre_ask("world", {})
        assert modified_query == "HELLO world"

        # Test post_ask default (None returns original)
        assert manager.dispatch_post_ask("echo", {}) == "echo"
