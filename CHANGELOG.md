# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0.dev5] - 2026-04-21

### Added

- **Web / Lightpanda** settings tab in **Tk** and **FLTK** GUIs: enable web, `lightpanda_path`, optional **auto-check** against GitHub on tab open, status text, **download/update** binary to `~/.local/share/tlm/bin/lightpanda`, open releases page.
- **`tlm config`** TUI **`w`**: same options plus GitHub status refresh and download.

## [0.2.0.dev4] - 2026-04-21

### Added

- **web_enabled** in **`tlm init --wizard`**, **`tlm config`** TUI (`w`), and config **GUI** (Tk + FLTK Keys tab): optional `lightpanda_path`, short Lightpanda hint in the terminal wizard.

## [0.2.0.dev3] - 2026-04-21

### Added

- **`tlm web`** subcommand (same flags as `tlm ask`) — sets **web_focus** so the model is nudged to use ```tlm-web```; system prompt explains missing `web_enabled` / Lightpanda instead of a generic “no live web” reply.

## [0.2.0.dev2] - 2026-04-21

### Changed

- Ask mode: **`tlm-web` search and fetch use Lightpanda only**; prompts instruct the model to rely on `tlm-web` for web search/pages (no HTTP search API path in the ask loop).

## [0.2.0b4] - 2026-04-21

### Changed

- Ask web tools: model guidance prefers **Lightpanda** (`tlm-web`) for heavy search/browse, optional **Brave Search API** fallback when `brave-search` / `TLM_BRAVE_SEARCH_API_KEY` is set (after a failed Lightpanda search, or search-only when Lightpanda is missing); simple one-off GETs may use **`tlm-exec` + curl**.

[0.2.0b4]: https://github.com/example/tlm/releases/tag/v0.2.0b4

## [0.2.0b2] - 2026-04-19

### Added

- Ask mode: optional **Lightpanda** web tools — fenced `tlm-web` JSON blocks (`fetch` / `search` via DuckDuckGo lite); per-fetch confirmation; config keys `web_enabled`, `lightpanda_path`, `web_dump`, `web_obey_robots`, `web_max_output_chars`, `web_disable_lightpanda_telemetry`, `web_allow_http`; CLI `tlm ask --no-web` and `tlm ? … --no-web`.

[0.2.0b2]: https://github.com/example/tlm/releases/tag/v0.2.0b2

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
