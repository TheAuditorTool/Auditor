"""Docker container security analyzer module."""

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

# Set up logger
logger = logging.getLogger(__name__)


def analyze_docker_images(db_path: str, check_vulnerabilities: bool = True) -> List[Dict[str, Any]]:
    """
    Analyze indexed Docker images for security misconfigurations.
    
    Args:
        db_path: Path to the repo_index.db database
        check_vulnerabilities: Whether to scan base images for vulnerabilities
        
    Returns:
        List of security findings with severity levels
    """
    findings = []
    
    # Connect to the database
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        
        # Run each security check
        findings.extend(_find_root_containers(conn))
        findings.extend(_find_exposed_secrets(conn))
        
        # Base image vulnerability check
        if check_vulnerabilities:
            base_images = _prepare_base_image_scan(conn)
            if base_images:
                # Import here to avoid circular dependency
                from .vulnerability_scanner import scan_dependencies
                
                # Run vulnerability scan on Docker base images
                vuln_findings = scan_dependencies(base_images, offline=False)
                
                # Convert vulnerability findings to Docker-specific format
                for vuln in vuln_findings:
                    findings.append({
                        'type': 'docker_base_image_vulnerability',
                        'severity': vuln.get('severity', 'medium'),
                        'file': 'Dockerfile',
                        'message': f"Base image {vuln.get('package', 'unknown')} has vulnerability: {vuln.get('title', 'Unknown vulnerability')}",
                        'recommendation': vuln.get('recommendation', 'Update to latest secure version'),
                        'details': vuln
                    })
        
    return findings


