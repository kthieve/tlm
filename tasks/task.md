# Task: v0.3.0 Foundation (Safety & Streams)

## Sprint 1: Harden Snapshot & Undo
- [x] Rewrite `src/tlm/safety/snapshot.py` (non-destructive `git stash create`)
- [x] Implement `list_snapshots()` and `restore_snapshot()` with stash apply
- [x] Add non-git fallback (copytree with size cap)
- [x] Rewrite `tlm undo` in `src/tlm/cli.py` with interactive picker
- [x] Add `tests/test_snapshot.py` and `tests/test_undo_cli.py`
- [x] Verify `undo --dry-run` and `--hard`

## Sprint 2: Atomic Transaction Manager
- [x] Create `src/tlm/safety/transaction.py`
- [x] Implement two-phase commit with rollback
- [x] Refactor `src/tlm/modes/write.py` to use `AtomicTransaction`
- [x] Add `tests/test_transaction.py`

## Sprint 3: Process Tracking & `tlm stop`
- [x] Create `src/tlm/safety/proctrack.py`
- [x] Update `src/tlm/modes/do.py` to use process registration
- [x] Rewrite `tlm stop` CLI with process listing and signals
- [x] Add `tests/test_proctrack.py`

## Sprint 4: Ask Stream SIGINT
- [x] Harden `src/tlm/providers/openai_compat.py` stream cleanup
- [x] Harden `src/tlm/ask_tools.py` interrupt handling
- [x] Fix B-101: Add read timeout to streaming connections
- [x] Add `tests/test_stream_interrupt.py`

## Sprint 5: Auth Timeout & Session Tokens
- [x] Create `src/tlm/safety/auth_session.py`
- [x] Add `auth_timeout_minutes` to `UserSettings`
- [x] Update `authenticate_tier()` to check/create tokens
- [x] Add `tlm auth login` / `tlm auth logout` subcommands
- [x] Add `tests/test_auth_session.py`

## Sprint 6: Dry-Run Parity & Polish
- [ ] Add `--dry-run` to `auth`, `init`, `new`
- [ ] Update `CODE_INDEX.md`
- [ ] Update `AGENT_PLAN.md`
- [ ] Final quality pass (ruff, mypy)
