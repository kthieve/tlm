"""Safety profiles: Tiers 0-3 (Root, Workspace, Whitelist, Sandbox)."""

from __future__ import annotations

import shlex
from dataclasses import replace
from enum import Enum, IntEnum

from tlm.safety.permissions import EffectivePolicy
from tlm.safety.tools import check_readonly


class SafetyTier(IntEnum):
    ROOT = 0        # Tier 0: Root (enhanced 'trusted')
    WORKSPACE = 1   # Tier 1: Workspace ('standard')
    WHITELIST = 2   # Tier 2: Whitelist ('strict')
    SANDBOX = 3     # Tier 3: Sandbox (Isolated bwrap/firejail)


class SafetyProfile(str, Enum):
    trusted = "trusted"
    standard = "standard"
    strict = "strict"
    sandbox = "sandbox"

    @property
    def tier(self) -> SafetyTier:
        return {
            SafetyProfile.trusted: SafetyTier.ROOT,
            SafetyProfile.standard: SafetyTier.WORKSPACE,
            SafetyProfile.strict: SafetyTier.WHITELIST,
            SafetyProfile.sandbox: SafetyTier.SANDBOX,
        }[self]


def normalize_profile(raw: str) -> SafetyProfile:
    s = str(raw).strip().lower()
    if s in ("0", "root"):
        return SafetyProfile.trusted
    if s in ("1", "workspace"):
        return SafetyProfile.standard
    if s in ("2", "whitelist"):
        return SafetyProfile.strict
    if s in ("3", "sandbox"):
        return SafetyProfile.sandbox
    try:
        return SafetyProfile(s)
    except ValueError:
        return SafetyProfile.standard


def is_readonly_argv(argv: list[str]) -> bool:
    if not argv:
        return False
    if argv[0] in ("sudo", "doas", "su", "pkexec"):
        return False
    res = check_readonly(argv)
    if res is not None:
        return res
    return False


def argv_to_line(argv: list[str]) -> str:
    return " ".join(shlex.quote(a) for a in argv)


def all_readonly(argvs: list[list[str]]) -> bool:
    return bool(argvs) and all(is_readonly_argv(a) for a in argvs)


def allow_do_auto_yes(profile: SafetyProfile, argvs: list[list[str]]) -> bool:
    return profile == SafetyProfile.trusted and all_readonly(argvs)


def overlay_effective_policy(ep: EffectivePolicy, profile: str | SafetyProfile) -> EffectivePolicy:
    """Apply safety_profile on top of permissions.toml (stricter profile tightens network/sandbox)."""
    p = profile if isinstance(profile, SafetyProfile) else normalize_profile(profile)
    ep = replace(ep, tier=int(p.tier))
    if p == SafetyProfile.sandbox:
        # Tier 3: Sandbox. Tighten: off network, force auto-sandbox.
        return replace(ep, network_mode="off", sandbox_engine="auto")
    if p == SafetyProfile.strict:
        # Tier 2: Whitelist. Tighten: off network, auto sandbox unless manually disabled.
        return replace(ep, network_mode="off", sandbox_engine="auto" if ep.sandbox_engine != "off" else "off")
    if p == SafetyProfile.standard:
        # Tier 1: Workspace. Respect permissions.toml.
        return ep
    if p == SafetyProfile.trusted:
        # Tier 0: Root. Enhanced: network ON, sandbox OFF.
        return replace(ep, network_mode="on", sandbox_engine="off")
    return ep
