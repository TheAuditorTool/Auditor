"""Parser for docker-compose.yml files.

This module provides safe parsing of docker-compose.yml files to extract
security-relevant configuration for each service.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional


class ComposeParser:
    """Parser for docker-compose.yml files."""
    
    def __init__(self):
        """Initialize the compose parser."""
        pass
    
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse a docker-compose.yml file and extract security-relevant information.
        
        Args:
            file_path: Path to the docker-compose.yml file
            
        Returns:
            Dictionary with parsed compose data including services and their configurations
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Use safe_load to prevent arbitrary code execution
                compose_data = yaml.safe_load(f)
                
            if not compose_data:
                return {'services': []}
                
            return self._extract_compose_info(compose_data, str(file_path))
            
        except (yaml.YAMLError, FileNotFoundError, PermissionError) as e:
            # Return empty result on parsing errors
            return {'services': [], 'error': str(e)}
    
    def parse_content(self, content: str, file_path: str = 'unknown') -> Dict[str, Any]:
        """
        Parse docker-compose content string and extract security-relevant information.
        
        Args:
            content: Docker-compose.yml content as string
            file_path: Optional file path for reference
            
        Returns:
            Dictionary with parsed compose data
        """
        try:
            compose_data = yaml.safe_load(content)
            if not compose_data:
                return {'services': []}
            return self._extract_compose_info(compose_data, file_path)
        except yaml.YAMLError as e:
            return {'services': [], 'error': str(e)}
    
    def _extract_compose_info(self, compose_data: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """
        Extract security-relevant information from parsed compose data.
        
        Args:
            compose_data: Parsed YAML data
            file_path: Path to the source file
            
        Returns:
            Dictionary with extracted service information
        """
        result = {
            'version': compose_data.get('version', ''),
            'services': []
        }
        
        services = compose_data.get('services', {})
        
        for service_name, service_config in services.items():
            if not isinstance(service_config, dict):
                continue
                
            service_info = {
                'name': service_name,
                'image': self._extract_image(service_config),
                'ports': self._extract_ports(service_config),
                'volumes': self._extract_volumes(service_config),
                'environment': self._extract_environment(service_config),
                'is_privileged': service_config.get('privileged', False),
                'network_mode': service_config.get('network_mode', 'bridge'),
                'user': service_config.get('user', None),
                'cap_add': service_config.get('cap_add', []),
                'cap_drop': service_config.get('cap_drop', []),
                'security_opt': service_config.get('security_opt', []),
                'restart': service_config.get('restart', 'no'),
                'command': service_config.get('command', None),
                'entrypoint': service_config.get('entrypoint', None),
                'depends_on': service_config.get('depends_on', []),
                'healthcheck': self._extract_healthcheck(service_config)
            }
            
            result['services'].append(service_info)
        
        return result
    
    def _extract_image(self, service_config: Dict[str, Any]) -> Optional[str]:
        """Extract image information from service configuration."""
        # Image can be specified directly or under build configuration
        if 'image' in service_config:
            return service_config['image']
        elif 'build' in service_config:
            build_config = service_config['build']
            if isinstance(build_config, dict) and 'image' in build_config:
                return build_config['image']
            else:
                return 'built_locally'
        return None
    
    def _extract_ports(self, service_config: Dict[str, Any]) -> List[str]:
        """
        Extract port mappings from service configuration.
        
        Handles various port formats:
        - "8080:80" (host:container)
        - "8080:80/tcp"
        - {"target": 80, "published": 8080}
        """
        ports = []
        port_config = service_config.get('ports', [])
        
        if not port_config:
            return ports
            
        for port in port_config:
            if isinstance(port, str):
                ports.append(port)
            elif isinstance(port, dict):
                # Long syntax
                target = port.get('target', '')
                published = port.get('published', '')
                protocol = port.get('protocol', 'tcp')
                if target and published:
                    ports.append(f"{published}:{target}/{protocol}")
                elif target:
                    ports.append(f"{target}/{protocol}")
            elif isinstance(port, (int, float)):
                ports.append(str(port))
        
        return ports
    
    def _extract_volumes(self, service_config: Dict[str, Any]) -> List[str]:
        """
        Extract volume mappings from service configuration.
        
        Handles various volume formats:
        - "./data:/var/lib/data" (host:container)
        - {"type": "bind", "source": "./data", "target": "/var/lib/data"}
        - "volume_name:/path"
        """
        volumes = []
        volume_config = service_config.get('volumes', [])
        
        if not volume_config:
            return volumes
            
        for volume in volume_config:
            if isinstance(volume, str):
                volumes.append(volume)
            elif isinstance(volume, dict):
                # Long syntax
                volume_type = volume.get('type', 'volume')
                source = volume.get('source', '')
                target = volume.get('target', '')
                
                if volume_type == 'bind' and source and target:
                    volumes.append(f"{source}:{target}")
                elif volume_type == 'volume' and source and target:
                    volumes.append(f"{source}:{target}")
                elif target:
                    volumes.append(target)
        
        return volumes
    
    def _extract_environment(self, service_config: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract environment variables from service configuration.
        
        Handles various environment formats:
        - List format: ["KEY=value", "KEY2=value2"]
        - Dictionary format: {"KEY": "value", "KEY2": "value2"}
        - env_file references (just notes the file, doesn't parse it)
        """
        env_vars = {}
        
        # Handle environment key
        env_config = service_config.get('environment', [])
        
        if isinstance(env_config, list):
            for env_item in env_config:
                if isinstance(env_item, str) and '=' in env_item:
                    key, value = env_item.split('=', 1)
                    env_vars[key] = value
                elif isinstance(env_item, str):
                    # Environment variable without value (inherits from host)
                    env_vars[env_item] = '${' + env_item + '}'
        elif isinstance(env_config, dict):
            for key, value in env_config.items():
                env_vars[key] = str(value) if value is not None else ''
        
        # Note if env_file is used (but don't parse the file)
        if 'env_file' in service_config:
            env_files = service_config['env_file']
            if isinstance(env_files, str):
                env_vars['_ENV_FILE'] = env_files
            elif isinstance(env_files, list) and env_files:
                env_vars['_ENV_FILES'] = ','.join(env_files)
        
        return env_vars
    
    def _extract_healthcheck(self, service_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract healthcheck configuration if present."""
        healthcheck = service_config.get('healthcheck')
        
        if not healthcheck:
            return None
            
        if isinstance(healthcheck, dict):
            return {
                'test': healthcheck.get('test', []),
                'interval': healthcheck.get('interval', '30s'),
                'timeout': healthcheck.get('timeout', '30s'),
                'retries': healthcheck.get('retries', 3),
                'start_period': healthcheck.get('start_period', '0s'),
                'disabled': healthcheck.get('disable', False)
            }
        
        return None