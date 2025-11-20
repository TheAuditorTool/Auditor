"""Terraform file extractor.

Handles extraction of Terraform/HCL infrastructure definitions including:
- Resource blocks (aws_instance, azurerm_storage_account, etc.)
- Variable declarations
- Output blocks
- Module configurations
- Provider settings
- Data source references

ARCHITECTURE: Database-first, zero fallbacks.
- Uses tree-sitter HCL parser for structural extraction
- NO regex fallbacks - hard fail if parsing fails
- Returns extracted data dict for indexer to store in database
- Facts go to repo_index.db terraform_* tables
- Graph edges built separately by TerraformGraphBuilder → graphs.db

CRITICAL: This extractor ONLY extracts facts from .tf files.
Graph relationships (variable → resource → output) are built in Phase 4 by graph builder.
"""


import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from . import BaseExtractor
from ...utils.logger import setup_logger

logger = setup_logger(__name__)


class TerraformExtractor(BaseExtractor):
    """Extractor for Terraform/HCL files."""

    def __init__(self, root_path: Path, ast_parser: Any | None = None):
        """Initialize Terraform extractor."""
        super().__init__(root_path, ast_parser)

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return ['.tf', '.tfvars', '.tf.json']

    def extract(self, file_info: dict[str, Any], content: str,
                tree: Any | None = None) -> dict[str, Any]:
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

        # Dedicated parsing path for tfvars files (variable assignments only)
        if file_path.endswith('.tfvars'):
            return self._extract_tfvars(file_path, content, tree)

        try:
            if not (tree and tree.get('type') == 'tree_sitter' and tree.get('tree')):
                logger.error(
                    "Tree-sitter HCL parser unavailable for %s. Run 'aud setup-ai' to install language support.",
                    file_path,
                )
                return {}

            from ...ast_extractors import hcl_impl

            ts_tree = tree['tree']

            # Extract using tree-sitter HCL implementation
            resources = hcl_impl.extract_hcl_resources(ts_tree, content, file_path)
            variables = hcl_impl.extract_hcl_variables(ts_tree, content, file_path)
            outputs = hcl_impl.extract_hcl_outputs(ts_tree, content, file_path)
            data_sources = hcl_impl.extract_hcl_data_sources(ts_tree, content, file_path)

            parsed = {
                'resources': self._convert_ts_resources(resources),
                'variables': self._convert_ts_variables(variables),
                'outputs': self._convert_ts_outputs(outputs),
                'data': self._convert_ts_data(data_sources),
                'modules': [],  # TODO: Add tree-sitter module extraction
                'providers': [],  # TODO: Add tree-sitter provider extraction
                'terraform': [],  # TODO: Add tree-sitter terraform block extraction
            }

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

    def _build_file_record(self, file_path: str, parsed: dict) -> dict[str, Any]:
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

    def _detect_backend_type(self, parsed: dict) -> str | None:
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

    def _convert_ts_resources(self, ts_resources: list[dict]) -> list[dict]:
        """Convert tree-sitter resource format to TerraformParser format.

        Args:
            ts_resources: Resources from hcl_impl (with line/column)

        Returns:
            Resources in TerraformParser format matching database schema
        """
        converted = []
        for resource in ts_resources:
            attributes = self._normalize_hcl_attributes(resource.get('attributes', {}))
            depends_on = attributes.pop('depends_on', [])

            converted.append({
                'resource_id': f"{resource['file_path']}::{resource['resource_type']}.{resource['resource_name']}",
                'file_path': resource['file_path'],
                'resource_type': resource['resource_type'],
                'resource_name': resource['resource_name'],
                'properties': attributes,
                'depends_on': depends_on,
                'sensitive_properties': self._identify_sensitive_properties(attributes),
                'line': resource['line'],
            })

        return converted

    def _convert_ts_variables(self, ts_variables: list[dict]) -> list[dict]:
        """Convert tree-sitter variable format to TerraformParser format.

        Args:
            ts_variables: Variables from hcl_impl (with line/column and attributes)

        Returns:
            Variables in TerraformParser format matching database schema
        """
        converted = []
        for v in ts_variables:
            attrs = v.get('attributes', {})

            # Parse sensitive flag
            sensitive_value = attrs.get('sensitive', 'false')
            is_sensitive = str(sensitive_value).lower() == 'true'

            # Parse variable type
            var_type = attrs.get('type')
            if var_type:
                var_type = str(var_type).strip('"')

            # Parse description
            description = attrs.get('description', '')
            if description:
                description = str(description).strip('"')

            # Parse default value
            default_value = attrs.get('default')

            converted.append({
                'variable_id': f"{v['file_path']}::{v['variable_name']}",
                'file_path': v['file_path'],
                'variable_name': v['variable_name'],
                'variable_type': var_type,
                'default': default_value,
                'is_sensitive': is_sensitive,
                'description': description,
                'line': v['line'],
            })

        return converted

    def _convert_ts_outputs(self, ts_outputs: list[dict]) -> list[dict]:
        """Convert tree-sitter output format to TerraformParser format.

        Args:
            ts_outputs: Outputs from hcl_impl (with line/column and attributes)

        Returns:
            Outputs in TerraformParser format matching database schema
        """
        converted = []
        for o in ts_outputs:
            attrs = o.get('attributes', {})

            # Parse sensitive flag
            sensitive_value = attrs.get('sensitive', 'false')
            is_sensitive = str(sensitive_value).lower() == 'true'

            # Parse value expression
            value = attrs.get('value')

            # Parse description
            description = attrs.get('description', '')
            if description:
                description = str(description).strip('"')

            converted.append({
                'output_id': f"{o['file_path']}::{o['output_name']}",
                'file_path': o['file_path'],
                'output_name': o['output_name'],
                'value': value,
                'is_sensitive': is_sensitive,
                'description': description,
                'line': o['line'],
            })

        return converted

    def _convert_ts_data(self, ts_data: list[dict]) -> list[dict]:
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

    def _normalize_hcl_attributes(self, attributes: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, raw_value in attributes.items():
            if key == 'depends_on':
                normalized[key] = self._parse_depends_on(raw_value)
            else:
                normalized[key] = self._interpret_hcl_value(raw_value)
        return normalized

    def _interpret_hcl_value(self, value: Any) -> Any:
        if isinstance(value, (bool, int, float)):
            return value
        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return text

        lowered = text.lower()
        if lowered in ('true', 'false'):
            return lowered == 'true'
        if lowered == 'null':
            return None

        if text.startswith('"') and text.endswith('"') and len(text) >= 2:
            return text[1:-1]

        try:
            if '.' in text:
                return float(text)
            return int(text)
        except ValueError:
            pass

        if text.startswith('[') and text.endswith(']'):
            inner = text[1:-1].strip()
            if inner:
                parts = [p.strip().strip('"') for p in inner.split(',') if p.strip()]
                return parts
            return []

        return text

    def _parse_depends_on(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip().strip('"') for item in value if str(item).strip()]

        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith('[') and stripped.endswith(']'):
                stripped = stripped[1:-1]
            parts = [part.strip().strip('"') for part in stripped.split(',') if part.strip()]
            return parts

        return []

    def _strip_inline_comment(self, text: str) -> str:
        result = []
        in_string = False
        escape = False
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '"' and not escape:
                in_string = not in_string
            if not in_string and not escape:
                if ch == '#':
                    break
                if ch == '/' and i + 1 < len(text) and text[i + 1] == '/':
                    break
            result.append(ch)
            escape = (ch == '\\' and not escape)
            if escape and ch != '\\':
                escape = False
            i += 1
        return ''.join(result).rstrip()

    def _detect_heredoc_marker(self, text: str) -> str | None:
        match = re.match(r"<<-?\s*\"?([A-Za-z0-9_]+)\"?", text)
        if match:
            return match.group(1)
        return None

    def _brace_delta(self, text: str | None) -> int:
        if not text:
            return 0
        delta = 0
        in_string = False
        escape = False
        for ch in text:
            if ch == '"' and not escape:
                in_string = not in_string
            if not in_string:
                if ch in '{[':
                    delta += 1
                elif ch in '}]':
                    delta -= 1
            escape = (ch == '\\' and not escape)
            if escape and ch != '\\':
                escape = False
        return delta

    def _extract_tfvars(self, file_path: str, content: str,
                        tree: Any | None) -> dict[str, Any]:
        """Extract variable assignments from .tfvars files without hcl2."""
        if content is None:
            try:
                with open(file_path, encoding='utf-8') as handle:
                    content = handle.read()
            except Exception as exc:
                logger.error(f"Failed to read .tfvars file {file_path}: {exc}")
                return {}

        lines = content.splitlines()
        variable_values: list[dict[str, Any]] = []
        idx = 0

        while idx < len(lines):
            raw_line = lines[idx]
            stripped = raw_line.strip()

            if not stripped or stripped.startswith(('#', '//')):
                idx += 1
                continue

            if '=' not in stripped:
                idx += 1
                continue

            key_part, remainder = raw_line.split('=', 1)
            key = key_part.strip()
            if not key:
                idx += 1
                continue

            start_line = idx + 1
            remainder = self._strip_inline_comment(remainder).strip()
            heredoc_marker = self._detect_heredoc_marker(remainder)
            value_lines: list[str] = []

            idx += 1

            if heredoc_marker:
                # Collect lines until the heredoc terminator (exclusive)
                value_lines.clear()
                while idx < len(lines):
                    current = lines[idx]
                    if current.strip() == heredoc_marker:
                        idx += 1
                        break
                    value_lines.append(current.rstrip())
                    idx += 1
            else:
                depth = 0
                if remainder:
                    value_lines.append(remainder)
                    depth = self._brace_delta(remainder)
                else:
                    # Value may start on following line
                    while idx < len(lines):
                        current = self._strip_inline_comment(lines[idx])
                        if not current.strip():
                            idx += 1
                            continue
                        value_lines.append(current.rstrip())
                        depth = self._brace_delta(current)
                        idx += 1
                        break

                while idx < len(lines) and depth > 0:
                    current = self._strip_inline_comment(lines[idx])
                    value_lines.append(current.rstrip())
                    depth += self._brace_delta(current)
                    idx += 1

            value_text = '\n'.join(line for line in value_lines if line is not None).strip()
            if not value_text:
                continue

            variable_values.append({
                'file_path': file_path,
                'variable_name': key,
                'variable_value': value_text,
                'line': start_line,
                'is_sensitive_context': self._is_sensitive_value(key, value_text),
            })

        if not variable_values:
            return {}

        logger.debug(
            f"Extracted {len(variable_values)} Terraform variable assignments from {file_path}"
        )
        return {'terraform_variable_values': variable_values}

    def _is_sensitive_value(self, key: str, value: Any) -> bool:
        """Heuristic detection for sensitive tfvars entries."""
        sensitive_keywords = (
            'password', 'secret', 'token', 'key', 'credential', 'private', 'auth'
        )
        key_lower = key.lower()
        if any(word in key_lower for word in sensitive_keywords):
            return True

        if isinstance(value, str):
            value_lower = value.lower()
            return any(word in value_lower for word in sensitive_keywords)

        return False

    def _identify_sensitive_properties(self, properties: dict[str, Any]) -> list[str]:
        sensitive = []
        keywords = ('password', 'secret', 'key', 'token', 'credential', 'private')
        for prop_name in properties.keys():
            lower = prop_name.lower()
            if any(keyword in lower for keyword in keywords):
                sensitive.append(prop_name)
        return sensitive
