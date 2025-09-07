"""Database-aware docker-compose security analyzer.

This module queries the compose_services table to detect common docker-compose
security misconfigurations. It follows the pattern established by other
database-aware rules in TheAuditor.
"""

import json
import sqlite3
import re
from typing import List, Dict, Any


def find_compose_issues(db_path: str) -> List[Dict[str, Any]]:
    """
    Analyze docker-compose configurations stored in the database for security issues.
    
    This function queries the compose_services table populated by the indexer
    and detects the following critical docker-compose misconfigurations:
    
    - Mounting the Docker socket (docker.sock)
    - Services running with privileged: true
    - Services using network_mode: host
    - Weak, hardcoded passwords or secrets in environment
    - Exposing sensitive database ports to the host
    
    Args:
        db_path: Path to the repo_index.db database
        
    Returns:
        List of security findings in normalized format
    """
    findings = []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query all compose services from the database
        cursor.execute("""
            SELECT file_path, service_name, image, ports, volumes, 
                   environment, is_privileged, network_mode
            FROM compose_services
        """)
        
        compose_services = cursor.fetchall()
        
        for row in compose_services:
            file_path = row[0]
            service_name = row[1]
            image = row[2]
            ports_json = row[3]
            volumes_json = row[4]
            env_json = row[5]
            is_privileged = row[6]
            network_mode = row[7]
            
            # Parse JSON fields
            try:
                ports = json.loads(ports_json) if ports_json else []
                volumes = json.loads(volumes_json) if volumes_json else []
                environment = json.loads(env_json) if env_json else {}
            except json.JSONDecodeError:
                # Skip malformed data
                continue
            
            # Detection 1: Mounting docker.sock (container escape risk)
            for volume in volumes:
                if isinstance(volume, str):
                    # Check for docker.sock in volume mapping
                    if 'docker.sock' in volume:
                        findings.append({
                            'pattern_name': 'COMPOSE_DOCKER_SOCKET_MOUNTED',
                            'message': f'Service "{service_name}" mounts Docker socket - container escape risk',
                            'file': file_path,
                            'line': 0,
                            'column': 0,
                            'severity': 'critical',
                            'snippet': f'volumes: {volume}',
                            'category': 'security',
                            'confidence': 0.95,
                            'details': {
                                'service': service_name,
                                'vulnerability': 'Container can control Docker daemon and escape',
                                'fix': 'Remove docker.sock mount or use Docker-in-Docker (DinD) instead',
                                'volume': volume
                            }
                        })
            
            # Detection 2: Privileged mode
            if is_privileged:
                findings.append({
                    'pattern_name': 'COMPOSE_PRIVILEGED_CONTAINER',
                    'message': f'Service "{service_name}" runs in privileged mode - security risk',
                    'file': file_path,
                    'line': 0,
                    'column': 0,
                    'severity': 'critical',
                    'snippet': f'{service_name}: privileged: true',
                    'category': 'security',
                    'confidence': 0.95,
                    'details': {
                        'service': service_name,
                        'vulnerability': 'Container has all capabilities and can compromise host',
                        'fix': 'Remove privileged mode and use specific capabilities instead'
                    }
                })
            
            # Detection 3: Host network mode
            if network_mode == 'host':
                findings.append({
                    'pattern_name': 'COMPOSE_HOST_NETWORK',
                    'message': f'Service "{service_name}" uses host network mode - security risk',
                    'file': file_path,
                    'line': 0,
                    'column': 0,
                    'severity': 'high',
                    'snippet': f'{service_name}: network_mode: host',
                    'category': 'security',
                    'confidence': 0.90,
                    'details': {
                        'service': service_name,
                        'vulnerability': 'Container bypasses network isolation',
                        'fix': 'Use bridge or custom network instead of host network'
                    }
                })
            
            # Detection 4: Weak passwords in environment
            if environment:
                sensitive_patterns = [
                    'PASSWORD', 'PASS', 'PWD', 'SECRET', 'TOKEN', 'KEY',
                    'API_KEY', 'ACCESS_KEY', 'PRIVATE', 'CREDENTIAL',
                    'AUTH', 'MYSQL_ROOT_PASSWORD', 'POSTGRES_PASSWORD',
                    'MONGO_INITDB_ROOT_PASSWORD', 'REDIS_PASSWORD'
                ]
                
                # Common weak passwords to check for
                weak_passwords = [
                    'password', '123456', 'admin', 'root', 'test', 'demo',
                    'secret', 'changeme', 'password123', 'admin123',
                    'letmein', 'welcome', 'monkey', 'dragon', 'master'
                ]
                
                for env_key, env_value in environment.items():
                    env_key_upper = env_key.upper()
                    
                    # Check if this is a sensitive environment variable
                    is_sensitive = any(pattern in env_key_upper for pattern in sensitive_patterns)
                    
                    if is_sensitive and env_value:
                        # Check for hardcoded values (not variable references)
                        if not env_value.startswith('$'):
                            # Check for weak passwords
                            if env_value.lower() in weak_passwords:
                                findings.append({
                                    'pattern_name': 'COMPOSE_WEAK_PASSWORD',
                                    'message': f'Service "{service_name}" has weak password in environment',
                                    'file': file_path,
                                    'line': 0,
                                    'column': 0,
                                    'severity': 'critical',
                                    'snippet': f'{env_key}={env_value[:10]}...' if len(env_value) > 10 else f'{env_key}={env_value}',
                                    'category': 'security',
                                    'confidence': 0.90,
                                    'details': {
                                        'service': service_name,
                                        'env_key': env_key,
                                        'vulnerability': 'Weak or common password used',
                                        'fix': 'Use strong passwords and store in .env file or secrets manager'
                                    }
                                })
                            # Check for any hardcoded secret (even if not weak)
                            elif len(env_value) > 0:
                                findings.append({
                                    'pattern_name': 'COMPOSE_HARDCODED_SECRET',
                                    'message': f'Service "{service_name}" has hardcoded secret in environment',
                                    'file': file_path,
                                    'line': 0,
                                    'column': 0,
                                    'severity': 'high',
                                    'snippet': f'{env_key}=***',
                                    'category': 'security',
                                    'confidence': 0.85,
                                    'details': {
                                        'service': service_name,
                                        'env_key': env_key,
                                        'vulnerability': 'Secret hardcoded in compose file',
                                        'fix': 'Use environment variables: ${' + env_key + '}'
                                    }
                                })
            
            # Detection 5: Exposed database ports
            if ports:
                # Database default ports
                database_ports = {
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
                    '1521': 'Oracle'
                }
                
                for port_mapping in ports:
                    if isinstance(port_mapping, str):
                        # Parse port mapping (can be "8080:80" or just "80")
                        if ':' in port_mapping:
                            host_port, container_port = port_mapping.split(':', 1)
                            # Remove protocol suffix if present (e.g., "80/tcp")
                            host_port = host_port.split('/')[0]
                            container_port = container_port.split('/')[0]
                        else:
                            # No host port specified, Docker assigns random port
                            continue
                        
                        # Check if this is a database port being exposed
                        if container_port in database_ports:
                            db_type = database_ports[container_port]
                            
                            # Check if it's bound to all interfaces (0.0.0.0 or no IP specified)
                            if not host_port.startswith('127.0.0.1') and not host_port.startswith('localhost'):
                                findings.append({
                                    'pattern_name': 'COMPOSE_DATABASE_PORT_EXPOSED',
                                    'message': f'Service "{service_name}" exposes {db_type} port to all interfaces',
                                    'file': file_path,
                                    'line': 0,
                                    'column': 0,
                                    'severity': 'high',
                                    'snippet': f'ports: {port_mapping}',
                                    'category': 'security',
                                    'confidence': 0.85,
                                    'details': {
                                        'service': service_name,
                                        'database': db_type,
                                        'port': container_port,
                                        'vulnerability': 'Database accessible from external network',
                                        'fix': f'Bind to localhost only: 127.0.0.1:{host_port}:{container_port}'
                                    }
                                })
            
            # Additional detection: Unpinned image versions
            if image and ':latest' in image:
                findings.append({
                    'pattern_name': 'COMPOSE_UNPINNED_IMAGE',
                    'message': f'Service "{service_name}" uses unpinned image version',
                    'file': file_path,
                    'line': 0,
                    'column': 0,
                    'severity': 'medium',
                    'snippet': f'image: {image}',
                    'category': 'security',
                    'confidence': 0.80,
                    'details': {
                        'service': service_name,
                        'image': image,
                        'vulnerability': 'Image version can change unexpectedly',
                        'fix': 'Pin to specific version tag'
                    }
                })
        
        conn.close()
        
    except sqlite3.Error as e:
        # Return empty findings if database is not accessible
        return []
    except Exception as e:
        # Catch any other unexpected errors
        return []
    
    return findings