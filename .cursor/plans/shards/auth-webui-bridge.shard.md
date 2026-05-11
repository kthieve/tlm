# Shard: Auth WebUI Bridge
- **Target Version**: v0.7.0
- **Target Feature**: Interface (Unified Configuration Hub)
- **Origin**: v0.3.0 Foundation (Sprint 5)

## Context
Milestone 0.3.0 introduces a session-based auth token stored in `$XDG_STATE_HOME/tlm/.auth_token` with a configurable timeout.

## Contract
The WebUI (v0.7.0) must not implement its own authentication bypass. It must read the `.auth_token` file and validate the expiry before allowing Tier 0/1 operations via the web interface. If no token exists or it is expired, the WebUI should trigger a password prompt that calls the `tlm auth` logic on the host.
