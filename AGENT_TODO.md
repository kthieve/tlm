# AGENT_TODO — next concrete tasks

- [ ] Implement OpenAI-compatible HTTP path (covers OpenRouter, DeepSeek API-compat, etc.).
- [ ] Add `tlm sessions` subcommand: list / show / delete JSON sessions.
- [ ] Wire `tlm do` to `subprocess.run` with timeout after interactive confirm.
- [ ] Wire `tlm write` to LLM → parse structured “files to write” → preview → confirm → write.
- [ ] Tk: tabs for Keys, Sessions, Usage (stub charts OK first).
- [ ] Tests: `check_command_line`, session round-trip, CLI smoke with `subprocess`.
- [ ] Align `VERSION` file with `pyproject.toml` / `tlm.__version__` (single source or bump script).
