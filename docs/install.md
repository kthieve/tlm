# Installing tlm

## From PyPI (when published)

Isolated CLI:

```bash
pipx install "tlm==0.2.0b2"
# or
pip install --user "tlm==0.2.0b2"
```

## From GitHub

Use the installer script: download it, verify the SHA256 from the release, then run it. Avoid unchecked `curl … | bash` pipelines.

```bash
# After verifying the script checksum from the release page:
bash scripts/install.sh 0.2.0b2
```

Release artifacts on GitHub may include wheels, sdist, `tlm.pyz` zipapp, and checksums (see `.github/workflows/release.yml`).

## From a git clone (development)

```bash
cd /path/to/tlm
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
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
