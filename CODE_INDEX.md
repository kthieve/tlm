# CODE_INDEX — tlm

| Path | Role |
|------|------|
| `src/tlm/cli.py` | argparse + `tlm ?` pre-parse; ask / write / do / gui |
| `src/tlm/config.py` | XDG paths, env keys, default provider |
| `src/tlm/session.py` | JSON session load/save |
| `src/tlm/providers/base.py` | `LLMProvider` protocol |
| `src/tlm/providers/stub.py` | Stub completions until real APIs |
| `src/tlm/providers/registry.py` | Provider id → instance |
| `src/tlm/safety/shell.py` | Denylist + argv preview for `do` |
| `src/tlm/gui/app.py` | Tk skeleton |
| `pyproject.toml` | Packaging, `tlm` console script |
| `requirements.txt` | Runtime pins (mirror `[project].dependencies`) |
| `Describe_Here.md` | Project form / requirements |
| `INIT.md` | Original scaffold tool instructions (no `scaffold.py` in tree) |
| `AI_INIT.md` | Brownfield agent workflow |
