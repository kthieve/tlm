# AGENT_PLAN — foundation → releases

## Phases 1–4 (in tree; pre-1.0 dev)

| Phase | Intent | Status |
|-------|--------|--------|
| **1 — Real LLM calls** | `OpenAICompatProvider` (httpx), env/config keys, clear HTTP errors | Done (`src/tlm/providers/openai_compat.py`, `registry.py`) |
| **2 — Sessions** | JSON sessions, trim, `tlm sessions …`, last-session pointer | Done (`session.py`, `cli.py`) |
| **3 — Write mode** | JSON plan, diff preview, atomic temp+rename | Done (`modes/write.py`; gate edit disabled by design) |
| **4 — Do mode** | argv JSON, denylist, gate, `subprocess.run` timeout, no `shell=True` | Done (`modes/do.py`, `safety/shell.py`) |

## Phase 5 — GUI (partial)

- **Done:** Keys (incl. optional keyring), session list + JSON view, usage summary text, request log tail, safety profile (`src/tlm/gui/app.py`).
- **Not done:** In-GUI chat, usage graphs, richer log redaction UX.

## Security (ongoing)

- Deny patterns + profiles: implemented (`safety/`).
- Stretch: stricter allowlist profile, consistent secret redaction in logs/GUI.

---

## Release **0.2.0** (next, dev line)

Focus: polish CLI parity with the provider layer, fix known gate gaps, improve cost visibility.

1. **`tlm ask --stream`** — Wire CLI to `OpenAICompatProvider.stream` (and stub). Multi-turn/tool loops need a defined story (e.g. stream only the final model reply, or add `stream_chat` on the provider when API supports it).
2. **`tlm do` gate + `$EDITOR`** — After `e`, re-run `extract_json_object` / `_parse_commands` on the edited buffer so argv changes apply (`do.py` currently notes this MVP gap).
3. **Telemetry** — Expand `telemetry/prices.py` for common default models / OpenRouter slugs; align `count_tokens` with model where practical (tiktoken already used in `openai_compat` when installed).
4. **GUI (optional for 0.2.0)** — Usage over time: simple matplotlib or text sparkline behind an extra (`usage` extra already in `pyproject.toml` pattern).
5. **Packaging** — deb/AUR only if release checklist demands it; can slip to 0.3.0.

---

## Later (post-0.2.0)

- Write-mode optional `$EDITOR` for raw JSON plan (currently `allow_edit=False`).
- Man page expansion (`docs/tlm.1` is minimal).
