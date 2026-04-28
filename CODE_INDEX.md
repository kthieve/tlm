# CODE_INDEX — tlm

| Path | Role |
|------|------|
| `src/tlm/ask_tools.py` | Ask loop: `tlm-exec`, `tlm-mem`, `tlm-web`, ready-memory system prompt |
| `src/tlm/web/lightpanda.py` | Lightpanda `fetch` argv, URL validation, DDG search URL |
| `src/tlm/cli.py` | argparse; `tlm ?`; `tlm models` (GET /v1/models); init/config; ask/write/do/gui/… |
| `src/tlm/tui_config.py` | `tlm config` interactive terminal editor |
| `src/tlm/config.py` | XDG paths, env keys, base URL / model env helpers |
| `src/tlm/settings.py` | `config.toml` load/save (`$XDG_CONFIG_HOME/tlm/`) |
| `src/tlm/_version.py` | `importlib.metadata` version lookup |
| `src/tlm/session.py` | Sessions JSON, keyword, resolve, trim, last-session pointer |
| `src/tlm/memory.py` | Ready + long-term memory, safety filters, search |
| `src/tlm/harvest.py` | Session → memory extraction, auto-harvest helper |
| `src/tlm/sessions_tui.py` | `tlm sessions` interactive terminal picker |
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
| `src/tlm/safety/shell.py` | Denylist + package-manager guard + network-tool policy |
| `src/tlm/safety/profiles.py` | `strict` / `standard` / `trusted`, read-only detection, `overlay_effective_policy` |
| `src/tlm/safety/gate.py` | Interactive confirm + `$EDITOR` |
| `src/tlm/safety/permissions.py` | `permissions.toml` freelist, per-project overrides |
| `src/tlm/safety/jail.py` | Path classification (freelist / jail / escape) |
| `src/tlm/safety/consent.py` | Jail-escape interactive consent |
| `src/tlm/safety/root_guard.py` | Root / elevation guard |
| `src/tlm/safety/sandbox.py` | Optional `bwrap` / `firejail` argv wrapper |
| `scripts/install.sh` | pipx / venv install from `git+https` (`TLM_GITHUB_REPO`) |
| `scripts/update-from-clone.sh` | `git pull` + editable reinstall into pipx / `tlm-venv` / `.venv` |
| `packaging/build_zipapp.sh` | Shiv zipapp → `dist/tlm.pyz` |
| `packaging/linux/deb/`, `packaging/linux/aur/` | Linux packaging scaffolding |
| `packaging/macos/homebrew/`, `packaging/windows/*` | Placeholders for 0.3.0 |
| `src/tlm/gui/app.py` | Tk: Keys, Sessions, Memory, Usage, Logs, Permissions |
| `docs/tlm.1` | Man page stub |
| `docs/install.md` | Install from git / GitHub; PyPI section for when published |
| `docs/sessions-and-memory.md` | Sessions, memory tiers, harvest |
| `docs/documentation.md` | Index of repo docs |
| `sandbox.py` | Dev sandbox: `sandboxes/<name>/` venv + XDG; `init`, `env` (POSIX/`--pwsh`), `refresh`, `run`, `shell` |
| `sandbox/README.md` | How to use the sandbox |
| `tests/` | pytest + ruff in CI |
| `pyproject.toml` | Packaging, extras `usage` / `dev`, pytest `pythonpath` |
| `requirements.txt` | Runtime pins (mirror `[project].dependencies`) |
| `Describe_Here.md` | Project form / requirements |
| `INIT.md` | Original scaffold tool instructions |
| `AI_INIT.md` | Brownfield agent workflow |
