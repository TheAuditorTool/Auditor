"""Docker package manager implementation.

Handles Docker Compose files and Dockerfiles for:
- Parsing base image dependencies
- Fetching latest tags from Docker Hub
- Upgrading image versions
"""

from __future__ import annotations

import platform
import re
from pathlib import Path
from typing import Any

import yaml

from theauditor import __version__
from theauditor.pipeline.ui import console

from .base import BasePackageManager, Dependency

IS_WINDOWS = platform.system() == "Windows"


def _validate_docker_name(name: str) -> bool:
    """Validate Docker image name format."""
    if not name or len(name) > 214:
        return False
    return bool(re.match(r"^[a-z0-9][\w./:-]*$", name))


class DockerPackageManager(BasePackageManager):
    """Docker package manager for docker-compose.yml and Dockerfile."""

    @property
    def manager_name(self) -> str:
        return "docker"

    @property
    def file_patterns(self) -> list[str]:
        return ["docker-compose*.yml", "docker-compose*.yaml", "Dockerfile*"]

    @property
    def registry_url(self) -> str | None:
        return "https://hub.docker.com/v2/repositories/"

    def parse_manifest(self, path: Path) -> list[Dependency]:
        """Parse Docker manifest file (compose or Dockerfile).

        Args:
            path: Path to docker-compose.yml or Dockerfile

        Returns:
            List of Dependency objects with guaranteed structure.
        """
        file_name = path.name.lower()

        if file_name.startswith("docker-compose"):
            return self._parse_docker_compose(path)
        elif file_name.startswith("dockerfile"):
            return self._parse_dockerfile(path)

        return []

    def _parse_docker_compose(self, path: Path) -> list[Dependency]:
        """Parse Docker base images from docker-compose.yml files."""
        deps: list[Dependency] = []

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or "services" not in data:
            return deps

        for _service_name, service_config in data["services"].items():
            if not isinstance(service_config, dict):
                continue

            if "image" in service_config:
                image_spec = service_config["image"]

                if ":" in image_spec:
                    name, tag = image_spec.rsplit(":", 1)
                else:
                    name = image_spec
                    tag = "latest"

                name = self._normalize_image_name(name)

                deps.append(
                    Dependency(
                        name=name,
                        version=tag,
                        manager="docker",
                        source=path.name,
                    )
                )

        return deps

    def _parse_dockerfile(self, path: Path) -> list[Dependency]:
        """Parse Docker base images from Dockerfile."""
        deps: list[Dependency] = []
        stages: set[str] = set()

        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if line.upper().startswith("FROM "):
                    parts = line[5:].strip().split()
                    image_part = parts[0]

                    if image_part in stages:
                        continue

                    if len(parts) >= 3 and parts[1].upper() == "AS":
                        stages.add(parts[2])

                    if image_part.lower() == "scratch":
                        continue

                    if ":" in image_part:
                        name, tag = image_part.rsplit(":", 1)
                    else:
                        name = image_part
                        tag = "latest"

                    name = self._normalize_image_name(name)

                    try:
                        source = str(path.resolve().relative_to(Path.cwd()))
                    except ValueError:
                        source = str(path)

                    deps.append(
                        Dependency(
                            name=name,
                            version=tag,
                            manager="docker",
                            source=source,
                        )
                    )

        return deps

    def _normalize_image_name(self, name: str) -> str:
        """Normalize Docker image name (handle library/ prefix)."""
        if "/" in name:
            name_parts = name.split("/")
            if len(name_parts) >= 2:
                if name_parts[-2] == "library":
                    return name_parts[-1]
                return "/".join(name_parts[-2:])
        return name

    async def fetch_latest_async(
        self,
        client: Any,
        dep: Dependency,
        allow_prerelease: bool = False,
    ) -> str | None:
        """Fetch latest Docker tag from Docker Hub.

        Args:
            client: httpx.AsyncClient instance
            dep: Dependency object
            allow_prerelease: Include pre-release versions

        Returns:
            Latest tag string or None
        """
        name = dep.name
        current_tag = dep.version

        if not _validate_docker_name(name):
            return None

        if "/" not in name:
            name = f"library/{name}"

        url = f"https://hub.docker.com/v2/repositories/{name}/tags?page_size=100"

        resp = await client.get(url, headers={"User-Agent": f"TheAuditor/{__version__}"})
        if resp.status_code != 200:
            return None

        data = resp.json()
        tags = data.get("results", [])
        if not tags:
            return None

        parsed_tags = []
        for tag in tags:
            tag_name = tag.get("name", "")
            parsed = self._parse_docker_tag(tag_name)
            if parsed:
                parsed_tags.append(parsed)

        if not parsed_tags:
            return None

        if allow_prerelease:
            candidates = parsed_tags
        else:
            candidates = [t for t in parsed_tags if t["stability"] == "stable"]
            if not candidates:
                return None

        if current_tag:
            base_preference = self._extract_base_preference(current_tag)
            if base_preference:
                matching_base = [t for t in candidates if base_preference in t["variant"].lower()]
                if matching_base:
                    candidates = matching_base
                else:
                    return None

        candidates.sort(key=lambda x: (x["version"], x["is_clean"], -len(x["tag"])), reverse=True)

        return candidates[0]["tag"] if candidates else None

    async def fetch_docs_async(
        self,
        client: Any,
        dep: Dependency,
        output_path: Path,
        allowlist: list[str],
    ) -> str:
        """Fetch documentation for Docker images.

        Note: Docker Hub doesn't provide comprehensive docs API,
        so we skip docs fetching for Docker images.

        Returns:
            Always returns 'skipped' for Docker
        """
        return "skipped"

    def upgrade_file(
        self,
        path: Path,
        latest_info: dict[str, dict[str, Any]],
        deps: list[Dependency],
    ) -> int:
        """Upgrade Docker manifest to latest versions.

        Note: Caller is responsible for creating backup before calling.

        Args:
            path: Path to manifest file
            latest_info: Dict mapping dep keys to version info
            deps: List of Dependency objects

        Returns:
            Count of dependencies upgraded
        """
        file_name = path.name.lower()

        if file_name.startswith("docker-compose"):
            return self._upgrade_docker_compose(path, latest_info, deps)
        elif file_name.startswith("dockerfile"):
            return self._upgrade_dockerfile(path, latest_info, deps)

        return 0

    def _upgrade_docker_compose(
        self,
        path: Path,
        latest_info: dict[str, dict[str, Any]],
        deps: list[Dependency],
    ) -> int:
        """Upgrade docker-compose.yml to latest Docker image versions."""
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()

        latest_versions = {}
        for dep in deps:
            key = f"docker:{dep.name}:{dep.version}"
            if key in latest_info and latest_info[key]["latest"] is not None:
                latest_versions[dep.name] = latest_info[key]["latest"]

        updated_lines = []
        count = 0
        updated_images = {}

        for line in lines:
            original_line = line
            stripped = line.strip()

            if stripped.startswith("image:"):
                image_spec = stripped[6:].strip()

                if ":" in image_spec:
                    name_part, tag = image_spec.rsplit(":", 1)

                    if "$" in tag or "{" in tag:
                        updated_lines.append(original_line)
                        continue

                    base_name = self._normalize_image_name(name_part)

                    if base_name in latest_versions:
                        new_tag = latest_versions[base_name]
                        old_tag = tag

                        if new_tag is not None and old_tag != new_tag:
                            old_parsed = self._parse_docker_tag(old_tag)
                            new_parsed = self._parse_docker_tag(new_tag)
                            if (
                                old_parsed
                                and new_parsed
                                and new_parsed["version"] <= old_parsed["version"]
                            ):
                                updated_lines.append(original_line)
                                continue

                            updated_images[base_name] = (old_tag, new_tag)

                            new_image_spec = f"{name_part}:{new_tag}"
                            indent = len(line) - len(line.lstrip())
                            updated_lines.append(" " * indent + f"image: {new_image_spec}\n")
                            count += 1
                        else:
                            updated_lines.append(original_line)
                    else:
                        updated_lines.append(original_line)
                else:
                    updated_lines.append(original_line)
            else:
                updated_lines.append(original_line)

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(updated_lines)

        check_mark = "[OK]" if IS_WINDOWS else "[OK]"
        arrow = "->" if IS_WINDOWS else "->"
        for image, (old_tag, new_tag) in updated_images.items():
            console.print(f"  {check_mark} {image}: {old_tag} {arrow} {new_tag}", highlight=False)

        return count

    def _upgrade_dockerfile(
        self,
        path: Path,
        latest_info: dict[str, dict[str, Any]],
        deps: list[Dependency],
    ) -> int:
        """Upgrade Dockerfile to latest Docker base image versions."""
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()

        latest_versions = {}
        for dep in deps:
            key = f"docker:{dep.name}:{dep.version}"
            if key in latest_info and latest_info[key]["latest"] is not None:
                latest_versions[dep.name] = latest_info[key]["latest"]

        updated_lines = []
        count = 0
        updated_images = {}

        for line in lines:
            original_line = line
            stripped = line.strip().upper()

            if stripped.startswith("FROM "):
                image_spec = line[5:].strip()

                if " AS " in image_spec.upper():
                    image_part, as_part = image_spec.split(" AS ", 1)
                    image_spec = image_part.strip()
                    as_clause = f" AS {as_part}"
                elif " as " in image_spec:
                    image_part, as_part = image_spec.split(" as ", 1)
                    image_spec = image_part.strip()
                    as_clause = f" as {as_part}"
                else:
                    as_clause = ""

                if image_spec.lower() in ["scratch", "builder"]:
                    updated_lines.append(original_line)
                    continue

                if ":" in image_spec:
                    name_part, tag = image_spec.rsplit(":", 1)

                    if "$" in tag or "{" in tag:
                        updated_lines.append(original_line)
                        continue

                    base_name = self._normalize_image_name(name_part)

                    if base_name in latest_versions:
                        new_tag = latest_versions[base_name]
                        old_tag = tag

                        if new_tag is not None and old_tag != new_tag:
                            old_parsed = self._parse_docker_tag(old_tag)
                            new_parsed = self._parse_docker_tag(new_tag)
                            if (
                                old_parsed
                                and new_parsed
                                and new_parsed["version"] <= old_parsed["version"]
                            ):
                                updated_lines.append(original_line)
                                continue

                            updated_images[base_name] = (old_tag, new_tag)

                            new_image_spec = f"{name_part}:{new_tag}"
                            updated_lines.append(f"FROM {new_image_spec}{as_clause}\n")
                            count += 1
                        else:
                            updated_lines.append(original_line)
                    else:
                        updated_lines.append(original_line)
                else:
                    updated_lines.append(original_line)
            else:
                updated_lines.append(original_line)

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(updated_lines)

        check_mark = "[OK]" if IS_WINDOWS else "[OK]"
        arrow = "->" if IS_WINDOWS else "->"
        for image, (old_tag, new_tag) in updated_images.items():
            console.print(f"  {check_mark} {image}: {old_tag} {arrow} {new_tag}", highlight=False)

        return count

    def _parse_docker_tag(self, tag: str) -> dict[str, Any] | None:
        """Parse Docker tag into semantic components for proper version comparison."""
        if tag in ["latest", "alpine", "slim", "bullseye", "bookworm", "main", "master"]:
            return None

        clean_tag = tag[1:] if tag.startswith("v") else tag

        match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", clean_tag)
        if not match:
            return None

        major = int(match.group(1))
        minor = int(match.group(2) or 0)
        patch = int(match.group(3) or 0)

        variant = clean_tag[match.end() :].lstrip("-")

        return {
            "tag": tag,
            "version": (major, minor, patch),
            "variant": variant,
            "stability": self._detect_stability(variant),
            "is_clean": len(variant) == 0,
        }

    def _extract_base_preference(self, current_tag: str) -> str:
        """Extract base image preference from current tag."""
        tag_lower = current_tag.lower()

        base_types = [
            "windowsservercore",
            "nanoserver",
            "alpine",
            "slim",
            "distroless",
            "bookworm",
            "bullseye",
            "buster",
            "jammy",
            "focal",
            "bionic",
            "trixie",
            "sid",
        ]

        for base in base_types:
            if base in tag_lower:
                return base

        return ""

    def _detect_stability(self, variant: str) -> str:
        """Detect stability level from Docker tag variant.

        Args:
            variant: The variant suffix after version (e.g., 'alpine', 'rc1', 'beta')

        Returns:
            Stability level: 'stable', 'rc', 'beta', 'alpha', or 'dev'
        """
        v = variant.lower()

        if re.search(r"\d{8,}", v):
            return "dev"

        if any(m in v for m in ("nightly", "dev", "snapshot", "edge")):
            return "dev"

        if "rc" in v:
            return "rc"

        debian_b = ("bookworm", "bullseye", "buster")
        if ("beta" in v or re.match(r"b\d", v)) and not any(v.startswith(d) for d in debian_b):
            return "beta"

        if ("alpha" in v or re.match(r"a\d", v)) and not v.startswith("alpine"):
            return "alpha"

        return "stable"
