# AI workflow — scaffold an existing project

Use this when the repo **already has code** and you need **agent docs + missing stubs** without clobbering working files.

## Goals

1. Reflect the real tree and stack in the form and indexes.
2. Merge template outputs **only where files are missing** (unless the human passes `--init-overwrite`).
3. Leave `INIT.md` / templates in the **SCAFFOLD** tool folder as the source of truth for how to re-run the tool.

## Steps (do in order)

### 1. Inventory

- List top-level layout, entrypoint (`main.py`, `src/…`, `package.json`, etc.).
- Note language, UI/framework, platform, and dependencies.

### 2. Form file

- Ensure `Describe_Here.md` exists **either** next to `scaffold.py` **or** in the **target project root** (same `##` headings as `SCAFFOLD/Describe_Here.md`).
- Fill required sections from the inventory. Set **Scale** / **Documentation Level** if you want extra dirs (tests, docs, agent stubs).

### 3. Pick template

- Prefer keyword match (`python scaffold.py --dry-run` from SCAFFOLD shows the chosen template).
- If nothing fits: extend `templates/<id>/` or use `--template generic`, then re-run.

### 4. Preview merge

From the directory that contains `scaffold.py`:

```bash
python scaffold.py --init-existing /path/to/existing/project --dry-run
```

Add `--template python_gui_ctk` (or another id) if you need to override auto-match.

### 5. Apply merge

```bash
python scaffold.py --init-existing /path/to/existing/project
```

- **Default:** existing files are **skipped**; only missing paths are created.
- **`--init-overwrite`:** replace every file that the template would emit (use only when intentional).

### 6. After merge (manual / AI pass)

- Open `AGENTS.md`, `CODE_INDEX.md`, `CODE_CATALOG.md` and **align** them with the real files (line refs, stub lists, catalog rows).
- Update `AGENT_PLAN.md` / `AGENT_TODO.md` with the next concrete tasks.
- Do **not** blindly trust generated indexes if the project already had different structure.

## One-liners

| Intent | Command |
|--------|---------|
| Preview | `python scaffold.py --init-existing . --dry-run` (from project root; form = `./Describe_Here.md` if present) |
| Force template | `python scaffold.py --init-existing . --template python_gui_ctk --dry-run` |
| Overwrite all emitted files | `python scaffold.py --init-existing . --init-overwrite` |

## Copying the tool into the repo

Optional: vendor `scaffold.py`, `templates/`, `INIT.md`, `Describe_Here.md`, and this file under e.g. `tools/scaffold/` so the team can run merges without an external path. Keep **one** canonical form file to avoid drift.
