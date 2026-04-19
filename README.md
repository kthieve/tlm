# tlm

Linux terminal helper for talking to LLMs (OpenAI-compatible APIs), with optional **read-only shell tools** (you approve each command), **write** and **do** modes behind previews, sessions, and a small **Tk** settings UI.

**Requires:** Python 3.11+

## Install

```bash
cd /path/to/tlm
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e .
```

Optional: `pip install -e ".[usage]"` for better token counting (`tiktoken`), or `pip install -e ".[dev]"` for tests and ruff.

Set an API key, for example:

```bash
export TLM_PROVIDER=openrouter   # or openai, deepseek, chutes, nano-gpt, stub
export TLM_API_KEY=sk-...
# or: export TLM_OPENROUTER_API_KEY=...
```

First run:

```bash
tlm init
```

## Quick commands

| Command | What it does |
|--------|----------------|
| `tlm` | Print help |
| `tlm which ubuntu version am i on` | Ask the model (same as `tlm ask …`) |
| `tlm ask --last "follow-up"` | Continue last session |
| `tlm ask --no-tools "…"` | Ask without the shell-tool loop |
| `tlm write "…"` | Generate files (preview + confirm) |
| `tlm do "…"` | Planned commands (preview + confirm) |
| `tlm gui` / `tlm config gui` | Tk UI |
| `tlm config` | Terminal settings menu |
| `tlm sessions list` | List saved chats |
| `tlm providers` | Show providers and keys |

Persistent settings live in `$XDG_CONFIG_HOME/tlm/config.toml` (see `tlm config` or the GUI). Sessions and logs use XDG data/state dirs (`tlm init` prints paths).

## Docs

- Agent / workflow notes: [AGENTS.md](AGENTS.md)
- Project scope form: [Describe_Here.md](Describe_Here.md)
- File map: [CODE_INDEX.md](CODE_INDEX.md)
