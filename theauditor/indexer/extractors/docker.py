"""Docker file extractor - Fidelity Protocol Compliant."""

from pathlib import Path
from typing import Any

from dockerfile_parse import DockerfileParser as DFParser

from theauditor.utils.logging import logger

from ..fidelity_utils import FidelityToken
from . import BaseExtractor


class DockerExtractor(BaseExtractor):
    """Extractor for Dockerfile files."""

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return []

    def should_extract(self, file_path: str) -> bool:
        """Check if this extractor should handle the file."""
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
        """Extract facts from Dockerfile and return data dict with manifest."""
        file_path_str = str(file_info["path"])

        result: dict[str, Any] = {
            "docker_images": [],
            "dockerfile_ports": [],
            "dockerfile_env_vars": [],
            "dockerfile_instructions": [],
        }

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
                inst_line = instruction.get("startline", 1)

                result["dockerfile_instructions"].append(
                    {
                        "file_path": file_path_str,
                        "line": inst_line,
                        "instruction": inst_type,
                        "arguments": inst_value,
                    }
                )

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

            result["docker_images"].append(
                {
                    "file_path": file_path_str,
                    "base_image": base_image,
                    "user": user,
                    "has_healthcheck": has_healthcheck,
                }
            )

            seen_ports: set[tuple[int, str]] = set()
            for port_str in exposed_ports:
                port_str = str(port_str)
                protocol = "tcp"
                if "/" in port_str:
                    port_str, protocol = port_str.split("/", 1)
                try:
                    port_num = int(port_str)
                    port_key = (port_num, protocol)
                    if port_key not in seen_ports:
                        seen_ports.add(port_key)
                        result["dockerfile_ports"].append(
                            {
                                "file_path": file_path_str,
                                "port": port_num,
                                "protocol": protocol,
                            }
                        )
                except ValueError:
                    pass

            for var_name, var_value in env_vars.items():
                if var_name == "_DOCKER_USER":
                    continue
                result["dockerfile_env_vars"].append(
                    {
                        "file_path": file_path_str,
                        "var_name": var_name,
                        "var_value": str(var_value) if var_value else None,
                        "is_build_arg": False,
                    }
                )

            for arg_name, arg_value in build_args.items():
                result["dockerfile_env_vars"].append(
                    {
                        "file_path": file_path_str,
                        "var_name": arg_name,
                        "var_value": str(arg_value) if arg_value else None,
                        "is_build_arg": True,
                    }
                )

        except Exception as e:
            logger.error(f"Failed to parse Dockerfile {file_path_str}: {e}")

        return FidelityToken.attach_manifest(result)
