"""Golden Standard Docker Compose Security Analyzer.

Detects security misconfigurations in Docker Compose services via database analysis.
Demonstrates database-aware rule pattern for TheAuditor.

MIGRATION STATUS: Golden Standard Reference [2024-12-13]
Signature: context: StandardRuleContext -> List[StandardFinding]
"""

import json
import sqlite3
from typing import List, Dict, Any, Set, Optional
from dataclasses import dataclass
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

@dataclass(frozen=True)
class ComposePatterns:
    """Configuration for Docker Compose security patterns."""
    
    # Sensitive environment variable patterns
    SENSITIVE_ENV_PATTERNS = frozenset([
        'PASSWORD', 'PASS', 'PWD', 'SECRET', 'TOKEN', 'KEY',
        'API_KEY', 'ACCESS_KEY', 'PRIVATE', 'CREDENTIAL',
        'AUTH', 'MYSQL_ROOT_PASSWORD', 'POSTGRES_PASSWORD',
        'MONGO_INITDB_ROOT_PASSWORD', 'REDIS_PASSWORD',
        'RABBITMQ_DEFAULT_PASS', 'ELASTIC_PASSWORD'
    ])
    
    # Common weak passwords
    WEAK_PASSWORDS = frozenset([
        'password', '123456', 'admin', 'root', 'test', 'demo',
        'secret', 'changeme', 'password123', 'admin123',
        'letmein', 'welcome', 'monkey', 'dragon', 'master',
        'qwerty', 'abc123', 'iloveyou', 'password1', 'sunshine'
    ])
    
    # Database ports and their services
    DATABASE_PORTS = {
        '3306': 'MySQL',
        '5432': 'PostgreSQL',
        '27017': 'MongoDB',
        '6379': 'Redis',
        '5984': 'CouchDB',
        '8086': 'InfluxDB',
        '9042': 'Cassandra',
        '7000': 'Cassandra',
        '7001': 'Cassandra',
        '9200': 'Elasticsearch',
        '9300': 'Elasticsearch',
        '2181': 'Zookeeper',
        '9092': 'Kafka',
        '1433': 'SQL Server',
        '1521': 'Oracle',
        '3307': 'MariaDB',
        '5601': 'Kibana',
        '15672': 'RabbitMQ Management'
    }
    
    # Risky volume mounts
    DANGEROUS_MOUNTS = frozenset([
        'docker.sock',
        '/var/run/docker.sock',
        '/etc/shadow',
        '/etc/passwd',
        '/root',
        '/.ssh',
        '/proc',
        '/sys'
    ])


# ============================================================================
# MAIN RULE FUNCTION (Standardized Interface)
# ============================================================================

