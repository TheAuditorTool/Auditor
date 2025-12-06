"""Docker Compose Security Analyzer - Database-First Approach.

Detects security misconfigurations in Docker Compose files:
- Privileged containers (CWE-250)
- Host network mode (CWE-668)
- Docker socket mounts (CWE-552)
- Dangerous volume mounts (CWE-552)
- Hardcoded secrets (CWE-798)
- Weak passwords (CWE-521)
- Exposed database/admin ports (CWE-668)
- Vulnerable/unpinned images (CWE-937, CWE-1104)
- Root user execution (CWE-250)
- Dangerous capabilities (CWE-250)
- Disabled security features (CWE-693)
- Command injection risks (CWE-78)
- Missing healthcheck (CWE-1188)
- Missing restart policy (CWE-1188)
- Missing resource limits (CWE-400)
- Writable root filesystem (CWE-1188)
"""

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="compose_security",
    category="deployment",
    target_extensions=[],
    exclude_patterns=["test/", "__tests__/", "node_modules/", ".pf/", ".auditor_venv/"],
    execution_scope="database",
    primary_table="compose_services",
)


SENSITIVE_ENV_PATTERNS = frozenset(
    [
        "PASSWORD",
        "PASS",
        "PWD",
        "SECRET",
        "TOKEN",
        "KEY",
        "API_KEY",
        "ACCESS_KEY",
        "PRIVATE",
        "CREDENTIAL",
        "AUTH",
        "MYSQL_ROOT_PASSWORD",
        "POSTGRES_PASSWORD",
        "MONGO_INITDB_ROOT_PASSWORD",
        "REDIS_PASSWORD",
        "RABBITMQ_DEFAULT_PASS",
        "ELASTIC_PASSWORD",
    ]
)


WEAK_PASSWORDS = frozenset(
    [
        "password",
        "123456",
        "admin",
        "root",
        "test",
        "demo",
        "secret",
        "changeme",
        "password123",
        "admin123",
        "letmein",
        "welcome",
        "monkey",
        "dragon",
        "master",
        "qwerty",
        "abc123",
        "iloveyou",
        "password1",
        "sunshine",
    ]
)


DATABASE_PORTS = {
    3306: "MySQL",
    5432: "PostgreSQL",
    27017: "MongoDB",
    6379: "Redis",
    5984: "CouchDB",
    8086: "InfluxDB",
    9042: "Cassandra",
    7000: "Cassandra Inter-node",
    7001: "Cassandra TLS",
    9200: "Elasticsearch",
    9300: "Elasticsearch Transport",
    2181: "Zookeeper",
    9092: "Kafka",
    1433: "SQL Server",
    1521: "Oracle",
    3307: "MariaDB",
    5601: "Kibana",
    15672: "RabbitMQ Management",
    5672: "RabbitMQ",
    8529: "ArangoDB",
    28015: "RethinkDB",
}


ADMIN_PORTS = {
    8080: "Admin Panel",
    8081: "Admin Interface",
    9090: "Prometheus",
    3000: "Grafana",
    15672: "RabbitMQ Management",
    5601: "Kibana",
    8161: "ActiveMQ Admin",
    7077: "Spark Master",
    8088: "YARN ResourceManager",
    9870: "HDFS NameNode",
    16010: "HBase Master",
}


DANGEROUS_MOUNTS = frozenset(
    [
        "docker.sock",
        "/var/run/docker.sock",
        "/etc/shadow",
        "/etc/passwd",
        "/root",
        "/.ssh",
        "/proc",
        "/sys",
        "/dev",
    ]
)


VULNERABLE_IMAGES = {
    "elasticsearch:2": "EOL - upgrade to 7.x or 8.x",
    "elasticsearch:5": "EOL - upgrade to 7.x or 8.x",
    "mysql:5.6": "EOL - upgrade to 8.0",
    "postgres:9": "EOL - upgrade to 14+",
    "mongo:3": "EOL - upgrade to 5.0+",
    "redis:3": "EOL - upgrade to 7.0+",
    "node:8": "EOL - upgrade to 18+",
    "node:10": "EOL - upgrade to 18+",
    "node:12": "EOL - upgrade to 18+",
    "python:2": "EOL - upgrade to Python 3.9+",
    "ruby:2.4": "EOL - upgrade to 3.0+",
    "php:5": "EOL - upgrade to 8.0+",
    "php:7.0": "EOL - upgrade to 8.0+",
    "php:7.1": "EOL - upgrade to 8.0+",
    "php:7.2": "EOL - upgrade to 8.0+",
}


