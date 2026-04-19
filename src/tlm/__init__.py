"""tlm — terminal LLM helper with optional Tk configuration UI."""

from tlm._version import package_version
from tlm.providers.registry import get_provider, list_provider_ids
from tlm.session import Session

__all__ = ["Session", "get_provider", "list_provider_ids", "package_version", "__version__"]

__version__ = package_version()
