"""Secret detection rules module."""

from .hardcoded_secret_analyze import find_hardcoded_secrets

__all__ = ['find_hardcoded_secrets']