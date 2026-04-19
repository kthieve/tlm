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

## Release **0.2.0b1** (beta, shipped in tree)

- Installer scripts (`scripts/install.sh`), zipapp (`packaging/build_zipapp.sh`), GitHub `release.yml`, CI `pip-audit` + soft-fail `mypy`.
- `permissions.toml`, freelist, jail classification, escape consent, root guard, optional `bwrap`/`firejail` for `tlm do`, log redaction, `tlm config migrate-keys`, GUI Permissions tab.

## Follow-ups (0.3.0+)

1. **`tlm ask --stream`** — Wire CLI to `OpenAICompatProvider.stream` (and stub).
2. **`tlm do` gate + `$EDITOR`** — Re-parse JSON after `e` so argv edits apply.
3. **Telemetry** — Expand `telemetry/prices.py`; optional GUI usage graphs.
4. **Packaging** — Activate Homebrew / Scoop / winget placeholders; optional `.deb` in CI.

---

## Later (post-0.2.0)

- Write-mode optional `$EDITOR` for raw JSON plan (currently `allow_edit=False`).
- Man page expansion (`docs/tlm.1` is minimal).
