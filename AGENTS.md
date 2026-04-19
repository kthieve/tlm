# Agent notes — tlm

## Product

- Linux CLI: natural questions, **write** mode (files/scripts), **do** mode (commands).
- Tk GUI for configuration, history, token usage, logs (mostly stubs today).
- LLM backends: openai, deepseek, chutes, openrouter, nano-gpt (stub provider until HTTP wiring).

## Rules

- **Never** auto-run shell commands or write files without the same interactive confirm flow the CLI uses (preview → user `y`).
- Extend `tlm/safety/shell.py` when adding execution; prefer `subprocess.run(..., shell=False)`, timeouts, and explicit argv lists.
- Session JSON lives under `XDG_DATA_HOME/tlm/sessions/` (see `tlm/config.py`).
- Canonical requirements: `requirements.txt` + `pyproject.toml` deps should stay aligned.

## Commands

- Editable install: `pip install -e .` from repo root (use project `.venv`).
- `tlm ? your question` or `tlm ask your question`
- `tlm write …`, `tlm do …`, `tlm gui`

## Docs

- Form / scope: `Describe_Here.md`
- File map: `CODE_INDEX.md`
- Backlog: `AGENT_TODO.md`, phases: `AGENT_PLAN.md`
