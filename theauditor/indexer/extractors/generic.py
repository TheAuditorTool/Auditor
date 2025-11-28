"""Generic configuration file extractor (Database-First Gold Standard)."""

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
    """Extract config files directly to database (Gold Standard v1.2)."""

    def supported_extensions(self) -> list[str]:
        """This extractor handles files by name pattern, not extension."""
        return []

    def should_extract(self, file_path: str) -> bool:
        """Check if this extractor should handle the file."""
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
        """Extract config file data directly to database."""
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
        """Extract Docker Compose services to compose_services and junction tables."""
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

                depends_on_list = depends_on
                if isinstance(depends_on, dict):
                    depends_on_list = list(depends_on.keys())

                if isinstance(user, int):
                    user = str(user)

                self.db_manager.add_compose_service(
                    file_path=file_path,
                    service_name=service_name,
                    image=image,
                    is_privileged=is_privileged,
                    network_mode=network_mode,
                    user=user,
                    security_opt=security_opt if security_opt else None,
                    restart=restart,
                    command=command,
                    entrypoint=entrypoint,
                    healthcheck=healthcheck,
                )

                for port_mapping in ports or []:
                    parsed = self._parse_port_mapping(port_mapping)
                    if parsed:
                        self.db_manager.add_compose_service_port(
                            file_path=file_path,
                            service_name=service_name,
                            host_port=parsed.get("host_port"),
                            container_port=parsed["container_port"],
                            protocol=parsed.get("protocol", "tcp"),
                        )

                for volume_mapping in volumes or []:
                    parsed = self._parse_volume_mapping(volume_mapping)
                    if parsed:
                        self.db_manager.add_compose_service_volume(
                            file_path=file_path,
                            service_name=service_name,
                            host_path=parsed.get("host_path"),
                            container_path=parsed["container_path"],
                            mode=parsed.get("mode", "rw"),
                        )

                for var_name, var_value in (environment or {}).items():
                    self.db_manager.add_compose_service_env(
                        file_path=file_path,
                        service_name=service_name,
                        var_name=var_name,
                        var_value=str(var_value) if var_value is not None else None,
                    )

                for cap in cap_add or []:
                    self.db_manager.add_compose_service_capability(
                        file_path=file_path,
                        service_name=service_name,
                        capability=cap,
                        is_add=True,
                    )

                for cap in cap_drop or []:
                    self.db_manager.add_compose_service_capability(
                        file_path=file_path,
                        service_name=service_name,
                        capability=cap,
                        is_add=False,
                    )

                if depends_on:
                    deps_to_process = depends_on
                    if isinstance(depends_on, dict):
                        for dep_service, dep_config in depends_on.items():
                            condition = "service_started"
                            if isinstance(dep_config, dict):
                                condition = dep_config.get("condition", "service_started")
                            self.db_manager.add_compose_service_dep(
                                file_path=file_path,
                                service_name=service_name,
                                depends_on_service=dep_service,
                                condition=condition,
                            )
                    elif isinstance(depends_on, list):
                        for dep_service in depends_on:
                            self.db_manager.add_compose_service_dep(
                                file_path=file_path,
                                service_name=service_name,
                                depends_on_service=dep_service,
                                condition="service_started",
                            )

        except (yaml.YAMLError, ValueError, TypeError):
            pass

    def _parse_port_mapping(self, port_str: str) -> dict | None:
        """Parse a port mapping string into components."""
        if not port_str:
            return None
        port_str = str(port_str)

        protocol = "tcp"
        if "/" in port_str:
            port_str, protocol = port_str.rsplit("/", 1)

        if ":" in port_str:
            parts = port_str.split(":")

            if len(parts) == 2:
                try:
                    return {
                        "host_port": int(parts[0]) if parts[0] else None,
                        "container_port": int(parts[1]),
                        "protocol": protocol,
                    }
                except ValueError:
                    return None
            elif len(parts) == 3:
                try:
                    return {
                        "host_port": int(parts[1]) if parts[1] else None,
                        "container_port": int(parts[2]),
                        "protocol": protocol,
                    }
                except ValueError:
                    return None
        else:
            try:
                return {
                    "host_port": None,
                    "container_port": int(port_str),
                    "protocol": protocol,
                }
            except ValueError:
                return None
        return None

    def _parse_volume_mapping(self, volume_str: str) -> dict | None:
        """Parse a volume mapping string into components."""
        if not volume_str:
            return None
        volume_str = str(volume_str)

        if ":" not in volume_str:
            return {"host_path": None, "container_path": volume_str, "mode": "rw"}

        parts = volume_str.split(":")
        if len(parts) == 2:
            return {"host_path": parts[0], "container_path": parts[1], "mode": "rw"}
        elif len(parts) >= 3:
            return {"host_path": parts[0], "container_path": parts[1], "mode": parts[2]}
        return None

    def _extract_image(self, config: dict[str, Any]) -> str | None:
        """Extract Docker image name from service config."""
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
        """Extract port mappings from service config."""
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
        """Extract volume mounts from service config."""
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
        """Extract environment variables from service config."""
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
        """Extract Nginx config directly to database."""

        self.db_manager.add_nginx_config(
            file_path=file_path,
            block_type="detected",
            block_context="minimal",
            directives={"status": "parsed_minimally", "reason": "regex_cancer_eliminated"},
            level=0,
        )

    def _extract_package_direct(self, file_path: str, content: str) -> None:
        """Extract package.json to package_configs and junction tables."""
        try:
            pkg_data = json.loads(content)

            self.db_manager.add_package_config(
                file_path=file_path,
                package_name=pkg_data.get("name", "unknown"),
                version=pkg_data.get("version", "unknown"),
                is_private=pkg_data.get("private", False),
            )

            deps = pkg_data.get("dependencies") or {}
            for name, version_spec in deps.items():
                self.db_manager.add_package_dependency(
                    file_path=file_path,
                    name=name,
                    version_spec=version_spec,
                    is_dev=False,
                    is_peer=False,
                )

            dev_deps = pkg_data.get("devDependencies") or {}
            for name, version_spec in dev_deps.items():
                self.db_manager.add_package_dependency(
                    file_path=file_path,
                    name=name,
                    version_spec=version_spec,
                    is_dev=True,
                    is_peer=False,
                )

            peer_deps = pkg_data.get("peerDependencies") or {}
            for name, version_spec in peer_deps.items():
                self.db_manager.add_package_dependency(
                    file_path=file_path,
                    name=name,
                    version_spec=version_spec,
                    is_dev=False,
                    is_peer=True,
                )

            scripts = pkg_data.get("scripts") or {}
            for script_name, script_command in scripts.items():
                self.db_manager.add_package_script(
                    file_path=file_path,
                    script_name=script_name,
                    script_command=script_command,
                )

            engines = pkg_data.get("engines") or {}
            for engine_name, version_spec in engines.items():
                self.db_manager.add_package_engine(
                    file_path=file_path,
                    engine_name=engine_name,
                    version_spec=version_spec,
                )

            workspaces = pkg_data.get("workspaces") or []
            if isinstance(workspaces, dict):
                workspaces = workspaces.get("packages", [])
            for workspace_path in workspaces:
                self.db_manager.add_package_workspace(
                    file_path=file_path,
                    workspace_path=workspace_path,
                )

        except json.JSONDecodeError:
            pass
