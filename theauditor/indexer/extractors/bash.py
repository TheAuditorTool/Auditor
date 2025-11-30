"""Bash/Shell script extractor - Thin wrapper for tree-sitter Bash extraction."""

from typing import Any

from . import BaseExtractor


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
                from theauditor.ast_extractors.bash_impl import extract_all_bash_data

                try:
                    extracted = extract_all_bash_data(actual_tree, content, file_info["path"])
                    result.update(extracted)
                except Exception as e:
                    import os
                    import sys

                    if os.environ.get("THEAUDITOR_DEBUG"):
                        print(f"[DEBUG] Bash extraction failed: {e}", file=sys.stderr)
                        import traceback

                        traceback.print_exc(file=sys.stderr)

        return result

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
