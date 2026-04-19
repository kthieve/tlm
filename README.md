# tlm

[![Python](https://img.shields.io/badge/python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat)](LICENSE)

**Terminal LLM helper for Linux** — ask questions in natural language, chat with **sessions**, use optional **read-only shell diagnostics** (you approve each command), and run **write** / **do** modes behind previews and confirmation. Works with OpenAI-compatible APIs and a small **Tk** (or optional **FLTK**) settings UI.

| | |
|:---|:---|
| **Version** | Declared in [`pyproject.toml`](pyproject.toml) (`[project].version`). Runtime: `tlm --version`. |
| **Runtime deps** | Pinned in [`requirements.txt`](requirements.txt) (kept aligned with `pyproject.toml`). |
| **Scope & features** | [Describe_Here.md](Describe_Here.md) — product form, core features, security notes. |
| **Command-oriented help** | [AGENTS.md](AGENTS.md) — quick command reference and paths. |
| **Man page** | [docs/tlm.1](docs/tlm.1) — `troff` manual (stub; mirrors CLI behavior). |

---

## Features

- **Ask** — `tlm`, `tlm ask …`, or `tlm ? …`; continues the last session by default; Rich markdown replies; optional `tlm-exec` tool loop (`tlm ask --no-tools` to disable).
- **Providers** — OpenAI-compatible HTTP client: OpenAI, DeepSeek, Chutes, OpenRouter, nano-gpt, plus offline `stub` (see `tlm providers`).
- **Sessions** — JSON sessions under XDG data; `tlm sessions` (TUI or list/show/delete/rename/resume), `tlm new`, memory harvest via `tlm harvest`.
- **Write mode** — `tlm write …` proposes file changes with preview and confirmation.
- **Do mode** — `tlm do …` runs planned argv lists with confirmation (no `shell=True` for untrusted input).
- **Safety** — Denylist / profiles / interactive gate (see `tlm/safety/`).
- **Telemetry** — JSONL request log; `tlm usage` for token/cost summaries.
- **GUI** — `tlm gui` / `tlm config gui` (`TLM_GUI=tk|fltk|auto`).
- **Shell completion** — `tlm completion bash|zsh|fish`.

More detail: [Describe_Here.md](Describe_Here.md) · Code map: [CODE_INDEX.md](CODE_INDEX.md)

---

## Install

```bash
cd /path/to/tlm
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

**Optional extras** (see [`pyproject.toml`](pyproject.toml) `[project.optional-dependencies]`):

| Extra | Purpose |
|-------|---------|
| `usage` | Better token counting (`tiktoken`) |
| `gui-fltk` | FLTK window UI (system FLTK / `fltk-config`) |
| `openai` | Official OpenAI client if needed |
| `dev` | `pytest`, `ruff`, `mypy` |

```bash
pip install -e ".[usage,dev]"
```

Window UI: `TLM_GUI=tk` (default when Tk is available), `TLM_GUI=fltk` after `[gui-fltk]`, or `TLM_GUI=auto`.

---

## Configuration

Set a provider and API key (examples):

```bash
export TLM_PROVIDER=openrouter   # or openai, deepseek, chutes, nano-gpt, stub
export TLM_API_KEY=sk-...
# e.g. OpenRouter-specific: export TLM_OPENROUTER_API_KEY=...
```

Initialize XDG dirs and default config:

```bash
tlm init
```

Persistent settings: `$XDG_CONFIG_HOME/tlm/config.toml` — use `tlm config` or the GUI. Sessions and request logs use XDG data/state (see `tlm init` output).

---

## Command cheat sheet

| Command | What it does |
|---------|----------------|
| `tlm` · `tlm help` | Print CLI help |
| `tlm --version` | Show version ([`pyproject.toml`](pyproject.toml)) |
| `tlm which cpu am i using` | Natural-language ask (same as `tlm ask …`) |
| `tlm ask …` · `tlm ? …` | Ask with `--session`, `--provider`, `--new`, `--budget`, `--no-tools`, … |
| `tlm write …` | Generate files (preview + confirm) |
| `tlm do …` | Planned commands (preview + confirm) |
| `tlm gui` · `tlm config gui` | Settings window |
| `tlm config` | Terminal settings UI |
| `tlm providers` | List providers, keys, models |
| `tlm sessions …` | Session TUI or list/show/delete/rename/resume |
| `tlm new` | New session (one-word name) |
| `tlm harvest` | Extract durable facts into long-term memory |
| `tlm usage` | Summarize usage from JSONL log |
| `tlm completion bash\|zsh\|fish` | Emit completion script |

Full narrative: [AGENTS.md](AGENTS.md) · Troff reference: [docs/tlm.1](docs/tlm.1)

---

## Documentation & help files

| Doc | Role |
|-----|------|
| [AGENTS.md](AGENTS.md) | Commands, XDG paths, contributor/agent notes |
| [Describe_Here.md](Describe_Here.md) | Product scope, core features, platform |
| [CODE_INDEX.md](CODE_INDEX.md) | Source file map |
| [docs/tlm.1](docs/tlm.1) | Man page source |
| [INIT.md](INIT.md) | Original scaffold instructions |
| [AI_INIT.md](AI_INIT.md) | Brownfield agent workflow |
| [AGENT_PLAN.md](AGENT_PLAN.md) | Implementation phases |
| [AGENT_TODO.md](AGENT_TODO.md) | Backlog items |

---

## Development sandbox

Isolated XDG under `sandbox/` so development does not touch your real `~/.config` / `~/.local`:

```bash
eval "$(python sandbox.py env)"
tlm init
python sandbox.py run tlm ask "hello"
python sandbox.py refresh    # reinstall; keeps API keys unless --wipe-keys
```

Details: [sandbox/README.md](sandbox/README.md)

---

## License

[MIT License](LICENSE)
