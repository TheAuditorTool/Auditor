"""Docker Compose Security Analyzer - Database-First Approach.

Detects security misconfigurations in Docker Compose services.
Uses pre-extracted data from compose_services table - NO FILE I/O.

This rule requires the compose_services table populated by the indexer
with Docker Compose configuration data.

Migration Status: Database-First Architecture
"""

import json
import sqlite3
from typing import List, Dict, Any, Set, Optional
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


# ============================================================================
# SECURITY PATTERNS
# ============================================================================

# Sensitive environment variable patterns
SENSITIVE_ENV_PATTERNS = frozenset([
    'PASSWORD', 'PASS', 'PWD', 'SECRET', 'TOKEN', 'KEY',
    'API_KEY', 'ACCESS_KEY', 'PRIVATE', 'CREDENTIAL',
    'AUTH', 'MYSQL_ROOT_PASSWORD', 'POSTGRES_PASSWORD',
    'MONGO_INITDB_ROOT_PASSWORD', 'REDIS_PASSWORD',
    'RABBITMQ_DEFAULT_PASS', 'ELASTIC_PASSWORD'
])

# Common weak passwords to detect
WEAK_PASSWORDS = frozenset([
    'password', '123456', 'admin', 'root', 'test', 'demo',
    'secret', 'changeme', 'password123', 'admin123',
    'letmein', 'welcome', 'monkey', 'dragon', 'master',
    'qwerty', 'abc123', 'iloveyou', 'password1', 'sunshine'
])

# Database ports that shouldn't be exposed externally
DATABASE_PORTS = {
    '3306': 'MySQL',
    '5432': 'PostgreSQL',
    '27017': 'MongoDB',
    '6379': 'Redis',
    '5984': 'CouchDB',
    '8086': 'InfluxDB',
    '9042': 'Cassandra',
    '7000': 'Cassandra Inter-node',
    '7001': 'Cassandra TLS',
    '9200': 'Elasticsearch',
    '9300': 'Elasticsearch Transport',
    '2181': 'Zookeeper',
    '9092': 'Kafka',
    '1433': 'SQL Server',
    '1521': 'Oracle',
    '3307': 'MariaDB',
    '5601': 'Kibana',
    '15672': 'RabbitMQ Management',
    '5672': 'RabbitMQ',
    '8529': 'ArangoDB',
    '28015': 'RethinkDB'
}

# Administrative ports that shouldn't be exposed
ADMIN_PORTS = {
    '8080': 'Admin Panel',
    '8081': 'Admin Interface',
    '9090': 'Prometheus',
    '3000': 'Grafana',
    '15672': 'RabbitMQ Management',
    '5601': 'Kibana',
    '8161': 'ActiveMQ Admin',
    '7077': 'Spark Master',
    '8088': 'YARN ResourceManager',
    '9870': 'HDFS NameNode',
    '16010': 'HBase Master'
}

# Dangerous volume mounts that enable container escape
DANGEROUS_MOUNTS = frozenset([
    'docker.sock',
    '/var/run/docker.sock',
    '/etc/shadow',
    '/etc/passwd',
    '/root',
    '/.ssh',
    '/proc',
    '/sys',
    '/dev'
])

