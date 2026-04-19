# tlm

Linux terminal helper for talking to LLMs (OpenAI-compatible APIs), with optional **read-only shell tools** (you approve each command), **write** and **do** modes behind previews, sessions, and a small **Tk** (or optional **FLTK**) settings UI.

**Requires:** Python 3.11+

## Install

```bash
cd /path/to/tlm
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e .
```

Optional: `pip install -e ".[usage]"` for better token counting (`tiktoken`), `pip install -e ".[gui-fltk]"` for the FLTK window UI (needs OS FLTK dev files / `fltk-config`), or `pip install -e ".[dev]"` for tests and ruff.

Window UI backend: `TLM_GUI=tk` (default when `TLM_GUI=auto` and tkinter exists), `TLM_GUI=fltk` after installing `[gui-fltk]`, or `TLM_GUI=auto` to prefer Tk then FLTK.

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
| `tlm gui` / `tlm config gui` | Settings window (Tk or FLTK; see `TLM_GUI`) |
| `tlm config` | Terminal settings menu |
| `tlm sessions list` | List saved chats |
| `tlm providers` | Show providers and keys |

Persistent settings live in `$XDG_CONFIG_HOME/tlm/config.toml` (see `tlm config` or the GUI). Sessions and logs use XDG data/state dirs (`tlm init` prints paths).

## Development sandbox

Use the repo-root helper so config, sessions, and logs stay under `sandbox/`:

```bash
eval "$(python sandbox.py env)"   # bash/zsh
tlm init
# or one-shot:
python sandbox.py run tlm ask "hello"
```

After editing `src/`, refresh (reinstalls the package; **API keys in sandbox config are kept** unless you add `--wipe-keys`):

```bash
python sandbox.py refresh
```

See [sandbox/README.md](sandbox/README.md).

## Docs

- Agent / workflow notes: [AGENTS.md](AGENTS.md)
- Project scope form: [Describe_Here.md](Describe_Here.md)
- File map: [CODE_INDEX.md](CODE_INDEX.md)
