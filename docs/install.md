# Installing tlm

**PyPI:** not published yet. Install from a **git clone** (below) or from **GitHub** with `pip` / `pipx` using a `git+https` URL (see [From GitHub](#from-github)).

## One-liner (pipx or venv; no clone)

Uses the installer from the default branch. Review the script before piping; use a **tagged** URL for a known revision.

```bash
curl -fsSL https://raw.githubusercontent.com/kthieve/tlm/main/scripts/install.sh | bash -s 0.2.0b2
```

Ensure `~/.local/bin` is on your `PATH` (the script prints a hint if it is not). Forks: `TLM_GITHUB_REPO=you/tlm curl -fsSL … | bash -s 0.2.0b2`.

After install, upgrade to the latest GitHub release when prompted (if you enabled update checks in config) or run:

```bash
tlm update --yes
```

(`tlm update` without `--yes` only shows the command that would run.)

## From a git clone (recommended)

```bash
git clone https://github.com/OWNER/tlm.git
cd tlm
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -U pip
pip install -e .
```

Replace `OWNER` with the real GitHub org or user. For one-off installs without cloning, use the GitHub URL method below.

### Update your install from this clone

After `git pull`, refresh the `tlm` on your PATH (pipx, `~/.local/share/tlm-venv`, or `./.venv`) with an **editable** reinstall from the repo root:

```bash
bash scripts/update-from-clone.sh
```

Use `--no-pull` to reinstall from the tree as-is without fetching. The script runs `git pull --ff-only` by default when `.git` exists.

## From GitHub (`pip` / `pipx`, no PyPI)

Use a **tag** (e.g. `v0.2.0b2`). Set the repo to match yours:

```bash
export TLM_GITHUB_REPO=OWNER/tlm   # your fork or upstream (omit for default kthieve/tlm with install.sh)
export VERSION=0.2.0b2
pipx install "git+https://github.com/${TLM_GITHUB_REPO}.git@v${VERSION}" --force
```

Or the repo’s installer script (after you trust and verify it); `TLM_GITHUB_REPO` defaults to `kthieve/tlm` if unset:

```bash
bash scripts/install.sh 0.2.0b2
# forks: TLM_GITHUB_REPO=you/tlm bash scripts/install.sh 0.2.0b2
```

The script installs from `git+https://github.com/${TLM_GITHUB_REPO}.git@v<version>` using `pipx`, or a fallback venv under `~/.local/share/tlm-venv` if `pipx` is missing. If `TLM_GITHUB_REPO` is unset, it defaults to `kthieve/tlm`.

### Update checks (optional)

In `config.toml`, set `check_for_updates = true` (or use `tlm config` → updates). Once per day at most, tlm may print one line to stderr if a newer **GitHub release** exists. Disable with `TLM_NO_UPDATE_CHECK=1`. Nothing is installed automatically; run `tlm update --yes`.

## PyPI (when published)

```bash
pipx install "tlm==0.2.0b2"
# or
pip install --user "tlm==0.2.0b2"
```

## Optional extras

See [`pyproject.toml`](../pyproject.toml) `[project.optional-dependencies]`:

| Extra | Purpose |
|-------|---------|
| `usage` | Better token counting (`tiktoken`) |
| `gui-fltk` | FLTK window UI (system FLTK / `fltk-config`) |
| `openai` | Official OpenAI client if needed |
| `secure` | Keyring helpers (`tlm config migrate-keys`) |
| `dev` | `pytest`, `ruff`, `mypy`, `pip-audit` |

```bash
pip install -e ".[usage,dev]"
```

## Window UI

`TLM_GUI=tk` (default when Tk is available), `TLM_GUI=fltk` after `[gui-fltk]`, or `TLM_GUI=auto`.