def find_compose_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Docker Compose security misconfigurations.
    
    Analyzes compose_services table for:
    - Docker socket mounting (container escape)
    - Privileged containers
    - Host network mode
    - Weak/hardcoded passwords
    - Exposed database ports
    - Unpinned image versions
    
    Args:
        context: Standardized rule context with database path
        
    Returns:
        List of StandardFinding objects for detected issues
    """
    analyzer = ComposeAnalyzer(context)
    return analyzer.analyze()


# ============================================================================
# COMPOSE ANALYZER CLASS
# ============================================================================

class ComposeAnalyzer:
    """Main analyzer for Docker Compose configurations."""
    
    def __init__(self, context: StandardRuleContext):
        self.context = context
        self.patterns = ComposePatterns()
        self.findings: List[StandardFinding] = []
        self.db_path = context.db_path or str(context.project_path / ".pf" / "repo_index.db")
    
    def analyze(self) -> List[StandardFinding]:
        """Run complete Docker Compose analysis."""
        services = self._load_compose_services()
        
        for service in services:
            self._analyze_service(service)
        
        return self.findings
    
    def _load_compose_services(self) -> List['ComposeService']:
        """Load compose services from database."""
        services = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT file_path, service_name, image, ports, volumes, 
                       environment, is_privileged, network_mode
                FROM compose_services
            """)
            
            for row in cursor.fetchall():
                service = ComposeService.from_db_row(row)
                if service:
                    services.append(service)
            
            conn.close()
            
        except (sqlite3.Error, Exception):
            # Return empty list if database unavailable
            pass
        
        return services
    
    def _analyze_service(self, service: 'ComposeService') -> None:
        """Analyze a single Docker Compose service."""
        # Check for dangerous volume mounts
        self._check_dangerous_volumes(service)
        
        # Check for privileged mode
        self._check_privileged_mode(service)
        
        # Check for host network mode
        self._check_host_network(service)
        
        # Check for weak/hardcoded secrets
        self._check_environment_secrets(service)
        
        # Check for exposed database ports
        self._check_exposed_ports(service)
        
        # Check for unpinned images
        self._check_unpinned_images(service)
    
    def _check_dangerous_volumes(self, service: 'ComposeService') -> None:
        """Check for dangerous volume mounts."""
        for volume in service.volumes:
            # Check for Docker socket mounting
            if any(mount in volume for mount in self.patterns.DANGEROUS_MOUNTS):
                if 'docker.sock' in volume:
                    self._add_docker_socket_finding(service, volume)
                else:
                    self._add_dangerous_mount_finding(service, volume)
    
    def _check_privileged_mode(self, service: 'ComposeService') -> None:
        """Check for privileged container mode."""
        if service.is_privileged:
            self.findings.append(StandardFinding(
                rule_name='compose-privileged-container',
                message=f'Service "{service.name}" runs in privileged mode',
                file_path=service.file_path,
                line=1,
                severity=Severity.CRITICAL,
                category='security',
                snippet=f'{service.name}: privileged: true',
                fix_suggestion='Remove privileged mode and use specific capabilities instead'
            ))
    
    def _check_host_network(self, service: 'ComposeService') -> None:
        """Check for host network mode."""
        if service.network_mode == 'host':
            self.findings.append(StandardFinding(
                rule_name='compose-host-network',
                message=f'Service "{service.name}" uses host network mode',
                file_path=service.file_path,
                line=1,
                severity=Severity.HIGH,
                category='security',
                snippet=f'{service.name}: network_mode: host',
                fix_suggestion='Use bridge or custom network instead of host network'
            ))
    
    def _check_environment_secrets(self, service: 'ComposeService') -> None:
        """Check for weak or hardcoded secrets in environment."""
        for key, value in service.environment.items():
            if self._is_sensitive_env(key) and value and not value.startswith('$'):
                if value.lower() in self.patterns.WEAK_PASSWORDS:
                    self._add_weak_password_finding(service, key, value)
                else:
                    self._add_hardcoded_secret_finding(service, key)
    
    def _check_exposed_ports(self, service: 'ComposeService') -> None:
        """Check for exposed database ports."""
        for port_mapping in service.ports:
            port_info = self._parse_port_mapping(port_mapping)
            if port_info:
                self._check_database_port_exposure(service, port_info)
    
    def _check_unpinned_images(self, service: 'ComposeService') -> None:
        """Check for unpinned image versions."""
        if service.image and (':latest' in service.image or ':' not in service.image):
            self.findings.append(StandardFinding(
                rule_name='compose-unpinned-image',
                message=f'Service "{service.name}" uses unpinned image version',
                file_path=service.file_path,
                line=1,
                severity=Severity.MEDIUM,
                category='security',
                snippet=f'image: {service.image}',
                fix_suggestion='Pin to specific version tag (e.g., nginx:1.21.6)'
            ))
    
    def _is_sensitive_env(self, key: str) -> bool:
        """Check if environment variable is sensitive."""
        key_upper = key.upper()
        return any(pattern in key_upper for pattern in self.patterns.SENSITIVE_ENV_PATTERNS)
    
    def _parse_port_mapping(self, port_mapping: str) -> Optional[Dict[str, str]]:
        """Parse port mapping string."""
        if not isinstance(port_mapping, str) or ':' not in port_mapping:
            return None
        
        parts = port_mapping.split(':')
        if len(parts) >= 2:
            host_part = parts[0] if len(parts) == 2 else parts[-2]
            container_port = parts[-1].split('/')[0]  # Remove protocol
            
            # Determine if bound to all interfaces
            is_exposed = not any(host_part.startswith(prefix) 
                                for prefix in ['127.0.0.1:', 'localhost:'])
            
            return {
                'host_part': host_part,
                'container_port': container_port,
                'is_exposed': is_exposed
            }
        
        return None
    
    def _check_database_port_exposure(self, service: 'ComposeService', port_info: Dict[str, str]) -> None:
        """Check if database port is exposed externally."""
        container_port = port_info['container_port']
        
        if container_port in self.patterns.DATABASE_PORTS and port_info['is_exposed']:
            db_type = self.patterns.DATABASE_PORTS[container_port]
            
            self.findings.append(StandardFinding(
                rule_name='compose-database-exposed',
                message=f'Service "{service.name}" exposes {db_type} port to all interfaces',
                file_path=service.file_path,
                line=1,
                severity=Severity.HIGH,
                category='security',
                snippet=f'ports: {port_info["host_part"]}:{container_port}',
                fix_suggestion=f'Bind to localhost only: 127.0.0.1:{container_port}:{container_port}'
            ))
    
    def _add_docker_socket_finding(self, service: 'ComposeService', volume: str) -> None:
        """Add finding for Docker socket mounting."""
        self.findings.append(StandardFinding(
            rule_name='compose-docker-socket',
            message=f'Service "{service.name}" mounts Docker socket - container escape risk',
            file_path=service.file_path,
            line=1,
            severity=Severity.CRITICAL,
            category='security',
            snippet=f'volumes: {volume}',
            fix_suggestion='Remove docker.sock mount or use Docker-in-Docker (DinD) instead'
        ))
    
    def _add_dangerous_mount_finding(self, service: 'ComposeService', volume: str) -> None:
        """Add finding for other dangerous mounts."""
        self.findings.append(StandardFinding(
            rule_name='compose-dangerous-mount',
            message=f'Service "{service.name}" mounts sensitive host path',
            file_path=service.file_path,
            line=1,
            severity=Severity.HIGH,
            category='security',
            snippet=f'volumes: {volume}',
            fix_suggestion='Avoid mounting sensitive host paths like /etc, /root, /proc'
        ))
    
    def _add_weak_password_finding(self, service: 'ComposeService', key: str, value: str) -> None:
        """Add finding for weak password."""
        # Truncate value for security
        display_value = value[:3] + '***' if len(value) > 3 else '***'
        
        self.findings.append(StandardFinding(
            rule_name='compose-weak-password',
            message=f'Service "{service.name}" has weak password in environment',
            file_path=service.file_path,
            line=1,
            severity=Severity.CRITICAL,
            category='security',
            snippet=f'{key}={display_value}',
            fix_suggestion='Use strong passwords and store in .env file or secrets manager'
        ))
    
    def _add_hardcoded_secret_finding(self, service: 'ComposeService', key: str) -> None:
        """Add finding for hardcoded secret."""
        self.findings.append(StandardFinding(
            rule_name='compose-hardcoded-secret',
            message=f'Service "{service.name}" has hardcoded secret in environment',
            file_path=service.file_path,
            line=1,
            severity=Severity.HIGH,
            category='security',
            snippet=f'{key}=***',
            fix_suggestion=f'Use environment variable: ${{{key}}}'
        ))


