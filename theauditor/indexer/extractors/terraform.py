"""Terraform file extractor.

Handles extraction of Terraform/HCL infrastructure definitions including:
- Resource blocks (aws_instance, azurerm_storage_account, etc.)
- Variable declarations
- Output blocks
- Module configurations
- Provider settings
- Data source references

ARCHITECTURE: Database-first, zero fallbacks.
- Uses TerraformParser for structural HCL parsing (python-hcl2)
- NO regex fallbacks - hard fail if parsing fails
- Returns extracted data dict for indexer to store in database
- Facts go to repo_index.db terraform_* tables
- Graph edges built separately by TerraformGraphBuilder → graphs.db

CRITICAL: This extractor ONLY extracts facts from .tf files.
Graph relationships (variable → resource → output) are built in Phase 4 by graph builder.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from . import BaseExtractor
from ...terraform.parser import TerraformParser
from ...utils.logger import setup_logger

logger = setup_logger(__name__)


class TerraformExtractor(BaseExtractor):
    """Extractor for Terraform/HCL files."""

    def __init__(self, root_path: Path, ast_parser: Optional[Any] = None):
        """Initialize Terraform extractor with HCL parser.

        Args:
            root_path: Project root path
            ast_parser: Unused for Terraform (no tree-sitter support needed)
        """
        super().__init__(root_path, ast_parser)
        self.parser = TerraformParser()

    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this extractor supports."""
        return ['.tf', '.tfvars', '.tf.json']

    def extract(self, file_info: Dict[str, Any], content: str,
                tree: Optional[Any] = None) -> Dict[str, Any]:
        """Extract all relevant information from a Terraform file.

        Args:
            file_info: File metadata dictionary with 'path' key
            content: File content (unused - parser reads file directly)
            tree: Optional pre-parsed AST tree from tree-sitter HCL parser

        Returns:
            Dictionary containing all extracted data:
            {
                'terraform_file': {...},           # File metadata
                'terraform_resources': [...],      # Resource blocks
                'terraform_variables': [...],      # Variable declarations
                'terraform_outputs': [...],        # Output blocks
                'terraform_modules': [...],        # Module configurations (not stored to DB yet)
                'terraform_providers': [...],      # Provider settings (not stored to DB yet)
                'terraform_data': [...],           # Data source blocks (not stored to DB yet)
            }
        """
        file_path = file_info['path']

        # Skip .tfvars files for now (TODO: parse for variable values)
        if file_path.endswith('.tfvars'):
            logger.debug(f"Skipping .tfvars file (not yet supported): {file_path}")
            return {}

        try:
            # PREFERRED: Use tree-sitter if available (provides line numbers)
            if tree and tree.get('type') == 'tree_sitter' and tree.get('tree'):
                from ...ast_extractors import hcl_impl

                ts_tree = tree['tree']

                # Extract using tree-sitter HCL implementation
                resources = hcl_impl.extract_hcl_resources(ts_tree, content, file_path)
                variables = hcl_impl.extract_hcl_variables(ts_tree, content, file_path)
                outputs = hcl_impl.extract_hcl_outputs(ts_tree, content, file_path)
                data_sources = hcl_impl.extract_hcl_data_sources(ts_tree, content, file_path)

                # Convert tree-sitter format to parser format for compatibility
                parsed = {
                    'resources': self._convert_ts_resources(resources),
                    'variables': self._convert_ts_variables(variables),
                    'outputs': self._convert_ts_outputs(outputs),
                    'data': self._convert_ts_data(data_sources),
                    'modules': [],  # TODO: Add tree-sitter module extraction
                    'providers': [],  # TODO: Add tree-sitter provider extraction
                    'terraform': [],  # TODO: Add tree-sitter terraform block extraction
                }
            else:
                # FALLBACK: Use python-hcl2 parser (no line numbers)
                parsed = self.parser.parse_file(file_path)

            # Build file metadata record
            terraform_file = self._build_file_record(file_path, parsed)

            # Return extracted data for indexer to store in database
            # NOTE: Indexer will call db_manager.add_* methods to batch insert this data
            result = {
                'terraform_file': terraform_file,
                'terraform_resources': parsed['resources'],
                'terraform_variables': parsed['variables'],
                'terraform_outputs': parsed['outputs'],
                # Modules, providers, data not yet stored to database (Phase 7)
                # Keeping in result for future extension
                'terraform_modules': parsed['modules'],
                'terraform_providers': parsed['providers'],
                'terraform_data': parsed['data'],
            }

            logger.debug(
                f"Extracted Terraform: {file_path} → "
                f"{len(parsed['resources'])} resources, "
                f"{len(parsed['variables'])} variables, "
                f"{len(parsed['outputs'])} outputs"
            )

            return result

        except Exception as e:
            # Hard fail - no fallback parsing
            # Log error and return empty dict (file will be skipped)
            logger.error(f"Failed to extract Terraform from {file_path}: {e}")
            return {}

    def _build_file_record(self, file_path: str, parsed: Dict) -> Dict[str, Any]:
        """Build terraform_files table record.

        Args:
            file_path: Path to Terraform file
            parsed: Parsed Terraform data from TerraformParser

        Returns:
            Dict with terraform_files table columns
        """
        # Detect if this is a module file
        is_module = 'modules/' in file_path or '/module/' in file_path

        # Extract module name from path (e.g., "modules/vpc/main.tf" → "vpc")
        module_name = None
        if is_module:
            parts = Path(file_path).parts
            if 'modules' in parts:
                idx = parts.index('modules')
                if idx + 1 < len(parts):
                    module_name = parts[idx + 1]

        # Detect backend type from terraform {} blocks
        backend_type = self._detect_backend_type(parsed)

        # Serialize providers to JSON
        providers_json = json.dumps(parsed['providers']) if parsed['providers'] else None

        return {
            'file_path': file_path,
            'module_name': module_name,
            'stack_name': None,  # TODO: Detect stack from directory structure or tags
            'backend_type': backend_type,
            'providers_json': providers_json,
            'is_module': is_module,
            'module_source': None,  # Populated for module {} blocks in Phase 7
        }

    def _detect_backend_type(self, parsed: Dict) -> Optional[str]:
        """Detect Terraform backend type from terraform {} blocks.

        Args:
            parsed: Parsed Terraform data

        Returns:
            Backend type string ('s3', 'local', 'remote', etc.) or None
        """
        # Terraform blocks define backend configuration
        # Format: terraform { backend "s3" { ... } }
        terraform_blocks = parsed.get('terraform', [])
        for block in terraform_blocks:
            if not isinstance(block, dict):
                continue
            backend = block.get('backend', {})
            if backend and isinstance(backend, dict):
                # backend is a dict like {'s3': {...}} or {'local': {...}}
                backend_types = list(backend.keys())
                if backend_types:
                    return backend_types[0]
        return None

    def _convert_ts_resources(self, ts_resources: List[Dict]) -> List[Dict]:
        """Convert tree-sitter resource format to TerraformParser format.

        Args:
            ts_resources: Resources from hcl_impl (with line/column)

        Returns:
            Resources in TerraformParser format matching database schema
        """
        return [
            {
                'resource_id': f"{r['file_path']}::{r['resource_type']}.{r['resource_name']}",
                'file_path': r['file_path'],
                'resource_type': r['resource_type'],
                'resource_name': r['resource_name'],
                'properties': {},  # TODO: Extract attributes from tree-sitter body node
                'depends_on': [],
                'sensitive_properties': [],
                'line': r['line'],  # Tree-sitter advantage: precise line numbers!
            }
            for r in ts_resources
        ]

    def _convert_ts_variables(self, ts_variables: List[Dict]) -> List[Dict]:
        """Convert tree-sitter variable format to TerraformParser format.

        Args:
            ts_variables: Variables from hcl_impl (with line/column)

        Returns:
            Variables in TerraformParser format matching database schema
        """
        return [
            {
                'variable_id': f"{v['file_path']}::{v['variable_name']}",
                'file_path': v['file_path'],
                'variable_name': v['variable_name'],
                'variable_type': None,  # TODO: Extract from tree-sitter
                'default': None,
                'is_sensitive': False,
                'description': '',
                'line': v['line'],  # Tree-sitter advantage: precise line numbers!
            }
            for v in ts_variables
        ]

    def _convert_ts_outputs(self, ts_outputs: List[Dict]) -> List[Dict]:
        """Convert tree-sitter output format to TerraformParser format.

        Args:
            ts_outputs: Outputs from hcl_impl (with line/column)

        Returns:
            Outputs in TerraformParser format matching database schema
        """
        return [
            {
                'output_id': f"{o['file_path']}::{o['output_name']}",
                'file_path': o['file_path'],
                'output_name': o['output_name'],
                'value': None,  # TODO: Extract from tree-sitter
                'is_sensitive': False,
                'description': '',
                'line': o['line'],  # Tree-sitter advantage: precise line numbers!
            }
            for o in ts_outputs
        ]

    def _convert_ts_data(self, ts_data: List[Dict]) -> List[Dict]:
        """Convert tree-sitter data source format to TerraformParser format.

        Args:
            ts_data: Data sources from hcl_impl (with line/column)

        Returns:
            Data sources in TerraformParser format matching database schema
        """
        return [
            {
                'data_id': f"{d['file_path']}::data.{d['data_type']}.{d['data_name']}",
                'file_path': d['file_path'],
                'data_type': d['data_type'],
                'data_name': d['data_name'],
                'properties': {},  # TODO: Extract from tree-sitter
                'line': d['line'],  # Tree-sitter advantage: precise line numbers!
            }
            for d in ts_data
        ]
