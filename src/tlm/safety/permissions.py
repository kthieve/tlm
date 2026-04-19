"""Load/save `$XDG_CONFIG_HOME/tlm/permissions.toml` and resolve effective policy per cwd."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
import tomllib

from tlm.settings import config_dir


def permissions_file_path() -> Path:
    return config_dir() / "permissions.toml"


@dataclass
class ProjectOverride:
    root: str  # absolute path prefix
    allow_paths: list[str] = field(default_factory=list)
    read_paths: list[str] = field(default_factory=list)
    deny_paths: list[str] = field(default_factory=list)
    allow_commands: list[str] = field(default_factory=list)
    deny_commands: list[str] = field(default_factory=list)
    network_mode: str | None = None
    sandbox_engine: str | None = None


@dataclass
class PermissionsFile:
    network_mode: str = "ask"
    sandbox_engine: str = "auto"
    allow_paths: list[str] = field(default_factory=list)
    read_paths: list[str] = field(default_factory=list)
    deny_paths: list[str] = field(default_factory=list)
    allow_commands: list[str] = field(default_factory=list)
    deny_commands: list[str] = field(default_factory=list)
    escape_grants: list[str] = field(default_factory=list)
    projects: list[ProjectOverride] = field(default_factory=list)


@dataclass
class EffectivePolicy:
    """Merged policy for a given cwd (paths still as configured; use realpath in jail)."""

    network_mode: str
    sandbox_engine: str
    allow_paths: list[str]
    read_paths: list[str]
    deny_paths: list[str]
    allow_commands: list[str]
    deny_commands: list[str]
    escape_grants: list[str]
    cwd: Path
    project_root: Path | None  # matched [[project]].root or git toplevel


def _toml_escape_str(s: str) -> str:
    return json.dumps(s)


def _validate_path_entry(raw: str, *, label: str) -> None:
    p = Path(os.path.expanduser(raw)).resolve()
    s = str(p)
    home = Path.home().resolve()
    if s == "/" or s == str(home):
        raise ValueError(f"{label}: refusing overly broad path {raw!r} (use a subdirectory)")
    if s == "/home":
        raise ValueError(f"{label}: refusing {raw!r} (too broad)")


def validate_path_list(paths: list[str], *, label: str) -> None:
    for x in paths:
        _validate_path_entry(x, label=label)


def load_permissions_file() -> PermissionsFile:
    path = permissions_file_path()
    if not path.is_file():
        return PermissionsFile()
    raw = path.read_text(encoding="utf-8")
    data = tomllib.loads(raw)
    if not isinstance(data, dict):
        return PermissionsFile()
    g = data.get("global") if isinstance(data.get("global"), dict) else data
    if not isinstance(g, dict):
        g = {}
    projects: list[ProjectOverride] = []
    for block in data.get("project") or []:
        if not isinstance(block, dict):
            continue
        r = block.get("root")
        if not isinstance(r, str) or not r.strip():
            continue
        projects.append(
            ProjectOverride(
                root=r.strip(),
                allow_paths=_str_list(block.get("allow_paths")),
                read_paths=_str_list(block.get("read_paths")),
                deny_paths=_str_list(block.get("deny_paths")),
                allow_commands=_str_list(block.get("allow_commands")),
                deny_commands=_str_list(block.get("deny_commands")),
                network_mode=block.get("network_mode") if isinstance(block.get("network_mode"), str) else None,
                sandbox_engine=block.get("sandbox_engine") if isinstance(block.get("sandbox_engine"), str) else None,
            )
        )
    eg = data.get("escape_grants")
    escape_grants: list[str] = []
    if isinstance(eg, dict) and isinstance(eg.get("paths"), list):
        escape_grants = [str(x) for x in eg["paths"] if isinstance(x, str)]
    elif isinstance(eg, list):
        escape_grants = [str(x) for x in eg if isinstance(x, str)]

    pf = PermissionsFile(
        network_mode=str(g.get("network_mode", "ask")),
        sandbox_engine=str(g.get("sandbox_engine", "auto")),
        allow_paths=_str_list(g.get("allow_paths")),
        read_paths=_str_list(g.get("read_paths")),
        deny_paths=_str_list(g.get("deny_paths")),
        allow_commands=_str_list(g.get("allow_commands")),
        deny_commands=_str_list(g.get("deny_commands")),
        escape_grants=escape_grants,
        projects=projects,
    )
    validate_path_list(pf.allow_paths, label="allow_paths")
    validate_path_list(pf.read_paths, label="read_paths")
    validate_path_list(pf.deny_paths, label="deny_paths")
    for pr in pf.projects:
        validate_path_list(pr.allow_paths, label=f"project[{pr.root}].allow_paths")
        validate_path_list(pr.read_paths, label=f"project[{pr.root}].read_paths")
        validate_path_list(pr.deny_paths, label=f"project[{pr.root}].deny_paths")
    validate_path_list(pf.escape_grants, label="escape_grants")
    return pf


def _str_list(v: object) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if isinstance(x, str)]
    return []


def git_toplevel(cwd: Path) -> Path | None:
    import subprocess

    try:
        p = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0 or not p.stdout.strip():
        return None
    return Path(p.stdout.strip()).resolve()


def effective_policy(cwd: Path) -> EffectivePolicy:
    pf = load_permissions_file()
    c = cwd.resolve()
    proj: ProjectOverride | None = None
    gt = git_toplevel(c)
    candidates: list[tuple[int, ProjectOverride]] = []
    for p in pf.projects:
        root = Path(os.path.expanduser(p.root)).resolve()
        try:
            c.relative_to(root)
            candidates.append((len(str(root)), p))
        except ValueError:
            continue
    if candidates:
        proj = max(candidates, key=lambda x: x[0])[1]
    allow = list(pf.allow_paths)
    read = list(pf.read_paths)
    deny = list(pf.deny_paths)
    ac = list(pf.allow_commands)
    dc = list(pf.deny_commands)
    net = pf.network_mode
    sbox = pf.sandbox_engine
    esc = list(pf.escape_grants)
    pr_root: Path | None = gt
    if proj:
        pr_root = Path(os.path.expanduser(proj.root)).resolve()
        allow = _merge_lists(proj.allow_paths, allow)
        read = _merge_lists(proj.read_paths, read)
        deny = _merge_lists(proj.deny_paths, deny)
        ac = _merge_lists(proj.allow_commands, ac)
        dc = _merge_lists(proj.deny_commands, dc)
        if proj.network_mode:
            net = proj.network_mode
        if proj.sandbox_engine:
            sbox = proj.sandbox_engine
    return EffectivePolicy(
        network_mode=net,
        sandbox_engine=sbox,
        allow_paths=allow,
        read_paths=read,
        deny_paths=deny,
        allow_commands=ac,
        deny_commands=dc,
        escape_grants=esc,
        cwd=c,
        project_root=pr_root,
    )


def _merge_lists(override: list[str], base: list[str]) -> list[str]:
    # project-specific entries take precedence by being checked first in classifier
    out = list(override)
    for b in base:
        if b not in out:
            out.append(b)
    return out


def add_freelist_path(
    raw: str,
    *,
    read_only: bool,
    project: bool,
    project_root: Path | None,
) -> None:
    """Add path to global or [[project]] freelist."""
    rp = str(Path(os.path.expanduser(raw)).resolve())
    _validate_path_entry(rp, label="path")
    pf = load_permissions_file()
    if project:
        root = str((project_root or Path.cwd()).resolve())
        for pr in pf.projects:
            if pr.root == root:
                lst = pr.read_paths if read_only else pr.allow_paths
                if rp not in lst:
                    lst.append(rp)
                save_permissions_file(pf)
                return
        pf.projects.append(
            ProjectOverride(
                root=root,
                allow_paths=[] if read_only else [rp],
                read_paths=[rp] if read_only else [],
            )
        )
    else:
        lst = pf.read_paths if read_only else pf.allow_paths
        if rp not in lst:
            lst.append(rp)
    save_permissions_file(pf)


def remove_freelist_path(raw: str, *, project: bool, project_root: Path | None) -> bool:
    """Remove path from allow/read/escape_grants. Returns True if something removed."""
    rp = str(Path(os.path.expanduser(raw)).resolve())
    pf = load_permissions_file()
    removed = False
    if rp in pf.escape_grants:
        pf.escape_grants = [x for x in pf.escape_grants if x != rp]
        removed = True
    if project:
        root = str((project_root or Path.cwd()).resolve())
        for pr in pf.projects:
            if pr.root != root:
                continue
            if rp in pr.allow_paths:
                pr.allow_paths = [x for x in pr.allow_paths if x != rp]
                removed = True
            if rp in pr.read_paths:
                pr.read_paths = [x for x in pr.read_paths if x != rp]
                removed = True
    else:
        if rp in pf.allow_paths:
            pf.allow_paths = [x for x in pf.allow_paths if x != rp]
            removed = True
        if rp in pf.read_paths:
            pf.read_paths = [x for x in pf.read_paths if x != rp]
            removed = True
    if removed:
        save_permissions_file(pf)
    return removed


def save_permissions_file(pf: PermissionsFile) -> None:
    path = permissions_file_path()
    lines: list[str] = []
    lines.append("[global]")
    lines.append(f"network_mode = {_toml_escape_str(pf.network_mode)}")
    lines.append(f"sandbox_engine = {_toml_escape_str(pf.sandbox_engine)}")
    lines.append(f"allow_paths = {_toml_list(pf.allow_paths)}")
    lines.append(f"read_paths = {_toml_list(pf.read_paths)}")
    lines.append(f"deny_paths = {_toml_list(pf.deny_paths)}")
    lines.append(f"allow_commands = {_toml_list(pf.allow_commands)}")
    lines.append(f"deny_commands = {_toml_list(pf.deny_commands)}")
    for pr in pf.projects:
        lines.append("")
        lines.append("[[project]]")
        lines.append(f"root = {_toml_escape_str(pr.root)}")
        lines.append(f"allow_paths = {_toml_list(pr.allow_paths)}")
        lines.append(f"read_paths = {_toml_list(pr.read_paths)}")
        lines.append(f"deny_paths = {_toml_list(pr.deny_paths)}")
        lines.append(f"allow_commands = {_toml_list(pr.allow_commands)}")
        lines.append(f"deny_commands = {_toml_list(pr.deny_commands)}")
        if pr.network_mode is not None:
            lines.append(f"network_mode = {_toml_escape_str(pr.network_mode)}")
        if pr.sandbox_engine is not None:
            lines.append(f"sandbox_engine = {_toml_escape_str(pr.sandbox_engine)}")
    lines.append("")
    lines.append("[escape_grants]")
    lines.append(f"paths = {_toml_list(pf.escape_grants)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _toml_list(xs: list[str]) -> str:
    inner = ", ".join(_toml_escape_str(x) for x in xs)
    return f"[{inner}]"