DANGEROUS_CAPABILITIES = frozenset(
    [
        "SYS_ADMIN",
        "NET_ADMIN",
        "SYS_PTRACE",
        "SYS_MODULE",
        "DAC_OVERRIDE",
        "DAC_READ_SEARCH",
        "SYS_RAWIO",
        "SYS_BOOT",
        "SYS_TIME",
        "SYS_RESOURCE",
    ]
)


INSECURE_SECURITY_OPTS = frozenset(
    [
        "apparmor=unconfined",
        "apparmor:unconfined",
        "seccomp=unconfined",
        "seccomp:unconfined",
        "label=disable",
        "label:disable",
    ]
)


SHELL_METACHARACTERS = frozenset(
    [";", "&", "|", "$", "`", "\n", ">", "<", "*", "?", "[", "]", "{", "}", "(", ")"]
)


ROOT_USER_IDS = frozenset(["root", "0"])


def find_compose_issues(context: StandardRuleContext) -> RuleResult:
    """Detect Docker Compose security misconfigurations using indexed data."""
    findings = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        services = _load_services(db)
        ports_by_service = _load_ports(db)
        volumes_by_service = _load_volumes(db)
        env_by_service = _load_environment(db)
        caps_by_service = _load_capabilities(db)

        for service_key, service_data in services.items():
            file_path, service_name = service_key

            ports = ports_by_service.get(service_key, [])
            volumes = volumes_by_service.get(service_key, [])
            environment = env_by_service.get(service_key, {})
            cap_add, cap_drop = caps_by_service.get(service_key, ([], []))

            service_findings = _analyze_service(
                file_path=file_path,
                service_name=service_name,
                service_data=service_data,
                ports=ports,
                volumes=volumes,
                environment=environment,
                cap_add=cap_add,
                cap_drop=cap_drop,
            )
            findings.extend(service_findings)

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _load_services(db: RuleDB) -> dict[tuple[str, str], dict]:
    """Load all compose services into a dictionary keyed by (file_path, service_name)."""
    services = {}

    rows = db.query(
        Q("compose_services")
        .select(
            "file_path",
            "service_name",
            "image",
            "is_privileged",
            "network_mode",
            "user",
            "security_opt",
            "restart",
            "command",
            "entrypoint",
            "healthcheck",
            "mem_limit",
            "cpus",
            "read_only",
        )
        .order_by("file_path, service_name")
    )

    for row in rows:
        (
            file_path,
            service_name,
            image,
            is_privileged,
            network_mode,
            user,
            security_opt,
            restart,
            command,
            entrypoint,
            healthcheck,
            mem_limit,
            cpus,
            read_only,
        ) = row
        services[(file_path, service_name)] = {
            "image": image,
            "is_privileged": bool(is_privileged),
            "network_mode": network_mode,
            "user": user,
            "security_opt": security_opt,
            "restart": restart,
            "command": command,
            "entrypoint": entrypoint,
            "healthcheck": healthcheck,
            "mem_limit": mem_limit,
            "cpus": cpus,
            "read_only": bool(read_only),
        }

    return services


def _load_ports(db: RuleDB) -> dict[tuple[str, str], list[dict]]:
    """Load all port mappings grouped by service."""
    ports_by_service = {}

    rows = db.query(
        Q("compose_service_ports").select(
            "file_path", "service_name", "host_port", "container_port", "protocol"
        )
    )

    for file_path, service_name, host_port, container_port, protocol in rows:
        key = (file_path, service_name)
        if key not in ports_by_service:
            ports_by_service[key] = []
        ports_by_service[key].append(
            {
                "host_port": host_port,
                "container_port": container_port,
                "protocol": protocol,
            }
        )

    return ports_by_service


def _load_volumes(db: RuleDB) -> dict[tuple[str, str], list[dict]]:
    """Load all volume mounts grouped by service."""
    volumes_by_service = {}

    rows = db.query(
        Q("compose_service_volumes").select(
            "file_path", "service_name", "host_path", "container_path", "mode"
        )
    )

    for file_path, service_name, host_path, container_path, mode in rows:
        key = (file_path, service_name)
        if key not in volumes_by_service:
            volumes_by_service[key] = []
        volumes_by_service[key].append(
            {
                "host_path": host_path,
                "container_path": container_path,
                "mode": mode,
            }
        )

    return volumes_by_service


