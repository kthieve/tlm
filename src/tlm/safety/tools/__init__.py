"""Initialize the modular tool registry."""

from __future__ import annotations

from tlm.safety.tools.registry import register_tool, check_readonly, is_known_tool, get_tool_wrapper
from tlm.safety.tools.git import GitWrapper
from tlm.safety.tools.generic import ReadOnlyToolWrapper
from tlm.safety.tools.pkg_manager import PackageManagerWrapper

# Register modular tools
register_tool(GitWrapper())

# Register package managers
_PKG_MANAGERS = ["apt", "apt-get", "dnf", "yum", "pacman", "zypper", "apk"]
for pkg in _PKG_MANAGERS:
    register_tool(PackageManagerWrapper(pkg))

# Register simple read-only tools
_SIMPLE_READONLY = [
    "ls", "dir", "cat", "head", "tail", "less", "more", "pwd", "echo",
    "which", "whereis", "file", "stat", "id", "whoami", "uname", "date",
    "uptime", "df", "du", "free", "lscpu", "lspci", "lsusb", "sensors"
]

for cmd in _SIMPLE_READONLY:
    register_tool(ReadOnlyToolWrapper(cmd))

__all__ = ["register_tool", "check_readonly", "is_known_tool", "get_tool_wrapper"]
