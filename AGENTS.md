# Agent notes — tlm

## Product

- Linux CLI: natural questions, **write** mode (files/scripts), **do** mode (commands).
- Tk GUI for configuration, history, token usage, logs (mostly stubs today).
- LLM backends: openai, deepseek, chutes, openrouter, nano-gpt (`OpenAICompatProvider` + `stub`).

## Rules

- **Never** auto-run shell commands or write files without the same interactive confirm flow the CLI uses (preview → user `y`).
- Extend `tlm/safety/shell.py` when adding execution; prefer `subprocess.run(..., shell=False)`, timeouts, and explicit argv lists (`tlm/modes/do.py`).
- Session JSON lives under `XDG_DATA_HOME/tlm/sessions/`; request log JSONL under `XDG_STATE_HOME/tlm/requests.jsonl`.
- User config: `XDG_CONFIG_HOME/tlm/config.toml` (`tlm/settings.py`). Optional: `pipx install .` for isolated CLI installs.
- Canonical requirements: `requirements.txt` + `pyproject.toml` deps should stay aligned.

## Commands

- Editable install: `pip install -e .` from repo root (use project `.venv`).
- `tlm` (no args) or `tlm help` prints help; natural ask: `tlm which version of ubuntu and what cpu am i using` (same as `tlm ask …`). Replies use Rich markdown; the model may propose read-only shell commands in fenced `tlm-exec` JSON blocks — you approve each run; `tlm ask --no-tools` disables that loop.
- `tlm ? your question` or `tlm ask your question`
- `tlm init` — create XDG dirs + default `config.toml` if missing
- `tlm config` — terminal settings UI; `tlm config gui` or `tlm gui` for Tk
- `tlm write …`, `tlm do …`
- `tlm providers`, `tlm sessions …`, `tlm usage`, `tlm completion bash|zsh|fish`

## Docs

- Form / scope: `Describe_Here.md`
- File map: `CODE_INDEX.md`
- Backlog: `AGENT_TODO.md`, phases: `AGENT_PLAN.md`
