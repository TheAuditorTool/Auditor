"""Language-specific toolbox system for TheAuditor.

Toolboxes handle detection and installation of language-specific analysis tools.
Each toolbox implements the LanguageToolbox interface.
"""


from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any


class LanguageToolbox(ABC):
    """Base class for language-specific toolboxes."""

    @abstractmethod
    def detect_project(self, project_dir: Path) -> bool:
        """
        Detect if project uses this language.

        Args:
            project_dir: Path to project root directory

        Returns:
            True if project uses this language, False otherwise
        """
        pass

    @abstractmethod
    def install(self, force: bool = False) -> dict[str, Any]:
        """
        Install language toolchain to sandbox.

        Args:
            force: If True, re-download even if cached binary exists

        Returns:
            Dict with installation result:
            {
                'status': 'success' | 'cached' | 'error',
                'path': str,  # Path to installed binary
                'version': str,  # Tool version
                'cached': bool  # Whether existing binary was reused
            }
        """
        pass


__all__ = ['LanguageToolbox']
