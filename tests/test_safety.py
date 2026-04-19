from pathlib import Path

from tlm.safety import check_argv, check_command_line, is_readonly_argv, normalize_profile
from tlm.safety.permissions import EffectivePolicy
from tlm.safety.profiles import SafetyProfile, overlay_effective_policy


def test_deny_rm_rf() -> None:
    ok, _ = check_command_line("rm -rf /tmp/x")
    assert ok is False


def test_allow_ls() -> None:
    ok, _ = check_argv(["ls", "-la"])
    assert ok is True


def test_readonly_ls() -> None:
    assert is_readonly_argv(["ls"]) is True


def test_readonly_git_status() -> None:
    assert is_readonly_argv(["git", "status"]) is True


def test_not_readonly_git_push() -> None:
    assert is_readonly_argv(["git", "push"]) is False


def test_normalize_profile() -> None:
    assert normalize_profile("standard") == SafetyProfile.standard


def test_overlay_trusted_sets_network_on() -> None:
    ep = EffectivePolicy(
        network_mode="ask",
        sandbox_engine="auto",
        allow_paths=[],
        read_paths=[],
        deny_paths=[],
        allow_commands=[],
        deny_commands=[],
        escape_grants=[],
        cwd=Path.cwd(),
        project_root=None,
    )
    o = overlay_effective_policy(ep, "trusted")
    assert o.network_mode == "on"
    assert o.sandbox_engine == "off"
