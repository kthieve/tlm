# Agent notes — tlm

## Product

- Linux CLI: natural questions, **write** mode (files/scripts), **do** mode (commands).
- Tk GUI for configuration, history, token usage, logs (mostly stubs today).
- LLM backends: openai, deepseek, chutes, openrouter, nano-gpt (`OpenAICompatProvider` + `stub`).

## Rules

- **Never** auto-run shell commands or write files without the same interactive confirm flow the CLI uses (preview → user `y`).
- Extend `tlm/safety/shell.py` when adding execution; prefer `subprocess.run(..., shell=False)`, timeouts, and explicit argv lists (`tlm/modes/do.py`).
- Session JSON lives under `XDG_DATA_HOME/tlm/sessions/`; ready/long-term memory under `XDG_DATA_HOME/tlm/memory/` (never store API keys or secrets — see `tlm/memory.py` rules); request log JSONL under `XDG_STATE_HOME/tlm/requests.jsonl`.
- User config: `XDG_CONFIG_HOME/tlm/config.toml` (`tlm/settings.py`); permissions / freelist: `XDG_CONFIG_HOME/tlm/permissions.toml` (`tlm/safety/permissions.py`). **Web in ask:** `web_enabled = true` plus the **lightpanda** binary (`lightpanda_path` optional) — set via `tlm init --wizard`, `tlm config` (TUI `w`), or **GUI** Keys tab. Install: from git / GitHub URL until PyPI (`docs/install.md`).
- Canonical requirements: `requirements.txt` + `pyproject.toml` deps should stay aligned.
- **Versioning:** Use **`.devN`** for development (`0.2.0.dev1`, …) and **`bN`** for beta (`0.2.0b4`, …), per PEP 440. On substantive changes: bump **`dev`** in `VERSION` (Dev line) + `pyproject.toml` + `requirements.txt` comment. When cutting a **beta**, bump **`bN`** in `VERSION` (Beta line), set `pyproject.toml` to that beta, and add `CHANGELOG.md`. Runtime `tlm --version` reads installed metadata (`pyproject.toml`).

## Commands

- Editable install: `pip install -e .` from repo root (use project `.venv`). Dev sandbox: `python sandbox.py` (see `sandbox/README.md`) — **`sandboxes/<name>/`** with `.venv` + isolated XDG; `init`, `env` (bash / `--pwsh` / `--posix`), `run`, `shell`, `refresh` (keeps `[keys]` unless `--wipe-keys`; `--recreate-venv` optional).
- `tlm` (no args) or `tlm help` prints help; natural ask: `tlm which version of ubuntu and what cpu am i using` (same as `tlm ask …`). Replies use Rich markdown; the model may propose read-only shell commands in fenced `tlm-exec` JSON blocks — you approve each run; `tlm ask --no-tools` disables that loop. With `web_enabled` and the [Lightpanda](https://github.com/lightpanda-io/browser) binary, ask mode can use fenced `tlm-web` blocks (fetch URL or simple DDG search); `tlm ask --no-web` disables that loop.
- `tlm ? your question` or `tlm ask your question`; `tlm web …` — same as ask but emphasizes `tlm-web` (Lightpanda)
- `tlm init` — create XDG dirs + default `config.toml` if missing
- `tlm config` — terminal settings UI; `tlm config gui` or `tlm gui` for Tk
- `tlm write …`, `tlm do …`
- `tlm providers`, `tlm sessions` (TUI) / `tlm sessions list|resume|…`, `tlm new`, `tlm harvest`, `tlm usage`, `tlm completion bash|zsh|fish`
- `tlm paths`, `tlm allow`, `tlm unallow` — freelist in `permissions.toml`; `tlm config migrate-keys` (optional `[secure]` / keyring)

## Docs

- Form / scope: `Describe_Here.md`
- Sessions & memory: `docs/sessions-and-memory.md`
- Install options: `docs/install.md`
- Doc index: `docs/documentation.md`
- File map: `CODE_INDEX.md`
- Backlog: `AGENT_TODO.md`, phases: `AGENT_PLAN.md`
