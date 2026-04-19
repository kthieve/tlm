"""Optional bubblewrap / firejail wrapping for `tlm do`."""

from __future__ import annotations

import shutil
from pathlib import Path

from tlm.safety.permissions import EffectivePolicy


def resolved_engine(policy: EffectivePolicy) -> str:
    s = policy.sandbox_engine.strip().lower()
    if s == "auto":
        if shutil.which("bwrap"):
            return "bwrap"
        if shutil.which("firejail"):
            return "firejail"
        return "off"
    return s


def wrap_argv(
    argv: list[str],
    *,
    cwd: Path,
    policy: EffectivePolicy,
    unshare_net: bool,
) -> list[str]:
    eng = resolved_engine(policy)
    c = cwd.resolve()
    if eng == "bwrap" and shutil.which("bwrap"):
        base = [
            "bwrap",
            "--ro-bind",
            "/",
            "/",
            "--bind",
            str(c),
            str(c),
            "--dev",
            "/dev",
            "--proc",
            "/proc",
            "--unshare-user",
            "--die-with-parent",
        ]
        if unshare_net:
            base.append("--unshare-net")
        return [*base, "--", *argv]
    if eng == "firejail" and shutil.which("firejail"):
        fj = ["firejail", "--quiet", f"--cwd={c}"]
        if unshare_net:
            fj.append("--net=none")
        return [*fj, *argv]
    return argv
