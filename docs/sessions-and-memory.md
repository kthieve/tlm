# Sessions and memory

Paths (see `tlm init`):

| Data | Location |
|------|----------|
| Session JSON | `$XDG_DATA_HOME/tlm/sessions/` |
| Ready + long-term memory | `$XDG_DATA_HOME/tlm/memory/` |

## Sessions

- **Last session** — Natural-language asks keep using the same session until you run `tlm new` or `tlm sessions resume SPEC` (keyword or UUID).
- **Keywords** — Each session has a one-word name (`[a-z0-9-]`). The first ask when no session exists yet picks a keyword via the model.
- **TUI** — `tlm sessions` (no subcommand) opens the interactive picker: resume by number, `d N` delete, `r N new title`, `n` new session, `h N` harvest, `q` quit.
- **Scripting** — `tlm sessions list`, `show`, `delete`, `rename`, `resume` accept a **SPEC** (keyword, full UUID, or unique prefix).

Examples:

```bash
tlm new work
tlm sessions
tlm sessions resume work
tlm ask --session work "follow-up question"
```

## Ready memory

Short bullet facts stored in `memory/ready.json`. They are **injected into the system prompt** on each `tlm ask` / natural-language ask unless you pass **`--clear-context`** or **`--fresh`** for that turn only.

Edit in **`tlm gui` → Memory** or **`tlm config`** (menu **`m`**) — options include `memory_enabled`, `memory_ready_budget_chars`, auto-harvest thresholds, and harvest-on-session-switch.

## Long-term memory

Stored as JSON lines in `memory/longterm.jsonl`. It is **not** auto-injected; the model can search it by emitting a fenced **`tlm-mem`** block whose body is JSON, for example:

```text
{"op": "search", "q": "short query"}
```

## Harvest

`tlm harvest` runs a small LLM pass over session messages to propose durable facts. Candidates are filtered (no API keys, tokens, private keys, etc. — see `tlm/memory.py`). A one-line summary may be appended to ready memory when items are stored.

```bash
tlm harvest              # last active session
tlm harvest work         # by keyword
tlm harvest --dry-run    # preview only
tlm harvest --yes        # store all safe items without prompting
tlm harvest --all        # every session
```

The sessions TUI (`h N`) and **GUI → Sessions → Harvest** offer the same idea with per-item confirmation where applicable.

## Storage rules (summary)

**Prefer:** OS/distro, hardware summary, shell/editor prefs, locale, volunteered project paths, workflow prefs, tool versions.

**Reject:** API keys, passwords, tokens, JWTs, private keys, high-entropy env-style secrets, URLs with embedded credentials.

Full rules text is shown in the GUI (**Memory** tab) and defined in `src/tlm/memory.py` (`STORAGE_RULES_TEXT`, `is_safe_to_store`).