# Known vulnerable or deprecated images
VULNERABLE_IMAGES = {
    'elasticsearch:2': 'EOL - upgrade to 7.x or 8.x',
    'elasticsearch:5': 'EOL - upgrade to 7.x or 8.x',
    'mysql:5.6': 'EOL - upgrade to 8.0',
    'postgres:9': 'EOL - upgrade to 14+',
    'mongo:3': 'EOL - upgrade to 5.0+',
    'redis:3': 'EOL - upgrade to 7.0+',
    'node:8': 'EOL - upgrade to 18+',
    'node:10': 'EOL - upgrade to 18+',
    'node:12': 'EOL - upgrade to 18+',
    'python:2': 'EOL - upgrade to Python 3.9+',
    'ruby:2.4': 'EOL - upgrade to 3.0+',
    'php:5': 'EOL - upgrade to 8.0+',
    'php:7.0': 'EOL - upgrade to 8.0+',
    'php:7.1': 'EOL - upgrade to 8.0+',
    'php:7.2': 'EOL - upgrade to 8.0+'
}


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def find_compose_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Docker Compose security misconfigurations using indexed data.

    Analyzes compose_services table for:
    - Docker socket mounting (container escape risk)
    - Privileged containers
    - Host network mode
    - Weak/hardcoded passwords
    - Exposed database and admin ports
    - Unpinned or vulnerable image versions
    - Dangerous volume mounts
    - Insecure capabilities

    All data comes from pre-indexed compose_services table.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of StandardFinding objects for detected issues
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Check if compose_services table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='compose_services'
        """)

        if not cursor.fetchone():
            # Table doesn't exist - indexer hasn't extracted compose data yet
            return findings

        # Load all compose services
        cursor.execute("""
            SELECT file_path, service_name, image, ports, volumes,
                   environment, is_privileged, network_mode
            FROM compose_services
            ORDER BY file_path, service_name
        """)

        for row in cursor.fetchall():
            service_findings = analyze_service(row)
            findings.extend(service_findings)

    finally:
        conn.close()

    return findings


# ============================================================================
# SERVICE ANALYSIS
# ============================================================================

def analyze_service(row: tuple) -> List[StandardFinding]:
    """Analyze a single Docker Compose service for security issues.

    Args:
        row: Database row with service data

    Returns:
        List of findings for this service
    """
    findings = []

    # Parse database row
    try:
        file_path = row[0]
        service_name = row[1]
        image = row[2]
        ports_json = row[3]
        volumes_json = row[4]
        env_json = row[5]
        is_privileged = bool(row[6])
        network_mode = row[7]

        # Parse JSON fields
        ports = json.loads(ports_json) if ports_json else []
        volumes = json.loads(volumes_json) if volumes_json else []
        environment = json.loads(env_json) if env_json else {}

    except (json.JSONDecodeError, IndexError, TypeError):
        return findings

    # Check for privileged mode
    if is_privileged:
        findings.append(StandardFinding(
            rule_name='compose-privileged-container',
            message=f'Service "{service_name}" runs in privileged mode',
            file_path=file_path,
            line=1,
            severity=Severity.CRITICAL,
            category='security',
            snippet=f'{service_name}:\n  privileged: true',
            fix_suggestion='Remove privileged mode and use specific capabilities instead',
            cwe_id='CWE-250'
        ))

    # Check for host network mode
    if network_mode == 'host':
        findings.append(StandardFinding(
            rule_name='compose-host-network',
            message=f'Service "{service_name}" uses host network mode',
            file_path=file_path,
            line=1,
            severity=Severity.HIGH,
            category='security',
            snippet=f'{service_name}:\n  network_mode: host',
            fix_suggestion='Use bridge or custom network instead of host network',
            cwe_id='CWE-668'
        ))

    # Check dangerous volume mounts
    for volume in volumes:
        if isinstance(volume, str):
            for dangerous_mount in DANGEROUS_MOUNTS:
                if dangerous_mount in volume:
                    if 'docker.sock' in volume:
                        findings.append(StandardFinding(
                            rule_name='compose-docker-socket',
                            message=f'Service "{service_name}" mounts Docker socket - container escape risk',
                            file_path=file_path,
                            line=1,
                            severity=Severity.CRITICAL,
                            category='security',
                            snippet=f'volumes:\n  - {volume}',
                            fix_suggestion='Remove docker.sock mount or use Docker-in-Docker (DinD) instead',
                            cwe_id='CWE-552'
                        ))
                    else:
                        findings.append(StandardFinding(
                            rule_name='compose-dangerous-mount',
                            message=f'Service "{service_name}" mounts sensitive host path: {dangerous_mount}',
                            file_path=file_path,
                            line=1,
                            severity=Severity.HIGH,
                            category='security',
                            snippet=f'volumes:\n  - {volume}',
                            fix_suggestion='Avoid mounting sensitive host paths',
                            cwe_id='CWE-552'
                        ))
                    break

    # Check environment variables for secrets
    if isinstance(environment, dict):
        for key, value in environment.items():
            if value and isinstance(value, str):
                key_upper = key.upper()

                # Check if it's a sensitive variable
                is_sensitive = any(pattern in key_upper for pattern in SENSITIVE_ENV_PATTERNS)

                if is_sensitive:
                    # Check if value is not using env var substitution
                    if not value.startswith('${') and not value.startswith('$'):
                        # Check for weak passwords
                        if value.lower() in WEAK_PASSWORDS:
                            findings.append(StandardFinding(
                                rule_name='compose-weak-password',
                                message=f'Service "{service_name}" uses weak password in {key}',
                                file_path=file_path,
                                line=1,
                                severity=Severity.CRITICAL,
                                category='security',
                                snippet=f'{key}=***',
                                fix_suggestion='Use strong password and store in .env file',
                                cwe_id='CWE-521'
                            ))
                        else:
                            findings.append(StandardFinding(
                                rule_name='compose-hardcoded-secret',
                                message=f'Service "{service_name}" has hardcoded secret: {key}',
                                file_path=file_path,
                                line=1,
                                severity=Severity.HIGH,
                                category='security',
                                snippet=f'{key}=***',
                                fix_suggestion=f'Use environment variable: ${{{key}}}',
                                cwe_id='CWE-798'
                            ))

    # Check exposed ports
    if isinstance(ports, list):
        for port_mapping in ports:
            if isinstance(port_mapping, str) and ':' in port_mapping:
                findings.extend(check_port_exposure(
                    file_path, service_name, port_mapping
                ))

    # Check image versions
    if image:
        findings.extend(check_image_security(
            file_path, service_name, image
        ))

    return findings


def check_port_exposure(file_path: str, service_name: str, port_mapping: str) -> List[StandardFinding]:
    """Check if sensitive ports are exposed externally.

    Args:
        file_path: Path to compose file
        service_name: Name of the service
        port_mapping: Port mapping string (e.g., "0.0.0.0:3306:3306")

    Returns:
        List of findings for port exposure issues
    """
    findings = []

    # Parse port mapping
    parts = port_mapping.split(':')
    if len(parts) >= 2:
        # Determine host binding
        if len(parts) == 2:
            # Format: "host:container"
            host_part = parts[0]
            container_port = parts[1].split('/')[0]  # Remove protocol if present
        else:
            # Format: "ip:host:container" or "host:container:protocol"
            host_part = ':'.join(parts[:-1])
            container_port = parts[-1].split('/')[0]

        # Check if exposed to all interfaces
        is_exposed = not any(host_part.startswith(prefix)
                            for prefix in ['127.0.0.1:', 'localhost:', '::1:'])

        if is_exposed:
            # Check for database ports
            if container_port in DATABASE_PORTS:
                db_type = DATABASE_PORTS[container_port]
                findings.append(StandardFinding(
                    rule_name='compose-database-exposed',
                    message=f'Service "{service_name}" exposes {db_type} port {container_port} to all interfaces',
                    file_path=file_path,
                    line=1,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=f'ports:\n  - {port_mapping}',
                    fix_suggestion=f'Bind to localhost only: 127.0.0.1:{container_port}:{container_port}',
                    cwe_id='CWE-668'
                ))

            # Check for admin ports
            elif container_port in ADMIN_PORTS:
                admin_type = ADMIN_PORTS[container_port]
                findings.append(StandardFinding(
                    rule_name='compose-admin-exposed',
                    message=f'Service "{service_name}" exposes {admin_type} port {container_port} externally',
                    file_path=file_path,
                    line=1,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=f'ports:\n  - {port_mapping}',
                    fix_suggestion=f'Bind to localhost or use reverse proxy',
                    cwe_id='CWE-668'
                ))

    return findings


def check_image_security(file_path: str, service_name: str, image: str) -> List[StandardFinding]:
    """Check Docker image for security issues.

    Args:
        file_path: Path to compose file
        service_name: Name of the service
        image: Docker image string

    Returns:
        List of findings for image issues
    """
    findings = []

    # Check for unpinned versions
    if ':latest' in image or (':' not in image and '/' in image):
        findings.append(StandardFinding(
            rule_name='compose-unpinned-image',
            message=f'Service "{service_name}" uses unpinned image version',
            file_path=file_path,
            line=1,
            severity=Severity.MEDIUM,
            category='security',
            snippet=f'image: {image}',
            fix_suggestion='Pin to specific version tag for reproducibility',
            cwe_id='CWE-330'
        ))

    # Check for known vulnerable images
    for vuln_pattern, upgrade_msg in VULNERABLE_IMAGES.items():
        if image.startswith(vuln_pattern):
            findings.append(StandardFinding(
                rule_name='compose-vulnerable-image',
                message=f'Service "{service_name}" uses deprecated/vulnerable image: {vuln_pattern}',
                file_path=file_path,
                line=1,
                severity=Severity.HIGH,
                category='security',
                snippet=f'image: {image}',
                fix_suggestion=upgrade_msg,
                cwe_id='CWE-937'
            ))
            break

    # Check for images without namespace (potential typosquatting)
    if ':' in image:
        image_name = image.split(':')[0]
    else:
        image_name = image

    if '/' not in image_name and image_name not in ['alpine', 'ubuntu', 'debian', 'centos',
                                                     'fedora', 'busybox', 'scratch']:
        findings.append(StandardFinding(
            rule_name='compose-unofficial-image',
            message=f'Service "{service_name}" uses potentially unofficial image without namespace',
            file_path=file_path,
            line=1,
            severity=Severity.LOW,
            category='security',
            snippet=f'image: {image}',
            fix_suggestion='Use official images with namespace (e.g., library/nginx or nginx)',
            cwe_id='CWE-494'
        ))

    return findings