"""Terraform HCL parser - structural parsing with zero fallbacks.

This module provides structural parsing of Terraform/HCL files using python-hcl2.
NO regex fallbacks. NO heuristics. If parsing fails, hard fail with actionable error.

Architecture:
- Uses python-hcl2 for canonical parsing
- Emits normalized dictionaries for database insertion
- Zero tolerance for malformed HCL - fail loud

Usage:
    parser = TerraformParser()
    result = parser.parse_file("main.tf")
    # result contains: resources, variables, outputs, modules, providers
"""

import hcl2
from pathlib import Path
from typing import Dict, List, Any, Optional


class TerraformParser:
    """Parse Terraform/HCL files structurally."""

    def __init__(self):
        """Initialize parser."""
        pass

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Parse a Terraform file and return normalized structure.

        Args:
            file_path: Path to .tf file

        Returns:
            Dict with keys: resources, variables, outputs, modules, providers, data

        Raises:
            ValueError: If file cannot be parsed (malformed HCL)
            FileNotFoundError: If file doesn't exist
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Terraform file not found: {file_path}")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                # Parse using python-hcl2 (canonical parser)
                parsed = hcl2.load(f)
        except Exception as e:
            # Hard fail - NO fallback parsing
            raise ValueError(f"Failed to parse Terraform file {file_path}: {e}")

        # Normalize parsed structure
        return {
            'resources': self._extract_resources(parsed, file_path),
            'variables': self._extract_variables(parsed, file_path),
            'outputs': self._extract_outputs(parsed, file_path),
            'modules': self._extract_modules(parsed, file_path),
            'providers': self._extract_providers(parsed, file_path),
            'data': self._extract_data_blocks(parsed, file_path),
        }

    def _extract_resources(self, parsed: Dict, file_path: str) -> List[Dict[str, Any]]:
        """Extract resource blocks."""
        resources = []
        for resource_block in parsed.get('resource', []):
            for resource_type, resources_of_type in resource_block.items():
                for resource_name, properties in resources_of_type.items():
                    resources.append({
                        'resource_id': f"{file_path}::{resource_type}.{resource_name}",
                        'file_path': file_path,
                        'resource_type': resource_type,
                        'resource_name': resource_name,
                        'properties': properties,
                        'depends_on': properties.get('depends_on', []) if isinstance(properties, dict) else [],
                        'sensitive_properties': self._identify_sensitive_properties(properties) if isinstance(properties, dict) else [],
                    })
        return resources

    def _extract_variables(self, parsed: Dict, file_path: str) -> List[Dict[str, Any]]:
        """Extract variable declarations."""
        variables = []
        for var_block in parsed.get('variable', []):
            for var_name, var_def in var_block.items():
                # var_def might be None or dict
                if var_def is None:
                    var_def = {}
                variables.append({
                    'variable_id': f"{file_path}::{var_name}",
                    'file_path': file_path,
                    'variable_name': var_name,
                    'variable_type': var_def.get('type'),
                    'default': var_def.get('default'),
                    'is_sensitive': var_def.get('sensitive', False),
                    'description': var_def.get('description', ''),
                })
        return variables

    def _extract_outputs(self, parsed: Dict, file_path: str) -> List[Dict[str, Any]]:
        """Extract output blocks."""
        outputs = []
        for output_block in parsed.get('output', []):
            for output_name, output_def in output_block.items():
                if output_def is None:
                    output_def = {}
                outputs.append({
                    'output_id': f"{file_path}::{output_name}",
                    'file_path': file_path,
                    'output_name': output_name,
                    'value': output_def.get('value'),
                    'is_sensitive': output_def.get('sensitive', False),
                    'description': output_def.get('description', ''),
                })
        return outputs

    def _extract_modules(self, parsed: Dict, file_path: str) -> List[Dict[str, Any]]:
        """Extract module blocks."""
        modules = []
        for module_block in parsed.get('module', []):
            for module_name, module_def in module_block.items():
                if module_def is None:
                    module_def = {}
                modules.append({
                    'module_name': module_name,
                    'source': module_def.get('source'),
                    'inputs': {k: v for k, v in module_def.items() if k not in ['source']},
                })
        return modules

    def _extract_providers(self, parsed: Dict, file_path: str) -> List[Dict[str, Any]]:
        """Extract provider configurations."""
        providers = []
        for provider_block in parsed.get('provider', []):
            for provider_name, provider_config in provider_block.items():
                if provider_config is None:
                    provider_config = {}
                providers.append({
                    'provider_name': provider_name,
                    'config': provider_config,
                })
        return providers

    def _extract_data_blocks(self, parsed: Dict, file_path: str) -> List[Dict[str, Any]]:
        """Extract data source blocks."""
        data_sources = []
        for data_block in parsed.get('data', []):
            for data_type, data_of_type in data_block.items():
                for data_name, properties in data_of_type.items():
                    data_sources.append({
                        'data_id': f"{file_path}::data.{data_type}.{data_name}",
                        'file_path': file_path,
                        'data_type': data_type,
                        'data_name': data_name,
                        'properties': properties if isinstance(properties, dict) else {},
                    })
        return data_sources

    def _identify_sensitive_properties(self, properties: Dict) -> List[str]:
        """Identify which properties contain sensitive data."""
        sensitive = []
        # Common sensitive property patterns
        sensitive_keywords = ['password', 'secret', 'key', 'token', 'credential']
        for prop_name in properties.keys():
            if any(keyword in prop_name.lower() for keyword in sensitive_keywords):
                sensitive.append(prop_name)
        return sensitive
