"""Generic configuration file extractor (Database-First Gold Standard).

Nuclear Option Rewrite (v1.2): Complete elimination of parser abstraction layer.

This extractor handles configuration files with DIRECT database storage:
- Docker Compose files (docker-compose.yml) → compose_services table
- Nginx configurations (nginx.conf) → nginx_configs table
- Package manifests (package.json) → package_configs table

ARCHITECTURE:
- Database-First: Extracts directly to database via self.db_manager
- Zero Parsers: Inline YAML/JSON parsing, no external parser classes
- Zero Intermediate Dicts: No 'config_data' nesting, direct DB writes
- Zero Backward Compat: Clean slate, orphaned code eliminated

Replaces:
- compose_parser.py (deprecated)
- nginx_parser.py (deprecated)
- webpack_config_parser.py (deprecated)
- Old generic.py with HAS_CUSTOM_PARSERS flag (eliminated)
"""

import json
from pathlib import Path
from typing import Any

import yaml

from . import BaseExtractor

COMPOSE_FILE_PATTERNS: frozenset = frozenset(
    [
        "docker-compose.yml",
        "docker-compose.yaml",
        "docker-compose.override.yml",
        "docker-compose.override.yaml",
        "docker-compose.prod.yml",
        "docker-compose.prod.yaml",
        "docker-compose.dev.yml",
        "docker-compose.dev.yaml",
        "docker-compose.test.yml",
        "docker-compose.test.yaml",
    ]
)


NGINX_FILE_PATTERNS: frozenset = frozenset(
    [
        "nginx.conf",
        "default.conf",
        "site.conf",
    ]
)


PACKAGE_FILE_PATTERNS: frozenset = frozenset(
    [
        "package.json",
    ]
)


