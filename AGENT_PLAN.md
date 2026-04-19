# AGENT_PLAN — foundation → MVP

## Phase 1 — Real LLM calls

- Replace `StubProvider` with httpx-based clients per vendor (unified message schema).
- Env vars: `TLM_PROVIDER`, `TLM_API_KEY` or `TLM_<PROVIDER>_API_KEY`, model overrides.
- Errors: surface HTTP status and rate limits clearly.

## Phase 2 — Sessions and context

- Thread last N messages + optional system prompt; session list CLI (`tlm sessions`).
- GUI: load/switch sessions, search history.

## Phase 3 — Write mode

- Plan: proposed paths, file contents, executable bit — all in preview.
- Confirm once per batch; write atomically (temp + rename).

## Phase 4 — Do mode

- After denylist: run with timeout, capture stdout/stderr, optional cwd allowlist.
- Never `shell=True` for untrusted strings.

## Phase 5 — GUI

- API key entry (masked), provider picker, token/cost estimates, matplotlib or canvas graphs for usage over time.

## Security (cross-cutting)

- Expand deny patterns (`rm -rf /`, privilege escalation, credential exfil).
- Optional command allowlist profile for paranoid installs.
- Log redaction for keys in GUI and file logs.
