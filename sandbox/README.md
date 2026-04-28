# Development sandbox

Isolated **XDG** config/data/state plus a **`.venv`** under **`sandboxes/<name>/`** (gitignored) so `tlm` does not touch your real `~/.config` / `~/.local`.

**Layout** (per sandbox name, default `default`):

```text
sandboxes/<name>/
  .venv/                  # pip install -e . and console_scripts live here
  .config/tlm/            # XDG_CONFIG_HOME → config.toml, keys, …
  .local/share/           # XDG_DATA_HOME
  .local/state/           # XDG_STATE_HOME
  activate.sh             # POSIX / Git Bash: exports XDG_* then sources venv
  activate.ps1            # PowerShell: sets env then dots Activates.ps1
```

Use repo-root **`sandbox.py`** (not installed as a package).

## Quick start

1. **`python sandbox.py init`** — creates **`sandboxes/default/`**, venv, editable install, **`tlm init`**, and **`activate.sh` / `activate.ps1`**.
2. Put sandbox env + venv on your shell (pick one):

| Shell | Command |
|-------|---------|
| Linux / macOS / Git Bash | `eval "$(python sandbox.py env)"` (POSIX exports; use **`env --posix`** on Windows Git Bash if `env` alone emits PowerShell) |
| PowerShell | **`python sandbox.py env --pwsh`** then paste, or **`. .\sandboxes\default\activate.ps1`** |
| fish | **`python sandbox.py env --fish`** |

3. **`python sandbox.py run tlm ask "hello"`** — runs **`tlm`** from that venv with sandbox XDG (needs **`init`** first).

## Commands

```bash
python sandbox.py                    # short help
python sandbox.py init [--sandbox NAME]
python sandbox.py env [--posix|--pwsh|--fish]
python sandbox.py refresh [--wipe-keys] [--recreate-venv]
python sandbox.py run -- tlm ask "hello"
python sandbox.py shell
```

**Resume:** reuse the same sandbox with **`--sandbox NAME`** or **`-n`** on every command so paths stay stable (e.g. **`init -n dev`** then **`run -n dev -- tlm …`**).

**Env overrides:** **`TLM_SANDBOX_NAME`** (default sandbox name), **`TLM_SANDBOXES_ROOT`** (parent of **`sandboxes/`**). Hidden CLI **`--sandboxes-root`** exists for tests.

## Refresh and API keys

**`refresh`** removes **`sandboxes/<name>/.config`** and **`sandboxes/<name>/.local`**, reinstalls **`pip install -e .`** with that sandbox’s Python, runs **`tlm init`**, and restores **`[keys]`** from the backed-up **`config.toml`** unless **`--wipe-keys`**. **`--recreate-venv`** deletes **`.venv`** before reinstall.

## Legacy layout

Older setups used **`repo/sandbox/.config`** (still gitignored). Prefer **`python sandbox.py init`** targeting **`sandboxes/`**; move settings manually if you still use the old tree.

## Try write / do

```bash
mkdir -p playground
python sandbox.py run tlm write "add note.txt containing one line hello" --dir playground
```

On Windows PowerShell you can use **`mkdir playground`** instead of **`mkdir -p`**.

Or open **`python sandbox.py shell`**, create **`playground`**, then run **`tlm`** as usual.

Git ignores **`sandboxes/`** — see root **`.gitignore`**.