def _find_root_containers(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Detect containers running as root user (default or explicit).
    
    CIS Docker Benchmark: Running containers as root is a major security risk.
    A container breakout would grant attacker root privileges on the host.
    
    Args:
        conn: SQLite database connection
        
    Returns:
        List of findings for containers running as root
    """
    findings = []
    cursor = conn.cursor()
    
    # Query all Docker images
    cursor.execute("SELECT file_path, env_vars FROM docker_images")
    
    for row in cursor:
        file_path = row['file_path']
        env_vars_json = row['env_vars']
        
        # Parse the JSON column
        try:
            env_vars = json.loads(env_vars_json) if env_vars_json else {}
        except json.JSONDecodeError as e:
            logger.debug(f"Non-critical error parsing Docker env vars JSON: {e}", exc_info=False)
            continue
            
        # Check for _DOCKER_USER key (set by USER instruction)
        docker_user = env_vars.get('_DOCKER_USER')
        
        # If no USER instruction or explicitly set to root
        if docker_user is None or docker_user.lower() == 'root':
            findings.append({
                'type': 'docker_root_user',
                'severity': 'High',
                'file': file_path,
                'message': f"Container runs as root user (USER instruction {'not set' if docker_user is None else 'set to root'})",
                'recommendation': "Add 'USER <non-root-user>' instruction to Dockerfile after installing dependencies"
            })
    
    return findings


def _find_exposed_secrets(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Detect hardcoded secrets in ENV and ARG instructions.
    
    ENV and ARG values are stored in image layers and can be inspected
    by anyone with access to the image, making them unsuitable for secrets.
    
    Args:
        conn: SQLite database connection
        
    Returns:
        List of findings for exposed secrets
    """
    findings = []
    cursor = conn.cursor()
    
    # Patterns for detecting sensitive keys
    sensitive_key_patterns = [
        r'(?i)password',
        r'(?i)secret',
        r'(?i)api[_-]?key',
        r'(?i)token',
        r'(?i)auth',
        r'(?i)credential',
        r'(?i)private[_-]?key',
        r'(?i)access[_-]?key'
    ]
    
    # Common secret value patterns
    secret_value_patterns = [
        r'^ghp_[A-Za-z0-9]{36}$',  # GitHub personal access token
        r'^ghs_[A-Za-z0-9]{36}$',  # GitHub secret
        r'^sk-[A-Za-z0-9]{48}$',   # OpenAI API key
        r'^xox[baprs]-[A-Za-z0-9-]+$',  # Slack token
        r'^AKIA[A-Z0-9]{16}$',     # AWS access key ID
    ]
    
    # Query all Docker images
    cursor.execute("SELECT file_path, env_vars, build_args FROM docker_images")
    
    for row in cursor:
        file_path = row['file_path']
        env_vars_json = row['env_vars']
        build_args_json = row['build_args']
        
        # Parse JSON columns
        try:
            env_vars = json.loads(env_vars_json) if env_vars_json else {}
            build_args = json.loads(build_args_json) if build_args_json else {}
        except json.JSONDecodeError as e:
            logger.debug(f"Non-critical error parsing Docker JSON columns: {e}", exc_info=False)
            continue
        
        # Check ENV variables
        for key, value in env_vars.items():
            # Skip internal tracking keys
            if key.startswith('_DOCKER_'):
                continue
                
            is_sensitive = False
            
            # Check if key name indicates sensitive data
            for pattern in sensitive_key_patterns:
                if re.search(pattern, key):
                    is_sensitive = True
                    findings.append({
                        'type': 'docker_exposed_secret',
                        'severity': 'Critical',
                        'file': file_path,
                        'message': f"Potential secret exposed in ENV instruction: {key}",
                        'recommendation': "Use Docker secrets or mount secrets at runtime instead of ENV"
                    })
                    break
            
            # Check if value matches known secret patterns
            if not is_sensitive and value:
                for pattern in secret_value_patterns:
                    if re.match(pattern, str(value)):
                        findings.append({
                            'type': 'docker_exposed_secret',
                            'severity': 'Critical',
                            'file': file_path,
                            'message': f"Detected secret pattern in ENV value for key: {key}",
                            'recommendation': "Remove hardcoded secrets and use runtime secret injection"
                        })
                        break
                
                # Check for high entropy strings (potential secrets)
                if not is_sensitive and value and _is_high_entropy(str(value)):
                    findings.append({
                        'type': 'docker_possible_secret',
                        'severity': 'Medium',
                        'file': file_path,
                        'message': f"High entropy value in ENV {key} - possible secret",
                        'recommendation': "Review if this is a secret and move to secure storage if so"
                    })
        
        # Check BUILD ARGs
        for key, value in build_args.items():
            # Check if key name indicates sensitive data
            for pattern in sensitive_key_patterns:
                if re.search(pattern, key):
                    findings.append({
                        'type': 'docker_exposed_secret',
                        'severity': 'High',  # Slightly lower than ENV as ARGs are build-time only
                        'file': file_path,
                        'message': f"Potential secret exposed in ARG instruction: {key}",
                        'recommendation': "Use --secret mount or BuildKit secrets instead of ARG for sensitive data"
                    })
                    break
    
    return findings


def _prepare_base_image_scan(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Prepare base image data for vulnerability scanning.
    
    This function extracts and parses base image information from the database,
    preparing it in the format expected by vulnerability_scanner.scan_dependencies().
    
    Args:
        conn: SQLite database connection
        
    Returns:
        List of dependency dicts with manager='docker', name, and version
    """
    dependencies = []
    cursor = conn.cursor()
    
    # Get all unique base images
    cursor.execute("SELECT DISTINCT base_image FROM docker_images WHERE base_image IS NOT NULL")
    
    for row in cursor:
        base_image = row[0]
        
        # Parse image string to extract name and version/tag
        # Format examples:
        # - python:3.11-slim
        # - node:18-alpine
        # - ubuntu:22.04
        # - gcr.io/project/image:tag
        # - image@sha256:hash
        
        if '@' in base_image:
            # Handle digest format (image@sha256:...)
            name = base_image.split('@')[0]
            version = base_image.split('@')[1]
        elif ':' in base_image:
            # Handle tag format (image:tag)
            parts = base_image.rsplit(':', 1)
            name = parts[0]
            version = parts[1]
        else:
            # No tag specified, defaults to 'latest'
            name = base_image
            version = 'latest'
        
        # Create dependency dict in vulnerability scanner format
        dependencies.append({
            'manager': 'docker',
            'name': name,
            'version': version,
            'source_file': 'Dockerfile'  # Could be enhanced to track actual file
        })
    
    return dependencies


def _is_high_entropy(value: str, threshold: float = 4.0) -> bool:
    """
    Check if a string has high entropy (potential secret).
    
    Uses Shannon entropy calculation to detect random-looking strings
    that might be secrets, API keys, or tokens.
    
    Args:
        value: String to check
        threshold: Entropy threshold (default 4.0)
        
    Returns:
        True if entropy exceeds threshold
    """
    import math
    
    # Skip short strings
    if len(value) < 10:
        return False
    
    # Skip strings with spaces (likely not secrets)
    if ' ' in value:
        return False
    
    # Calculate character frequency
    char_freq = {}
    for char in value:
        char_freq[char] = char_freq.get(char, 0) + 1
    
    # Calculate Shannon entropy
    entropy = 0.0
    for freq in char_freq.values():
        probability = freq / len(value)
        if probability > 0:
            entropy -= probability * math.log2(probability)
    
    return entropy > threshold