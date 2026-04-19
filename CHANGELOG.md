# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0b1] - 2026-04-19

### Added

- Beta release: Linux-first installer scripts, zipapp build, packaging scaffolding (deb/AUR; Homebrew/Scoop/winget placeholders).
- `permissions.toml` at `$XDG_CONFIG_HOME/tlm/permissions.toml`: freelist (`allow_paths`, `read_paths`), deny lists, escape grants, network/sandbox settings, per-project overrides.
- Path classification (`jail`, freelist, escape consent), root-access guard, optional `bwrap`/`firejail` wrapping for `tlm do`.
- CLI: `tlm paths`, `tlm allow`, `tlm unallow`; `tlm config migrate-keys` (optional keyring extra).
- GUI Permissions tab: freelist, engine, network mode, escape grants, root policy notice.
- Log redaction for secrets in request JSONL; config file mode warning on load.
- CI: pip-audit; release workflow for wheel/sdist/zipapp/SBOM on `v0.2.*` tags.

### Security

- Stricter handling of elevation (`sudo`/`doas`/etc.) and system paths; profile-based policies (`strict` / `standard` / `trusted`).

[0.2.0b1]: https://github.com/example/tlm/releases/tag/v0.2.0b1
