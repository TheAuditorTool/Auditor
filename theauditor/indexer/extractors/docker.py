"""Docker file extractor.

Handles extraction of Docker-specific elements including:
- Base images and build stages
- Environment variables and build arguments
- Security issues (running as root, unpinned images, etc.)
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from . import BaseExtractor
from ..config import SENSITIVE_PORTS, SENSITIVE_ENV_KEYWORDS

# Check for optional Docker parsing libraries
try:
    from dockerfile_parse import DockerfileParser as DFParser
    HAS_DOCKERFILE_PARSE = True
except ImportError:
    HAS_DOCKERFILE_PARSE = False

try:
    from theauditor.parsers.dockerfile_parser import DockerfileParser
    HAS_CUSTOM_PARSERS = True
except ImportError:
    HAS_CUSTOM_PARSERS = False


class DockerExtractor(BaseExtractor):
    """Extractor for Docker files."""
    
    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this extractor supports.
        
        Note: Dockerfiles don't have extensions, we match by filename.
        """
        return []  # We handle this specially in should_extract
    
    def should_extract(self, file_path: str) -> bool:
        """Check if this extractor should handle the file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if this is a Dockerfile
        """
        file_name_lower = Path(file_path).name.lower()
        dockerfile_patterns = [
            'dockerfile', 'dockerfile.dev', 'dockerfile.prod', 
            'dockerfile.test', 'dockerfile.staging'
        ]
        return (file_name_lower in dockerfile_patterns or 
                file_name_lower.startswith('dockerfile.'))
    
    def extract(self, file_info: Dict[str, Any], content: str, 
                tree: Optional[Any] = None) -> Dict[str, Any]:
        """Extract all relevant information from a Dockerfile.
        
        Args:
            file_info: File metadata dictionary
            content: File content
            tree: Optional pre-parsed AST tree (not used for Docker)
            
        Returns:
            Dictionary containing all extracted data
        """
        result = {
            'docker_info': {},
            'docker_issues': []
        }
        
        # Extract basic Docker info if dockerfile_parse available
        if HAS_DOCKERFILE_PARSE:
            result['docker_info'] = self._extract_docker_info(content)
        
        # Analyze for security issues if custom parser available
        if HAS_CUSTOM_PARSERS:
            file_path = self.root_path / file_info['path']
            result['docker_issues'] = self._analyze_security(file_path, content)
        
        return result
    
    def _extract_docker_info(self, content: str) -> Dict[str, Any]:
        """Extract structured information from Dockerfile content.
        
        Args:
            content: Dockerfile content
            
        Returns:
            Dict with Docker information
        """
        info = {
            'base_image': None,
            'exposed_ports': [],
            'env_vars': {},
            'build_args': {},
            'user': None,
            'has_healthcheck': False
        }
        
        try:
            # Parse the Dockerfile
            parser = DFParser()
            parser.content = content
            
            # Extract base image
            if parser.baseimage:
                info['base_image'] = parser.baseimage
            
            # Extract exposed ports
            for instruction in parser.structure:
                if instruction['instruction'] == 'EXPOSE':
                    # Parse ports from the value
                    ports_str = instruction['value']
                    ports = ports_str.split()
                    info['exposed_ports'].extend(ports)
                
                # Extract environment variables
                elif instruction['instruction'] == 'ENV':
                    # Parse ENV key=value or ENV key value
                    env_str = instruction['value']
                    # Handle both formats: KEY=value and KEY value
                    if '=' in env_str:
                        # Format: KEY=value KEY2=value2
                        parts = env_str.split()
                        for part in parts:
                            if '=' in part:
                                key, value = part.split('=', 1)
                                info['env_vars'][key] = value
                    else:
                        # Format: KEY value
                        parts = env_str.split(None, 1)
                        if len(parts) == 2:
                            info['env_vars'][parts[0]] = parts[1]
                
                # Extract build arguments
                elif instruction['instruction'] == 'ARG':
                    arg_str = instruction['value']
                    # Handle ARG key=value or ARG key
                    if '=' in arg_str:
                        key, value = arg_str.split('=', 1)
                        info['build_args'][key] = value
                    else:
                        info['build_args'][arg_str] = None
                
                # Check for USER and HEALTHCHECK
                elif instruction['instruction'] == 'USER':
                    info['user'] = instruction['value']
                elif instruction['instruction'] == 'HEALTHCHECK':
                    info['has_healthcheck'] = True
                elif instruction['instruction'] == 'WORKDIR':
                    info['env_vars']['_DOCKER_WORKDIR'] = instruction['value']
        
        except Exception:
            # If parsing fails, return empty info
            return {}
        
        return info
    
    def _analyze_security(self, file_path: Path, content: str) -> List[Dict]:
        """Analyze Dockerfile for security issues.
        
        Args:
            file_path: Path to the Dockerfile
            content: Dockerfile content
            
        Returns:
            List of security issue dictionaries
        """
        issues = []
        
        try:
            parser = DockerfileParser()
            parsed_data = parser.parse_file(file_path)
            
            if 'instructions' not in parsed_data:
                return issues
            
            instructions = parsed_data['instructions']
            
            # Security Rule 1: Check for running as root
            has_user = False
            runs_as_root = False
            for inst in instructions:
                if inst['instruction'] == 'USER':
                    has_user = True
                    if inst['value'].strip().lower() == 'root':
                        runs_as_root = True
                        issues.append({
                            'line': inst['line'],
                            'issue_type': 'ROOT_USER',
                            'severity': 'critical'
                        })
            
            if not has_user:
                # No USER instruction means runs as root by default
                issues.append({
                    'line': 1,
                    'issue_type': 'ROOT_USER',
                    'severity': 'critical'
                })
            
            # Security Rule 2: Check for unpinned images
            for inst in instructions:
                if inst['instruction'] == 'FROM':
                    image = inst['value'].strip()
                    # Check for :latest or no tag
                    if ':latest' in image or (':' not in image and ' as ' not in image.lower()):
                        issues.append({
                            'line': inst['line'],
                            'issue_type': 'UNPINNED_IMAGE',
                            'severity': 'high'
                        })
            
            # Security Rule 3: Check for secrets in ENV
            for inst in instructions:
                if inst['instruction'] == 'ENV':
                    env_value = inst['value'].upper()
                    for keyword in SENSITIVE_ENV_KEYWORDS:
                        if keyword in env_value:
                            issues.append({
                                'line': inst['line'],
                                'issue_type': 'SECRET_IN_ENV',
                                'severity': 'critical'
                            })
                            break
            
            # Security Rule 4: Check for missing healthcheck
            has_healthcheck = any(inst['instruction'] == 'HEALTHCHECK' for inst in instructions)
            if not has_healthcheck:
                issues.append({
                    'line': 1,
                    'issue_type': 'MISSING_HEALTHCHECK',
                    'severity': 'medium'
                })
            
            # Security Rule 5: Check for dangerous COPY commands
            for inst in instructions:
                if inst['instruction'] == 'COPY':
                    copy_value = inst['value'].strip()
                    # Check for copying entire directory including potential secrets
                    if copy_value.startswith('. ') or copy_value == '.' or '.env' in copy_value:
                        issues.append({
                            'line': inst['line'],
                            'issue_type': 'DANGEROUS_COPY',
                            'severity': 'high'
                        })
            
            # Security Rule 6: Check for apt-get upgrade in production
            for inst in instructions:
                if inst['instruction'] == 'RUN':
                    run_value = inst['value'].lower()
                    if 'apt-get upgrade' in run_value or 'apt upgrade' in run_value:
                        issues.append({
                            'line': inst['line'],
                            'issue_type': 'APT_UPGRADE_IN_PROD',
                            'severity': 'medium'
                        })
            
            # Security Rule 7: Check for exposed sensitive ports
            for inst in instructions:
                if inst['instruction'] == 'EXPOSE':
                    ports = inst['value'].split()
                    for port in ports:
                        port_num = port.split('/')[0]  # Handle "8080/tcp" format
                        if port_num in SENSITIVE_PORTS:
                            issues.append({
                                'line': inst['line'],
                                'issue_type': 'SENSITIVE_PORT_EXPOSED',
                                'severity': 'high'
                            })
        
        except Exception:
            # Silently fail security analysis
            pass
        
        return issues