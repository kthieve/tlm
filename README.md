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
- **Safety** — Denylist / profiles / freelist (`permissions.toml`) / optional `bwrap`/`firejail` for `tlm do` / root guard (see `tlm/safety/`).
- **Telemetry** — JSONL request log; `tlm usage` for token/cost summaries.
- **GUI** — `tlm gui` / `tlm config gui` (`TLM_GUI=tk|fltk|auto`).
- **Shell completion** — `tlm completion bash|zsh|fish`.

More detail: [Describe_Here.md](Describe_Here.md) · Code map: [CODE_INDEX.md](CODE_INDEX.md)

---

## Install

**From PyPI (when published)** — isolated CLI:

```bash
pipx install "tlm==0.2.0b1"
# or
pip install --user "tlm==0.2.0b1"
```

**From GitHub** — use the installer script (prefer downloading it, verify the SHA256 from the release, then run `bash install.sh 0.2.0b1`). Avoid unchecked `curl … | bash` pipelines.

```bash
# After verifying the script checksum from the release page:
bash scripts/install.sh 0.2.0b1
```

**From a git clone** (development):

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
| `secure` | Keyring helpers (`tlm config migrate-keys`) |
| `dev` | `pytest`, `ruff`, `mypy`, `pip-audit` |

```bash
pip install -e ".[usage,dev]"
```

Release artifacts: GitHub Releases may include wheels, sdist, `tlm.pyz` zipapp, and checksums (see `.github/workflows/release.yml`).

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

Persistent settings: `$XDG_CONFIG_HOME/tlm/config.toml` — use `tlm config` or the GUI. **Permissions / freelist** for `tlm do` sandboxing: `$XDG_CONFIG_HOME/tlm/permissions.toml` (also editable in **GUI → Permissions**; CLI: `tlm paths`, `tlm allow`, `tlm unallow`). Sessions live in `$XDG_DATA_HOME/tlm/sessions/`; **memory** (ready + long-term) in `$XDG_DATA_HOME/tlm/memory/`. Request logs: `$XDG_STATE_HOME/tlm/requests.jsonl` (see `tlm init` output).

### Sessions & memory

- **Last session** — Natural-language asks keep using the same session until `tlm new` or `tlm sessions resume SPEC` (keyword or id).
- **Keywords** — One-word names per session; the first ask after no prior session picks a keyword via the model.
- **Ready memory** — Short facts auto-injected into the ask system prompt; skip for one turn with `tlm ask --clear-context` (`--fresh`). Edit in **`tlm gui` → Memory** or `tlm config` → `m`.
- **Long-term memory** — Searchable JSONL store; in chat the model can emit a fenced **`tlm-mem`** block with JSON like `{"op": "search", "q": "short query"}`.

- **Harvest** — `tlm harvest` (or the sessions TUI / GUI) proposes tiny summaries; lines matching secret patterns are dropped. Use `--dry-run` to preview.

---

## Command cheat sheet

| Command | What it does |
|---------|----------------|
| `tlm` · `tlm help` | Print CLI help |
| `tlm --version` | Show version ([`pyproject.toml`](pyproject.toml)) |
| `tlm which cpu am i using` | Natural-language ask (same as `tlm ask …`) |
| `tlm ask …` · `tlm ? …` | Ask with `--session SPEC`, `--provider`, `--new`/`--keyword`, `--clear-context`, `--budget`, `--no-tools`, … |
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
| `tlm paths` | Show freelist paths from `permissions.toml` |
| `tlm allow` / `tlm unallow` | Add/remove RW or read-only freelist entries |
| `tlm config migrate-keys` | Move API keys from config to OS keyring (`[secure]`) |

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