# ============================================================================
# DATA MODEL
# ============================================================================

@dataclass
class ComposeService:
    """Represents a Docker Compose service from database."""
    
    file_path: str
    name: str
    image: Optional[str]
    ports: List[str]
    volumes: List[str]
    environment: Dict[str, str]
    is_privileged: bool
    network_mode: Optional[str]
    
    @classmethod
    def from_db_row(cls, row: tuple) -> Optional['ComposeService']:
        """Create ComposeService from database row."""
        try:
            file_path = row[0]
            service_name = row[1]
            image = row[2]
            ports_json = row[3]
            volumes_json = row[4]
            env_json = row[5]
            is_privileged = bool(row[6])
            network_mode = row[7]
            
            # Parse JSON fields safely
            try:
                ports = json.loads(ports_json) if ports_json else []
                volumes = json.loads(volumes_json) if volumes_json else []
                environment = json.loads(env_json) if env_json else {}
            except json.JSONDecodeError:
                return None
            
            return cls(
                file_path=file_path,
                name=service_name,
                image=image,
                ports=ports if isinstance(ports, list) else [],
                volumes=volumes if isinstance(volumes, list) else [],
                environment=environment if isinstance(environment, dict) else {},
                is_privileged=is_privileged,
                network_mode=network_mode
            )
            
        except (IndexError, TypeError):
            return None