class GenericExtractor(BaseExtractor):
    """Extract config files directly to database (Gold Standard v1.2).

    NO parsers, NO intermediate dicts, NO backward compatibility.
    Direct YAML/JSON parsing → database storage.
    """

    def supported_extensions(self) -> list[str]:
        """This extractor handles files by name pattern, not extension."""
        return []

    def should_extract(self, file_path: str) -> bool:
        """Check if this extractor should handle the file.

        Uses frozenset O(1) lookup for performance.

        Args:
            file_path: Path to the file

        Returns:
            True if this extractor handles this config file type
        """
        file_name = Path(file_path).name.lower()

        return (
            file_name in COMPOSE_FILE_PATTERNS
            or file_name in NGINX_FILE_PATTERNS
            or file_name in PACKAGE_FILE_PATTERNS
            or file_name.endswith(".conf")
        )

    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract config file data directly to database.

        ARCHITECTURE CHANGE (v1.2 Nuclear Option):
        - OLD: Return nested dict → indexer unpacks → database
        - NEW: Call db_manager directly → no intermediate dict

        Returns minimal dict for indexer compatibility.
        Actual data flows directly to database via self.db_manager calls.

        Args:
            file_info: File metadata dictionary
            content: File content as string
            tree: Unused (configs don't have AST)

        Returns:
            Minimal dict for indexer (empty lists, no config_data nesting)
        """
        file_path_str = str(file_info["path"])
        file_name = Path(file_path_str).name.lower()

        if file_name in COMPOSE_FILE_PATTERNS:
            self._extract_compose_direct(file_path_str, content)

        elif file_name in NGINX_FILE_PATTERNS or file_name.endswith(".conf"):
            self._extract_nginx_direct(file_path_str, content)

        elif file_name in PACKAGE_FILE_PATTERNS:
            self._extract_package_direct(file_path_str, content)

        return {"imports": [], "routes": [], "sql_queries": [], "symbols": []}

    def _extract_compose_direct(self, file_path: str, content: str) -> None:
        """Extract Docker Compose services directly to database.

        Parses YAML inline, writes to compose_services table (17 fields).
        No intermediate dict, no parser abstraction.

        Args:
            file_path: Path to docker-compose.yml
            content: YAML content as string
        """
        try:
            compose_data = yaml.safe_load(content)
            if not compose_data or "services" not in compose_data:
                return

            services = compose_data.get("services", {})

            for service_name, service_config in services.items():
                if not isinstance(service_config, dict):
                    continue

                image = self._extract_image(service_config)
                ports = self._extract_ports(service_config)
                volumes = self._extract_volumes(service_config)
                environment = self._extract_environment(service_config)
                is_privileged = service_config.get("privileged", False)
                network_mode = service_config.get("network_mode", "bridge")

                user = service_config.get("user")
                cap_add = service_config.get("cap_add", [])
                cap_drop = service_config.get("cap_drop", [])
                security_opt = service_config.get("security_opt", [])
                restart = service_config.get("restart")
                command = service_config.get("command")
                entrypoint = service_config.get("entrypoint")
                depends_on = service_config.get("depends_on")
                healthcheck = service_config.get("healthcheck")

                if isinstance(command, str):
                    command = [command]
                if isinstance(entrypoint, str):
                    entrypoint = [entrypoint]

                if isinstance(depends_on, dict):
                    depends_on = list(depends_on.keys())

                if isinstance(user, int):
                    user = str(user)

                self.db_manager.add_compose_service(
                    file_path=file_path,
                    service_name=service_name,
                    image=image,
                    ports=ports,
                    volumes=volumes,
                    environment=environment,
                    is_privileged=is_privileged,
                    network_mode=network_mode,
                    user=user,
                    cap_add=cap_add if cap_add else None,
                    cap_drop=cap_drop if cap_drop else None,
                    security_opt=security_opt if security_opt else None,
                    restart=restart,
                    command=command,
                    entrypoint=entrypoint,
                    depends_on=depends_on,
                    healthcheck=healthcheck,
                )

        except (yaml.YAMLError, ValueError, TypeError):
            pass

    def _extract_image(self, config: dict[str, Any]) -> str | None:
        """Extract Docker image name from service config.

        Args:
            config: Service configuration dict

        Returns:
            Image name or None
        """
        image = config.get("image")
        if isinstance(image, str):
            return image

        if "build" in config:
            build_config = config["build"]
            if isinstance(build_config, str):
                return f"build:{build_config}"
            elif isinstance(build_config, dict):
                context = build_config.get("context", ".")
                return f"build:{context}"

        return None

    def _extract_ports(self, config: dict[str, Any]) -> list[str]:
        """Extract port mappings from service config.

        Handles both short syntax ("8080:80") and long syntax (target/published).

        Args:
            config: Service configuration dict

        Returns:
            List of port mapping strings
        """
        ports_raw = config.get("ports", [])
        if not isinstance(ports_raw, list):
            return []

        ports = []
        for port_def in ports_raw:
            if isinstance(port_def, str):
                ports.append(port_def)
            elif isinstance(port_def, dict):
                target = port_def.get("target", "")
                published = port_def.get("published", "")
                if target and published:
                    ports.append(f"{published}:{target}")
                elif target:
                    ports.append(str(target))

        return ports

    def _extract_volumes(self, config: dict[str, Any]) -> list[str]:
        """Extract volume mounts from service config.

        Handles both short syntax ("/host:/container") and long syntax (type/source/target).

        Args:
            config: Service configuration dict

        Returns:
            List of volume mount strings
        """
        volumes_raw = config.get("volumes", [])
        if not isinstance(volumes_raw, list):
            return []

        volumes = []
        for vol_def in volumes_raw:
            if isinstance(vol_def, str):
                volumes.append(vol_def)
            elif isinstance(vol_def, dict):
                # Long syntax: {type: bind, source: /host, target: /container}
                vol_type = vol_def.get("type", "volume")
                source = vol_def.get("source", "")
                target = vol_def.get("target", "")
                if source and target:
                    volumes.append(f"{source}:{target}")
                elif target:
                    volumes.append(f"{vol_type}:{target}")

        return volumes

    def _extract_environment(self, config: dict[str, Any]) -> dict[str, str]:
        """Extract environment variables from service config.

        Handles both list format ["KEY=value"] and dict format {KEY: value}.

        Args:
            config: Service configuration dict

        Returns:
            Dictionary of environment variables
        """
        env_raw = config.get("environment", {})

        if isinstance(env_raw, dict):
            return {k: str(v) for k, v in env_raw.items()}

        if isinstance(env_raw, list):
            env_dict = {}
            for item in env_raw:
                if isinstance(item, str) and "=" in item:
                    key, _, value = item.partition("=")
                    env_dict[key] = value
            return env_dict

        return {}

    def _extract_nginx_direct(self, file_path: str, content: str) -> None:
        """Extract Nginx config directly to database.

        MINIMAL IMPLEMENTATION: Only detects file presence, no deep parsing.

        Why minimal? nginx_parser.py uses recursive regex (cancer).
        Options for future:
        - Option A: Use pyparsing library (6-8 hours)
        - Option B: Execute nginx -T in sandbox (validate syntax only)
        - Option C: This minimal approach (rules handle security checks)

        Current: Option C - let rules query nginx_configs for presence only.

        Args:
            file_path: Path to nginx.conf
            content: Config content as string
        """

        self.db_manager.add_nginx_config(
            file_path=file_path,
            block_type="detected",
            block_context="minimal",
            directives={"status": "parsed_minimally", "reason": "regex_cancer_eliminated"},
            level=0,
        )

    def _extract_package_direct(self, file_path: str, content: str) -> None:
        """Extract package.json to package_configs table.

        Args:
            file_path: Path to package.json
            content: JSON content as string
        """
        try:
            pkg_data = json.loads(content)

            self.db_manager.add_package_config(
                file_path=file_path,
                package_name=pkg_data.get("name", "unknown"),
                version=pkg_data.get("version", "unknown"),
                dependencies=pkg_data.get("dependencies"),
                dev_dependencies=pkg_data.get("devDependencies"),
                peer_dependencies=pkg_data.get("peerDependencies"),
                scripts=pkg_data.get("scripts"),
                engines=pkg_data.get("engines"),
                workspaces=pkg_data.get("workspaces"),
                is_private=pkg_data.get("private", False),
            )

        except json.JSONDecodeError:
            pass