def _load_environment(db: RuleDB) -> dict[tuple[str, str], dict[str, str]]:
    """Load all environment variables grouped by service."""
    env_by_service = {}

    rows = db.query(
        Q("compose_service_env").select("file_path", "service_name", "var_name", "var_value")
    )

    for file_path, service_name, var_name, var_value in rows:
        key = (file_path, service_name)
        if key not in env_by_service:
            env_by_service[key] = {}
        env_by_service[key][var_name] = var_value

    return env_by_service


def _load_capabilities(db: RuleDB) -> dict[tuple[str, str], tuple[list[str], list[str]]]:
    """Load all capabilities grouped by service, split into add/drop lists."""
    caps_by_service = {}

    rows = db.query(
        Q("compose_service_capabilities").select(
            "file_path", "service_name", "capability", "is_add"
        )
    )

    for file_path, service_name, capability, is_add in rows:
        key = (file_path, service_name)
        if key not in caps_by_service:
            caps_by_service[key] = ([], [])

        cap_add, cap_drop = caps_by_service[key]
        if is_add:
            cap_add.append(capability)
        else:
            cap_drop.append(capability)

    return caps_by_service


def _analyze_service(
    file_path: str,
    service_name: str,
    service_data: dict,
    ports: list[dict],
    volumes: list[dict],
    environment: dict[str, str],
    cap_add: list[str],
    cap_drop: list[str],
) -> list[StandardFinding]:
    """Analyze a single Docker Compose service for security issues."""
    findings = []

    image = service_data.get("image")
    is_privileged = service_data.get("is_privileged", False)
    network_mode = service_data.get("network_mode")
    user = service_data.get("user")
    security_opt = service_data.get("security_opt")
    command = service_data.get("command")
    entrypoint = service_data.get("entrypoint")

    if is_privileged:
        findings.append(
            StandardFinding(
                rule_name="compose-privileged-container",
                message=f'Service "{service_name}" runs in privileged mode',
                file_path=file_path,
                line=1,
                severity=Severity.CRITICAL,
                category="security",
                snippet=f"{service_name}:\n  privileged: true",
                cwe_id="CWE-250",
            )
        )

    if network_mode == "host":
        findings.append(
            StandardFinding(
                rule_name="compose-host-network",
                message=f'Service "{service_name}" uses host network mode',
                file_path=file_path,
                line=1,
                severity=Severity.HIGH,
                category="security",
                snippet=f"{service_name}:\n  network_mode: host",
                cwe_id="CWE-668",
            )
        )

    for vol in volumes:
        host_path = vol.get("host_path") or ""
        container_path = vol.get("container_path") or ""
        vol_str = f"{host_path}:{container_path}" if host_path else container_path

        for dangerous_mount in DANGEROUS_MOUNTS:
            if dangerous_mount in host_path or dangerous_mount in container_path:
                if "docker.sock" in host_path or "docker.sock" in container_path:
                    findings.append(
                        StandardFinding(
                            rule_name="compose-docker-socket",
                            message=f'Service "{service_name}" mounts Docker socket - container escape risk',
                            file_path=file_path,
                            line=1,
                            severity=Severity.CRITICAL,
                            category="security",
                            snippet=f"volumes:\n  - {vol_str}",
                            cwe_id="CWE-552",
                        )
                    )
                else:
                    findings.append(
                        StandardFinding(
                            rule_name="compose-dangerous-mount",
                            message=f'Service "{service_name}" mounts sensitive host path: {dangerous_mount}',
                            file_path=file_path,
                            line=1,
                            severity=Severity.HIGH,
                            category="security",
                            snippet=f"volumes:\n  - {vol_str}",
                            cwe_id="CWE-552",
                        )
                    )
                break

    for key, value in environment.items():
        if value:
            key_upper = key.upper()
            is_sensitive = any(pattern in key_upper for pattern in SENSITIVE_ENV_PATTERNS)

            if is_sensitive:
                if not value.startswith("${") and not value.startswith("$"):
                    if value.lower() in WEAK_PASSWORDS:
                        findings.append(
                            StandardFinding(
                                rule_name="compose-weak-password",
                                message=f'Service "{service_name}" uses weak password in {key}',
                                file_path=file_path,
                                line=1,
                                severity=Severity.CRITICAL,
                                category="security",
                                snippet=f"{key}=***",
                                cwe_id="CWE-521",
                            )
                        )
                    else:
                        findings.append(
                            StandardFinding(
                                rule_name="compose-hardcoded-secret",
                                message=f'Service "{service_name}" has hardcoded secret: {key}',
                                file_path=file_path,
                                line=1,
                                severity=Severity.HIGH,
                                category="security",
                                snippet=f"{key}=***",
                                cwe_id="CWE-798",
                            )
                        )

    for port_info in ports:
        host_port = port_info.get("host_port")
        container_port = port_info.get("container_port")

        if host_port is not None and container_port:
            if container_port in DATABASE_PORTS:
                db_type = DATABASE_PORTS[container_port]
                findings.append(
                    StandardFinding(
                        rule_name="compose-database-exposed",
                        message=f'Service "{service_name}" exposes {db_type} port {container_port} externally',
                        file_path=file_path,
                        line=1,
                        severity=Severity.HIGH,
                        category="security",
                        snippet=f"ports:\n  - {host_port}:{container_port}",
                        cwe_id="CWE-668",
                    )
                )
            elif container_port in ADMIN_PORTS:
                admin_type = ADMIN_PORTS[container_port]
                findings.append(
                    StandardFinding(
                        rule_name="compose-admin-exposed",
                        message=f'Service "{service_name}" exposes {admin_type} port {container_port} externally',
                        file_path=file_path,
                        line=1,
                        severity=Severity.HIGH,
                        category="security",
                        snippet=f"ports:\n  - {host_port}:{container_port}",
                        cwe_id="CWE-668",
                    )
                )

    if image:
        findings.extend(_check_image_security(file_path, service_name, image))

    if user in ROOT_USER_IDS or (isinstance(user, str) and user.lower() in ROOT_USER_IDS):
        findings.append(
            StandardFinding(
                rule_name="compose-root-user",
                message=f'Service "{service_name}" explicitly runs as root user',
                file_path=file_path,
                line=1,
                severity=Severity.CRITICAL,
                category="deployment",
                snippet=f"{service_name}:\n  user: {user}",
                cwe_id="CWE-250",
            )
        )
    elif user is None:
        findings.append(
            StandardFinding(
                rule_name="compose-no-user-specified",
                message=f'Service "{service_name}" has no user specified (may default to root depending on image)',
                file_path=file_path,
                line=1,
                severity=Severity.MEDIUM,
                category="deployment",
                snippet=f"{service_name}:\n  # user: not specified",
                cwe_id="CWE-250",
            )
        )

    for capability in cap_add:
        if capability in DANGEROUS_CAPABILITIES:
            findings.append(
                StandardFinding(
                    rule_name="compose-dangerous-capability",
                    message=f'Service "{service_name}" grants dangerous capability: {capability}',
                    file_path=file_path,
                    line=1,
                    severity=Severity.CRITICAL,
                    category="deployment",
                    snippet=f"cap_add:\n  - {capability}",
                    cwe_id="CWE-250",
                )
            )

    if security_opt:
        for opt in INSECURE_SECURITY_OPTS:
            if opt in security_opt:
                findings.append(
                    StandardFinding(
                        rule_name="compose-disabled-security",
                        message=f'Service "{service_name}" disables security feature: {opt}',
                        file_path=file_path,
                        line=1,
                        severity=Severity.HIGH,
                        category="deployment",
                        snippet=f"security_opt:\n  - {opt}",
                        cwe_id="CWE-693",
                    )
                )

    for cmd_field, cmd_value in [("command", command), ("entrypoint", entrypoint)]:
        if cmd_value and isinstance(cmd_value, str):
            has_metachar = any(char in cmd_value for char in SHELL_METACHARACTERS)
            if has_metachar:
                snippet = (
                    f"{cmd_field}: {cmd_value[:60]}..."
                    if len(cmd_value) > 60
                    else f"{cmd_field}: {cmd_value}"
                )
                findings.append(
                    StandardFinding(
                        rule_name="compose-command-injection-risk",
                        message=f'Service "{service_name}" has shell metacharacters in {cmd_field}',
                        file_path=file_path,
                        line=1,
                        severity=Severity.MEDIUM,
                        category="deployment",
                        snippet=snippet,
                        cwe_id="CWE-78",
                    )
                )

    if not cap_drop or "ALL" not in cap_drop:
        findings.append(
            StandardFinding(
                rule_name="compose-missing-cap-drop",
                message=f'Service "{service_name}" does not drop all capabilities (missing cap_drop: [ALL])',
                file_path=file_path,
                line=1,
                severity=Severity.LOW,
                category="deployment",
                snippet=f"{service_name}:\n  cap_drop:\n    - ALL  # RECOMMENDED",
                cwe_id="CWE-250",
            )
        )

    healthcheck = service_data.get("healthcheck")
    if not healthcheck:
        findings.append(
            StandardFinding(
                rule_name="compose-missing-healthcheck",
                message=f'Service "{service_name}" has no healthcheck defined - orchestrator cannot monitor health',
                file_path=file_path,
                line=1,
                severity=Severity.LOW,
                category="deployment",
                snippet=f"{service_name}:\n  # healthcheck: not defined",
                cwe_id="CWE-1188",
            )
        )

    restart = service_data.get("restart")
    if not restart:
        findings.append(
            StandardFinding(
                rule_name="compose-missing-restart-policy",
                message=f'Service "{service_name}" has no restart policy - container will not auto-recover from crashes',
                file_path=file_path,
                line=1,
                severity=Severity.LOW,
                category="deployment",
                snippet=f"{service_name}:\n  # restart: not defined (use 'unless-stopped' or 'always')",
                cwe_id="CWE-1188",
            )
        )

    mem_limit = service_data.get("mem_limit")
    cpus = service_data.get("cpus")
    if not mem_limit and not cpus:
        findings.append(
            StandardFinding(
                rule_name="compose-no-resource-limits",
                message=f'Service "{service_name}" has no resource limits - can exhaust host resources (DoS)',
                file_path=file_path,
                line=1,
                severity=Severity.MEDIUM,
                category="deployment",
                snippet=f"{service_name}:\n  # mem_limit/cpus: not defined",
                cwe_id="CWE-400",
            )
        )

    read_only = service_data.get("read_only", False)
    if not read_only:
        findings.append(
            StandardFinding(
                rule_name="compose-writable-rootfs",
                message=f'Service "{service_name}" has writable root filesystem - use read_only: true',
                file_path=file_path,
                line=1,
                severity=Severity.LOW,
                category="deployment",
                snippet=f"{service_name}:\n  # read_only: true (recommended)",
                cwe_id="CWE-1188",
            )
        )

    return findings


