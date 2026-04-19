# AGENT_TODO — 0.2.0 and follow-ups

## 0.2.0 (priority)

- [ ] **`tlm ask --stream`** — CLI flag + `run_interactive_ask` path using `provider.stream` (define behavior with tool rounds / session history).
- [ ] **`tlm do` — structured re-parse after `e`** — If the user edits the preview in `$EDITOR`, extract JSON and replace `commands` before execution (`modes/do.py`; see comment near gate).
- [ ] **Pricing / tokens** — Grow `telemetry/prices.py` (OpenRouter full IDs, chutes/nano-gpt defaults); document unknown-model cost as `None` in `summarize_usage` / JSONL.
- [ ] **Ask UX polish** — Optional: Rich syntax highlighting for fenced code in `ask_tools.print_markdown`; ensure stderr/progress does not fight streaming.

## Backlog (after 0.2.0)

- [ ] **GUI:** Chat tab and usage graphs (matplotlib or canvas), redaction for keys in log viewer.
- [ ] **`tlm write`:** Optional gate edit + JSON re-parse (parity with `do`).
- [ ] **Packaging:** `.deb` / AUR when release-ready.
- [ ] **Man page:** Flesh out `docs/tlm.1` to match `tlm help` / README.
