"""TheAuditor - Offline, air-gapped CLI for repo indexing and evidence checking."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("theauditor")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

__all__ = ["__version__"]