def _check_image_security(file_path: str, service_name: str, image: str) -> list[StandardFinding]:
    """Check Docker image for security issues."""
    findings = []

    has_digest = "@" in image
    has_explicit_tag = ":" in image and not image.endswith(":latest")
    if not has_digest and not has_explicit_tag:
        findings.append(
            StandardFinding(
                rule_name="compose-unpinned-image",
                message=f'Service "{service_name}" uses unpinned image version (no tag or :latest)',
                file_path=file_path,
                line=1,
                severity=Severity.MEDIUM,
                category="security",
                snippet=f"image: {image}",
                cwe_id="CWE-1104",
            )
        )

    for vuln_pattern in VULNERABLE_IMAGES:
        if image.startswith(vuln_pattern):
            findings.append(
                StandardFinding(
                    rule_name="compose-vulnerable-image",
                    message=f'Service "{service_name}" uses deprecated/vulnerable image: {vuln_pattern}',
                    file_path=file_path,
                    line=1,
                    severity=Severity.HIGH,
                    category="security",
                    snippet=f"image: {image}",
                    cwe_id="CWE-937",
                )
            )
            break

    image_name = image.split(":")[0] if ":" in image else image
    official_images = {"alpine", "ubuntu", "debian", "centos", "fedora", "busybox", "scratch"}

    if "/" not in image_name and image_name not in official_images:
        findings.append(
            StandardFinding(
                rule_name="compose-unofficial-image",
                message=f'Service "{service_name}" uses potentially unofficial image without namespace',
                file_path=file_path,
                line=1,
                severity=Severity.LOW,
                category="security",
                snippet=f"image: {image}",
                cwe_id="CWE-494",
            )
        )

    return findings
