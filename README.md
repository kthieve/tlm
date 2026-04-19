# tlm

[![Python](https://img.shields.io/badge/python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat)](LICENSE)

**tlm** is a **terminal-first LLM assistant** for Linux: ask questions in plain language, keep **sessions**, optionally let the model suggest **read-only shell checks** and **web fetches** (you approve each step), and use **write** / **do** modes when you want files or commands executed with previews. It talks to **OpenAI-compatible** HTTP APIs and includes a small **Tk** or **FLTK** settings window.

| | |
|:---|:---|
| **Install (all options)** | [docs/install.md](docs/install.md) |
| **Sessions & memory** | [docs/sessions-and-memory.md](docs/sessions-and-memory.md) |
| **Command & path reference** | [AGENTS.md](AGENTS.md) |
| **Doc index** | [docs/documentation.md](docs/documentation.md) |
| **Scope & security** | [Describe_Here.md](Describe_Here.md) |
| **Source map** | [CODE_INDEX.md](CODE_INDEX.md) |

---

## What it does

| Mode | What you get |
|:-----|:-------------|
| **Ask** | Chat with the model; answers render as **Rich markdown**. Same as typing a natural question after `tlm` with no subcommand. |
| **Tools (optional)** | The model may emit fenced blocks: **`tlm-exec`** (argv JSON — local diagnostics), **`tlm-mem`** (search your saved memory), **`tlm-web`** (fetch a URL or a simple DuckDuckGo search via [Lightpanda](https://github.com/lightpanda-io/browser)). Nothing runs until you confirm. |
| **Write** | Proposed file changes with preview and confirmation. |
| **Do** | Planned **`argv` lists** (no shell injection by default), preview, then `subprocess` with timeouts and safety checks. |
| **GUI** | `tlm gui` / `tlm config gui` — keys, sessions, usage, logs, permissions. Set `TLM_GUI` to `tk`, `fltk`, or `auto`. |

---

## Features at a glance

- **Sessions** — JSON chats under XDG data; `tlm sessions` (TUI), `tlm new`, resume by keyword or id; optional **harvest** into long-term memory.
- **Providers** — OpenAI-compatible: OpenAI, DeepSeek, Chutes, OpenRouter, nano-gpt, plus offline **`stub`** (`tlm providers`).
- **Safety** — Denylist and profiles; **`permissions.toml`** freelist and optional **`bwrap` / `firejail`** for `tlm do`; root guard; `tlm paths` / `allow` / `unallow`.
- **Telemetry** — Request log (JSONL); `tlm usage` for rough token/cost summaries.
- **Shell completion** — `tlm completion bash|zsh|fish`.
- **Optional keyring** — `tlm config migrate-keys` with the `[secure]` extra ([install.md](docs/install.md)).

---

## Quick start

1. **Python 3.11+** and an API key for your provider.

2. **Install** — **not on PyPI yet**; use a clone or a GitHub `git+https` URL ([docs/install.md](docs/install.md)):

   ```bash
   git clone https://github.com/kthieve/tlm.git && cd tlm
   python3 -m venv .venv && source .venv/bin/activate
   pip install -e .
   ```


3. **Configure and run:**

   ```bash
   export TLM_PROVIDER=openrouter    # or openai, deepseek, chutes, nano-gpt, stub
   export TLM_API_KEY=sk-...
   tlm init                             # creates XDG dirs + default config if needed
   tlm what is 2+2                      # natural ask; continues last session by default
   ```

   You can put provider and model in **`$XDG_CONFIG_HOME/tlm/config.toml`** instead of env vars (`tlm config` for the terminal editor).

---

## Installation (summary)

| Method | Command / note |
|:-------|:---------------|
| **Git clone** | `pip install -e .` in a venv (primary path until PyPI) |
| **GitHub only** | Set `TLM_GITHUB_REPO=owner/repo`, then `bash scripts/install.sh 0.2.0b2` or `pipx install "git+https://github.com/…/tlm.git@v0.2.0b2"` — see [install.md](docs/install.md) |
| **PyPI** | Planned; not published yet |

Release artifacts (wheel, sdist, zipapp) may still appear on GitHub Releases when you cut a tag; see the repo workflow.

---

## User guide

### Ask and tools

- **Natural language:** `tlm <your question>` — same as `tlm ask`.
- **Explicit:** `tlm ask "…"` or `tlm ? "…"` (flags: `--session`, `--provider`, `--new`, `--keyword`, `--budget`, `--clear-context`, `--no-tools`, `--no-web`).
- **`tlm-exec`** — model suggests a single argv array per block; you approve each command. Disable with **`--no-tools`**.
- **`tlm-web`** — needs `web_enabled = true` in config and the **Lightpanda** binary on `PATH` (or `lightpanda_path`). Disable with **`--no-web`**. No native Windows binary for Lightpanda — use **WSL** if needed.
- **`tlm-mem`** — read-only search over stored memory (when memory is enabled).

See [sessions-and-memory.md](docs/sessions-and-memory.md) for ready vs long-term memory and harvest.

### Write and do

- **`tlm write …`** — base directory, overwrite and dry-run flags; always confirm before writes.
- **`tlm do …`** — JSON plan of argv lists; network and path policies from **`permissions.toml`**; use `tlm paths` / `allow` / `unallow` to adjust the freelist.

### Configuration layout

| Path | Role |
|:-----|:-----|
| `$XDG_CONFIG_HOME/tlm/config.toml` | Provider, model, timeouts, memory, **web / Lightpanda** settings |
| `$XDG_CONFIG_HOME/tlm/permissions.toml` | Freelist, sandbox, network mode, escape grants |
| `$XDG_DATA_HOME/tlm/` | Sessions, memory |
| `$XDG_STATE_HOME/tlm/` | Logs (e.g. `requests.jsonl`) |

Run **`tlm init`** to create standard dirs and a starter config.

---

## Common commands

| Command | Purpose |
|:--------|:--------|
| `tlm help` | Full CLI help |
| `tlm ask …` / natural `tlm …` | Chat (default: continue last session) |
| `tlm write …` / `tlm do …` | Files / commands (with confirmation) |
| `tlm gui` | Settings UI |
| `tlm sessions` | Session TUI (also `list`, `resume`, `show`, …) |
| `tlm new` / `tlm harvest` | New session / promote lines to long-term memory |
| `tlm providers` / `tlm usage` | Provider list / usage summary |
| `tlm paths` / `tlm allow` / `tlm unallow` | Inspect or edit freelist paths |

Man page stub: [docs/tlm.1](docs/tlm.1).

---

## Development sandbox

```bash
eval "$(python sandbox.py env)"
tlm init
python sandbox.py run tlm ask "hello"
```

Details: [sandbox/README.md](sandbox/README.md).

---

## License

[Apache License 2.0](LICENSE)
