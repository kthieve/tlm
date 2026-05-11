# GEMINI.md - Project Context & Instructions

## Project Overview
`tlm` is a **terminal-first LLM assistant** designed primarily for Linux. It provides a natural language interface to various LLM providers (OpenAI-compatible) and supports specialized modes for file modification and command execution with human-in-the-loop safety.

### Main Technologies
- **Language:** Python 3.11+
- **CLI Framework:** `argparse` (via `src/tlm/cli.py`)
- **UI/Formatting:** `rich` for terminal output, `pyfltk` or `Tkinter` for optional GUI settings.
- **Networking:** `httpx` for API calls.
- **Sandbox/Safety:** `bubblewrap` (`bwrap`) or `firejail` (optional) for command execution isolation.
- **Web Fetching:** `lightpanda` (optional) for headless browsing.

### Key Features
- **Ask/Chat:** Persistent sessions with Markdown rendering.
- **Tools:** Model-suggested shell checks (`tlm-exec`), memory search (`tlm-mem`), and web fetches (`tlm-web`).
- **Write Mode:** Managed file changes with diff previews.
- **Do Mode:** Guarded command execution based on `permissions.toml`.
- **Sessions & Memory:** Local JSON storage for chat history and long-term memory "harvesting".
- **GUI:** `tlm gui` for configuration, usage tracking, and log management.

## Building and Running

### Development Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,openai,usage,gui-fltk,secure]"
```

### Running the CLI
```bash
# Initialize configuration
tlm init

# Ask a question (uses default provider/model)
tlm "how do I list files by size in bash?"

# Run with a specific provider
TLM_PROVIDER=openai tlm ask "hello"
```

### Testing
```bash
# Run all tests
pytest

# Run tests with specific markers (e.g., skip GUI tests)
pytest -m "not gui"
```

### Linting and Type Checking
```bash
# Format and lint
ruff check .
ruff format .

# Type checking
mypy
```

## Agile Engineering Methodology

We employ a strict, iterative 7-phase Agile loop (Plan, Build, Test, Document, QC, Report, Polish).
For detailed instructions on each phase, see **[`.cursor/plans/AGILE.md`](.cursor/plans/AGILE.md)**.

### The Planning Shard System
To ensure forward compatibility, we use **Planning Shards** (`.cursor/plans/shards/`). 
- If current development has implications for a future feature or version, leave a shard to document the contract.
- See the [Shard Ledger](.cursor/plans/shards/SHARD_LEDGER.md) for pending requirements.

### The AI Codex (CODE_INDEX.md)
`CODE_INDEX.md` is our **AI Codex**. It is the primary navigation tool for AI agents and developers. Always update it during the **Document** phase.

## Development Conventions

### Code Style
- **Formatting:** Handled by `ruff`. Line length is set to 100.
- **Imports:** `from __future__ import annotations` is preferred for modern type hinting.
- **Naming:** Follow standard PEP 8 conventions.

### Architecture & Patterns
- **CLI Entrypoint:** `src/tlm/cli.py` handles subcommand dispatch and natural language passthrough.
- **Providers:** Abstracted in `src/tlm/providers/`. New providers should implement the base class in `base.py`.
- **Modes:** Specialized logic for `write` and `do` resides in `src/tlm/modes/`.
- **Safety:** Permissions, sandboxing, and redacting sensitive info are managed in `src/tlm/safety/` and `src/tlm/telemetry/log.py`.
- **Configuration:** Managed via `src/tlm/settings.py` and `src/tlm/config.py`, respecting XDG base directory specifications.

### Testing Practices
- **Test Location:** All tests are in the `tests/` directory.
- **Mocking:** API calls and file system operations should be mocked using `pytest` fixtures or `unittest.mock`.
- **Coverage:** Aim for high coverage in core logic (providers, sessions, safety gates).

## Key Files & Directories
- `src/tlm/`: Core package source.
- `src/tlm/cli.py`: Main CLI entry point.
- `src/tlm/session.py`: Session management logic.
- `src/tlm/settings.py`: User settings and config loading.
- `src/tlm/providers/`: LLM provider implementations.
- `src/tlm/safety/`: Security gates and sandboxing logic.
- `permissions.toml`: (Generated) Defines the freelist for allowed paths and commands.
- `AGENT_PLAN.md`: Tracks development phases and upcoming features.
- `CODE_INDEX.md`: A map of the codebase for quick navigation.
