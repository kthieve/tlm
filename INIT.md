# Blueprint Scaffold

Small tool: fill the form → run `python scaffold.py` → new project folder (default: `../<project-slug>/`), **or** merge into an **existing** repo with `--init-existing`.

**Version:** see `VERSION`.

**AI / agent checklist for brownfield projects:** `AI_INIT.md` (inventory → form → dry-run → merge → fix up `AGENTS.md` / `CODE_INDEX.md`).

## Steps (new project)

1. Edit `Describe_Here.md` (required `##` blocks only; see below).
2. From `SCAFFOLD/`: `python scaffold.py`
3. Optional: `python scaffold.py --dry-run` to preview paths.

## Steps (existing project)

1. Add `Describe_Here.md` to the **project root** (same headings as the default form), or keep using `--form` pointing at a filled copy.
2. Preview: `python scaffold.py --init-existing /path/to/project --dry-run` (run from the folder that contains `scaffold.py`).
3. Apply: same command without `--dry-run`. Existing files are **left unchanged** unless you pass `--init-overwrite`.
4. Follow `AI_INIT.md` to reconcile docs with the real codebase.

## Optional form sections

Add any of these **after** the required blocks if you want them; otherwise defaults apply.

| Heading | Default |
|---------|---------|
| `## Core Features` | empty |
| `## Scale` | Small |
| `## Documentation Level` | Minimal |
| `## Additional Notes` | empty |

`Scale`: Small / Medium / Large — extra dirs and files from `template.json`.  
`Documentation Level`: Standard adds `AGENTS.md` + `CODE_INDEX.md`; Full (or Large scale) also adds sprint/bug/catalog stubs.

## CLI

| Flag | Meaning |
|------|---------|
| `--form PATH` | Form file (default: `./Describe_Here.md`) |
| `--output PATH` | Output dir (default: parent of SCAFFOLD + slug) |
| `--dry-run` | Print plan only |
| `--list` | List templates |
| `--template ID` | Force `templates/<ID>/` |
| `--threshold N` | Min keyword score for a non-fallback match (default: 1) |
| `--no-fallback` | Write `unmatched/<slug>_request.md` instead of using generic |
| `--force` | Replace existing output dir (not allowed with `--init-existing`) |
| `--init-existing DIR` | Merge template into **existing** project `DIR`; create missing dirs/files only |
| `--init-overwrite` | With `--init-existing`: overwrite every path the template would write |

Matching: text from Language, Project Type, Dependencies, Description, Target Platform, and Additional Notes is tokenized and scored against each template’s `keywords` in `templates/*/template.json`. Below threshold → **generic** fallback (unless `--no-fallback`).

## Placeholders in `.tmpl` files

`{{project_name}}`, `{{project_slug}}`, `{{description}}`, `{{features}}`, `{{dependencies}}`, `{{language_framework}}`, `{{project_type}}`, `{{target_platform}}`, `{{scale}}`, `{{documentation_level}}`, `{{additional_notes}}`, `{{year}}`, `{{package_json_description}}`

## New template

Copy `templates/generic/`, `templates/python_app/`, or `templates/python_gui_ctk/` (full `ui/` + `core/` + `utils/` + doc set), edit `template.json` and `files/*.tmpl`, then `python scaffold.py --list`.
