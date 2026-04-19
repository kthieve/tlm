# CODE_INDEX — tlm

| Path | Role |
|------|------|
| `src/tlm/ask_tools.py` | Ask tool loop (`tlm-exec` blocks), Rich markdown + prompts |
| `src/tlm/cli.py` | argparse; `tlm ?`; init/config; natural-language ask; ask/write/do/gui/… |
| `src/tlm/tui_config.py` | `tlm config` interactive terminal editor |
| `src/tlm/config.py` | XDG paths, env keys, base URL / model env helpers |
| `src/tlm/settings.py` | `config.toml` load/save (`$XDG_CONFIG_HOME/tlm/`) |
| `src/tlm/_version.py` | `importlib.metadata` version lookup |
| `src/tlm/session.py` | Sessions JSON, trim, last-session pointer |
| `src/tlm/jsonutil.py` | Extract JSON from LLM output |
| `src/tlm/completion.py` | bash/zsh/fish completion snippets |
| `src/tlm/telemetry/log.py` | JSONL request log + rotation + `summarize_usage` |
| `src/tlm/telemetry/prices.py` | Rough USD/token pricing |
| `src/tlm/providers/base.py` | `LLMProvider` protocol (`complete`, `chat`, `stream`, `count_tokens`) |
| `src/tlm/providers/stub.py` | Offline stub |
| `src/tlm/providers/openai_compat.py` | OpenAI-compatible HTTP client |
| `src/tlm/providers/registry.py` | `get_provider`, `describe_providers`, `REAL_PROVIDER_IDS` |
| `src/tlm/modes/write.py` | `tlm write` — JSON files, diff, atomic write |
| `src/tlm/modes/do.py` | `tlm do` — JSON argv plans, gate, `subprocess.run` |
| `src/tlm/safety/shell.py` | Denylist + package-manager guard |
| `src/tlm/safety/profiles.py` | `strict` / `standard` / `trusted`, read-only detection |
| `src/tlm/safety/gate.py` | Interactive confirm + `$EDITOR` |
| `src/tlm/gui/app.py` | Tk: Keys, Sessions, Usage, Logs, Permissions |
| `docs/tlm.1` | Man page stub |
| `tests/` | pytest + ruff in CI |
| `pyproject.toml` | Packaging, extras `usage` / `dev`, pytest `pythonpath` |
| `requirements.txt` | Runtime pins (mirror `[project].dependencies`) |
| `Describe_Here.md` | Project form / requirements |
| `INIT.md` | Original scaffold tool instructions |
| `AI_INIT.md` | Brownfield agent workflow |
