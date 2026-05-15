# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.2.dev6] - 2026-05-15

### Fixed

- **Installer**: Fixed `_tkinter.TclError` crashes in `install_gui.py` by adding thread-safe checks for widget existence before updating the UI from background threads. This prevents crashes if the window is closed during installation.

## [0.4.2.dev5] - 2026-05-15

### Fixed

- **Installer**: Fixed a bug where updating an existing non-portable installation would incorrectly switch it to portable mode. The installer now correctly detects the existing installation mode by checking the launcher script and data directory.

## [0.4.2.dev4] - 2026-05-15

### Added

- **Installer**: Added a direct "Reinstall as Portable" option to both the terminal (`install.py`) and graphical (`install_gui.py`) installers. This allows users to easily convert an existing installation into a single-folder portable setup.

## [0.4.2.dev3] - 2026-05-15

### Added

- **GUI: Browser Installer**: Added a selection dialog to "Install Browser" in the Web Browser tab.
- **Cross-Platform Support**: The installer now offers Lightpanda (Linux/Mac) or Playwright (All platforms) based on the user's OS.

## [0.4.2.dev2] - 2026-05-15

### Added

- **Elevation Support**: New `tlm.safety.elevation` module for cross-platform privilege detection and elevation (UAC on Windows, sudo/pkexec on Linux/macOS).
- **GUI**: Added elevation status and "Run as Admin" button to the About tab in both Tk and FLTK interfaces.
- **CLI**: New `tlm elevate` command to restart the CLI with administrative privileges.

## [0.4.2.dev1] - 2026-05-15

### Fixed

- **Web Browser Backend**: Fixed `SyntaxError` in `playwright_backend.py` (missing `except` block in `install_chromium`) which caused the CLI and GUI to crash on import.

## [0.4.1] - 2026-05-15

### Added

- **Web Browser Backend**: Introduced Playwright as a cross-platform alternative to Lightpanda.
- **Windows Support**: `tlm-web` now works on Windows via Playwright + Chromium auto-installation.
- **Backend Selection**: Added `web_backend` setting ("auto", "lightpanda", "playwright") to `config.toml`.
- **Unified Installer**: New browser installation flow in GUI, TUI, and setup wizard.
- **Optional Dependencies**: Added `[web]` extra group for `playwright` and `markdownify`.

### Changed

- **UI/UX**: Renamed "Web / Lightpanda" tab to "Web Browser" and updated all web-related messaging to be backend-agnostic.
- **Architecture**: Decoupled `tlm-web` tools from the Lightpanda binary via a new backend abstraction layer.

## [0.4.0.dev4] - 2026-05-15

### Changed

- **Path Detection**: Improved `find_tlm_bin_dir` to be more robust, checking `sys.prefix/Scripts` on Windows and other common installation paths.
- **GUI**: Added "Detected Bin Path" status label to the About tab.

## [0.4.0.dev3] - 2026-05-15

### Changed

- **Versioning Rules**: Formalized the requirement in `AGENTS.md` to bump the subversion and update the changelog at every substantive task completion.

## [0.4.0.dev2] - 2026-05-15

### Added

- **GUI: Add to PATH**: New "Add to PATH" button in the About tab with automatic detection of the correct binary directory and platform-specific logic (Windows Registry vs. Linux shell profile).

## [0.4.0.dev1] - 2026-05-14

### Added

- **Ability System (Plugins)**: Initial implementation of the "Abilities" plugin architecture.
- **CLI abilities command**: `tlm abilities` to list discovered plugins.
- **TUI/GUI Abilities Tab**: Integrated plugin discovery and management into the configuration interfaces.

## [0.3.0.dev2] - 2026-05-13

### Changed

- **Improved CLI Help**: Switched to `rich-argparse` for prettier, syntax-highlighted help output (requires `rich-argparse` dependency).
- **Subcommand Formatting**: Enhanced descriptions and layout for all `tlm` subcommands using `RichHelpFormatter`.

## [0.3.0.dev1] - 2026-05-12

### Added

- **Atomic Transactions**: `write` mode now uses a two-phase commit system (via `AtomicTransaction`) to ensure multi-file updates either succeed completely or roll back entirely on failure.
- **Temporal Snapshots**: Workspace snapshots are now created before destructive operations (`write`, `do`) using `git stash create` for non-destructive capturing of dirty states (or `shutil.copytree` fallback for non-git directories).
- **Interactive Undo**: `tlm undo` command with an interactive snapshot picker, `--dry-run` with file diffs, and confirmation prompts.
- **Process Tracking**: Multi-process tracking for `tlm do`; `tlm stop` command to kill all runaway processes in a group.
- **Auth Sessions**: Token-based authentication with configurable timeouts and master recovery keys to bypass lost passwords.
- **Dry-Run Parity**: Added `--dry-run` support to `auth`, `init`, `new`, `undo`, and `stop` subcommands.

### Changed

- **Interrupt Handling**: Hardened `openai_compat.py` and `ask_tools.py` to handle `SIGINT` (Ctrl+C) gracefully during model streaming and tool loops, including read timeouts to prevent hangs on high-latency buffers.
- **Snapshot Logic**: Moved from destructive `git add .` to `git stash create`, preserving untracked files and the working index.


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
