"""Bash/Shell script extractor - Thin wrapper for tree-sitter Bash extraction."""

from typing import Any

from theauditor.utils.logging import logger

from . import BaseExtractor
from ..fidelity_utils import FidelityToken


class BashExtractor(BaseExtractor):
    """Extractor for Bash/Shell script files."""

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return [".sh", ".bash"]

    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract all relevant information from a Bash/Shell script file."""
        result = self._empty_result()

        if not tree:
            return result

        if isinstance(tree, dict) and tree.get("type") == "tree_sitter":
            actual_tree = tree.get("tree")
            if actual_tree:
                from theauditor.ast_extractors.base import check_tree_sitter_parse_quality
                from theauditor.ast_extractors.bash_impl import extract_all_bash_data

                check_tree_sitter_parse_quality(actual_tree.root_node, file_info["path"], logger)

                try:
                    extracted = extract_all_bash_data(actual_tree, content, file_info["path"])
                    result.update(extracted)
                except Exception as e:
                    logger.debug(f"Bash extraction failed: {e}")

                    logger.exception("")

        return FidelityToken.attach_manifest(result)

    def _empty_result(self) -> dict[str, Any]:
        """Return an empty result structure."""
        return {
            "bash_functions": [],
            "bash_variables": [],
            "bash_sources": [],
            "bash_commands": [],
            "bash_pipes": [],
            "bash_subshells": [],
            "bash_redirections": [],
        }
