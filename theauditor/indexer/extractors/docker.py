"""Docker file extractor - Database-First Architecture.

Extracts facts from Dockerfiles directly to database.
NO security checks (that's what rules do).
NO separate parser class (inline parsing).

Follows gold standard: Facts only, direct DB writes, no intermediate dicts.
"""

from pathlib import Path
from typing import Any

from . import BaseExtractor


class DockerExtractor(BaseExtractor):
    """Extractor for Dockerfile files.

    Extracts FACTS ONLY:
    - Base image
    - Environment variables
    - Build arguments
    - User instruction
    - Healthcheck presence
    - Exposed ports

    Security checks are performed by rules/deployment/docker_analyze.py.
    """

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports.

        Note: Dockerfiles don't have extensions, we match by filename.
        """
        return []

    def should_extract(self, file_path: str) -> bool:
        """Check if this extractor should handle the file.

        Args:
            file_path: Path to the file

        Returns:
            True if this is a Dockerfile
        """
        file_name_lower = Path(file_path).name.lower()
        dockerfile_patterns = [
            "dockerfile",
            "dockerfile.dev",
            "dockerfile.prod",
            "dockerfile.test",
            "dockerfile.staging",
        ]
        return file_name_lower in dockerfile_patterns or file_name_lower.startswith("dockerfile.")

    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract facts from Dockerfile directly to database.

        Uses external dockerfile-parse library for parsing.
        Extracts to docker_images table via self.db_manager.

        Args:
            file_info: File metadata dictionary
            content: File content
            tree: Optional pre-parsed AST tree (not used for Docker)

        Returns:
            Minimal dict for indexer compatibility
        """

        try:
            from dockerfile_parse import DockerfileParser as DFParser
        except ImportError:
            return {}

        try:
            parser = DFParser()
            parser.content = content

            base_image = parser.baseimage if parser.baseimage else None

            env_vars = {}
            build_args = {}
            user = None
            has_healthcheck = False
            exposed_ports = []

            for instruction in parser.structure:
                inst_type = instruction.get("instruction", "").upper()
                inst_value = instruction.get("value", "")

                if inst_type == "ENV":
                    if "=" in inst_value:
                        parts = inst_value.split()
                        for part in parts:
                            if "=" in part:
                                key, value = part.split("=", 1)
                                env_vars[key.strip()] = value.strip()
                    else:
                        parts = inst_value.split(None, 1)
                        if len(parts) == 2:
                            env_vars[parts[0].strip()] = parts[1].strip()

                elif inst_type == "ARG":
                    if "=" in inst_value:
                        key, value = inst_value.split("=", 1)
                        build_args[key.strip()] = value.strip()
                    else:
                        build_args[inst_value.strip()] = None

                elif inst_type == "USER":
                    user = inst_value.strip()

                elif inst_type == "HEALTHCHECK":
                    has_healthcheck = True

                elif inst_type == "EXPOSE":
                    ports = inst_value.split()
                    exposed_ports.extend(ports)

            if user:
                env_vars["_DOCKER_USER"] = user

            self.db_manager.add_docker_image(
                file_path=str(file_info["path"]),
                base_image=base_image,
                ports=exposed_ports if exposed_ports else [],
                env_vars=env_vars,
                build_args=build_args,
                user=user,
                has_healthcheck=has_healthcheck,
            )

        except Exception:
            pass

        return {}
