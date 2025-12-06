"""
JavaScript/TypeScript Build Guard.

Ensures the compiled extractor.cjs always matches the TypeScript source code.
Follows the same pattern as schemas/codegen.py - explicit file list, deterministic hash,
hard fail on mismatch.

NO FALLBACKS. If build fails, it fails loud.
"""

import hashlib
import os
import subprocess
from pathlib import Path

from theauditor.utils.logging import logger


class JavaScriptBuildGuard:
    """
    Guards the integrity of the TypeScript extractor build.

    Pattern mirrors SchemaCodeGenerator.get_schema_hash() from codegen.py:
    - Explicit list of watched files (no directory walking with fallbacks)
    - Deterministic hash (sorted files, filename + content)
    - Hard fail on mismatch
    """

    def __init__(self, js_project_path: Path):
        """
        Initialize the build guard.

        Args:
            js_project_path: Absolute path to theauditor/ast_extractors/javascript
        """
        self.js_project_path = js_project_path
        self.dist_path = js_project_path / "dist"
        self.signature_file = self.dist_path / ".build_signature"
        self.artifact_file = self.dist_path / "extractor.cjs"

    def get_source_hash(self) -> str:
        """
        Calculate SHA256 hash of all source files.

        Mirrors SchemaCodeGenerator.get_schema_hash() - explicit file list,
        sorted, hash filename + content.
        """
        hasher = hashlib.sha256()

        watch_files = [
            self.js_project_path / "package.json",
            self.js_project_path / "tsconfig.json",
            self.js_project_path / "src" / "main.ts",
            self.js_project_path / "src" / "schema.ts",
            self.js_project_path / "src" / "types" / "index.ts",
            self.js_project_path / "src" / "extractors" / "angular_extractors.ts",
            self.js_project_path / "src" / "extractors" / "bullmq_extractors.ts",
            self.js_project_path / "src" / "extractors" / "cfg_extractor.ts",
            self.js_project_path / "src" / "extractors" / "core_language.ts",
            self.js_project_path / "src" / "extractors" / "data_flow.ts",
            self.js_project_path / "src" / "extractors" / "framework_extractors.ts",
            self.js_project_path / "src" / "extractors" / "module_framework.ts",
            self.js_project_path / "src" / "extractors" / "security_extractors.ts",
            self.js_project_path / "src" / "extractors" / "sequelize_extractors.ts",
            self.js_project_path / "src" / "fidelity.ts",
        ]

        for file_path in sorted(watch_files):
            hasher.update(file_path.name.encode())

            hasher.update(file_path.read_bytes())

        return hasher.hexdigest()

    def get_stored_signature(self) -> str | None:
        """Read the signature from the last successful build."""
        if not self.signature_file.exists():
            return None
        return self.signature_file.read_text().strip()

    def rebuild(self) -> None:
        """
        Trigger npm run build.

        NO FALLBACKS:
        - Does NOT check if node_modules exists first
        - If npm install needed, build will fail with clear error
        - User must run 'npm install' manually if needed
        """
        logger.error("[JS GUARD] TypeScript sources changed. Rebuilding extractor...")

        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"

        result = subprocess.run(
            [npm_cmd, "run", "build"],
            cwd=str(self.js_project_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        if result.returncode != 0:
            logger.error(f"[JS GUARD] Build FAILED (exit code {result.returncode})")
            logger.error(f"[JS GUARD] STDERR:\n{result.stderr}")
            logger.error(f"[JS GUARD] STDOUT:\n{result.stdout}")

            if "Cannot find module" in result.stderr or "node_modules" in result.stderr:
                logger.error(
                    "[JS GUARD] HINT: Run 'npm install' in theauditor/ast_extractors/javascript"
                )

            raise RuntimeError(
                f"JavaScript extractor build failed. Fix the error and re-run. "
                f"Exit code: {result.returncode}"
            )

        logger.error("[JS GUARD] Build successful.")

    def ensure_up_to_date(self) -> bool:
        """
        Main entry point. Check hash and rebuild if necessary.

        Returns:
            True if rebuild was triggered (caller should exit for re-import)
            False if already up-to-date

        Raises:
            RuntimeError: If build fails
            FileNotFoundError: If source files missing
        """

        current_hash = self.get_source_hash()

        if not self.artifact_file.exists():
            logger.error("[JS GUARD] Extractor artifact missing. Building...")
            self.rebuild()
            self.signature_file.write_text(current_hash)
            return True

        stored_hash = self.get_stored_signature()

        if current_hash != stored_hash:
            logger.debug(
                f"[JS GUARD] Hash mismatch. Current: {current_hash[:12]}..., "
                f"Stored: {stored_hash[:12] if stored_hash else 'None'}..."
            )

            self.rebuild()
            self.signature_file.write_text(current_hash)
            return True

        logger.debug("[JS GUARD] TypeScript extractor is up-to-date.")

        return False


def get_js_project_path() -> Path:
    """Get the absolute path to the JavaScript extractor project."""

    return (Path(__file__).parent.parent / "ast_extractors" / "javascript").resolve()
