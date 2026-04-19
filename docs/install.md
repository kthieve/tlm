# Installing tlm

**PyPI:** not published yet. Install from a **git clone** (below) or from **GitHub** with `pip` / `pipx` using a `git+https` URL (see [From GitHub](#from-github)).

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

## From GitHub (`pip` / `pipx`, no PyPI)

Use a **tag** (e.g. `v0.2.0b2`). Set the repo to match yours:

```bash
export TLM_GITHUB_REPO=OWNER/tlm   # required: your fork or upstream
export VERSION=0.2.0b2
pipx install "git+https://github.com/${TLM_GITHUB_REPO}.git@v${VERSION}" --force
```

Or the repo’s installer script (after you trust and verify it):

```bash
export TLM_GITHUB_REPO=OWNER/tlm
bash scripts/install.sh 0.2.0b2
```

The script installs from `git+https://github.com/${TLM_GITHUB_REPO}.git@v<version>` using `pipx`, or a fallback venv under `~/.local/share/tlm-venv` if `pipx` is missing.

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
