# tlm Abilities (Plugins)

Abilities are non-destructive extensions that allow you to grow `tlm`'s features without modifying the core source code. They can modify queries, intercept responses, and add new providers or commands.

## Directory Structure

Abilities are loaded from `$XDG_DATA_HOME/tlm/abilities/`. Each ability resides in its own subdirectory:

```text
~/.local/share/tlm/abilities/
└── my-greet-ability/
    ├── ability.toml
    └── main.py
```

### `ability.toml`

The metadata file defines how `tlm` loads the plugin.

```toml
name = "greet-plugin"
version = "1.0.0"
description = "Prefixes 'Hello' to every query."
entry_point = "main:GreetExtension"
author = "Dev"
```

*   `entry_point`: Format is `module_name:ClassName`. `tlm` will add the ability directory to `sys.path`.

## The Extension Class

Your plugin must inherit from `tlm.plugins.base.Extension`.

```python
from tlm.plugins.base import Extension
from typing import Any

class GreetExtension(Extension):
    def pre_ask(self, query: str, context: dict[str, Any]) -> str | None:
        """Executed before the model is called in ask mode."""
        return f"User says: {query}"

    def post_ask(self, response: str, context: dict[str, Any]) -> str | None:
        """Executed after the model returns a response."""
        return f"{response}\n\n-- Processed by GreetPlugin"
```

## Hook Points

| Hook | Purpose |
| :--- | :--- |
| `pre_ask(query, context)` | Modify the query string before it reaches the LLM. |
| `post_ask(response, context)` | Modify the response string before it is displayed. |
| `register_providers()` | Return a list of `LLMProvider` instances to add to the registry. |
| `register_commands(parser)` | Use the `argparse` subparser to add new CLI commands. |

## Enabling/Disabling

Plugins are controlled via `tlm config` or directly in `config.toml`:

```toml
extension_enabled = true
```

If `extension_enabled` is `false`, no plugins will be discovered or loaded.
