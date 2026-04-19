# Development sandbox

Isolated **XDG** paths under `sandbox/` so `tlm` does not touch your real `~/.config` / `~/.local`.

Use the repo-root script **`sandbox.py`** (not a package):

```bash
python sandbox.py              # quick help
python sandbox.py env          # prints exports →  eval "$(python sandbox.py env)"
python sandbox.py init         # tlm init in the sandbox
python sandbox.py refresh      # wipe sandbox + pip install -e . + init (keeps API keys)
python sandbox.py refresh --wipe-keys   # same but drop saved [keys] too
python sandbox.py run tlm ask "hello"   # one command with sandbox env
python sandbox.py shell        # interactive bash -i with sandbox env
```

Fish: run `python sandbox.py env --fish` and paste the `set -gx` lines, or use `python sandbox.py shell` (bash).

## Refresh and API keys

`refresh` deletes `sandbox/.config` and `sandbox/.local`, reinstalls the editable package from `src/`, then runs `tlm init`. By default it **re-applies `[keys]`** from the previous `config.toml` so you do not lose API keys. Use **`--wipe-keys`** to start with no saved keys.

## Try write / do

```bash
mkdir -p sandbox/playground
python sandbox.py run tlm write "add note.txt containing one line hello" --dir sandbox/playground
```

Or: `python sandbox.py shell`, then `mkdir -p sandbox/playground` and run `tlm …` as usual.

Git ignores `sandbox/.config/` and `sandbox/.local/` (see repo `.gitignore`).
