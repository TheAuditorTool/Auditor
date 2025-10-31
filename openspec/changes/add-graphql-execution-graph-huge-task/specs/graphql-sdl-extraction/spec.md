## ADDED Requirements

### Requirement: GraphQL SDL Extractor Implementation
The GraphQL extractor MUST parse SDL files using graphql-core and return structured data dicts.

#### Scenario: Extractor Follows BaseExtractor Pattern
- **GIVEN** all extractors inherit from BaseExtractor with @register_extractor decorator
- **WHEN** implementing GraphQL SDL extraction
- **THEN** it follows this structure:
```python
"""GraphQL SDL (Schema Definition Language) extractor.

Parses .graphql, .gql, and .graphqls files using graphql-core library.
Extracts schema structure (types, fields, arguments, directives) without
executing or validating queries.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from graphql import parse, DocumentNode
    from graphql.language import ast as graphql_ast
    GRAPHQL_AVAILABLE = True
except ImportError:
    GRAPHQL_AVAILABLE = False

from theauditor.indexer.extractors import BaseExtractor, register_extractor


@register_extractor
class GraphQLExtractor(BaseExtractor):
    """Extracts GraphQL schema definitions from SDL files."""

    def __init__(self, root_path: Path, ast_parser):
        """Initialize GraphQL extractor.

        Args:
            root_path: Project root directory
            ast_parser: AST parser (not used for GraphQL - we use graphql-core directly)
        """
        super().__init__(root_path, ast_parser)
        if not GRAPHQL_AVAILABLE:
            raise ImportError("graphql-core not available - cannot parse GraphQL SDL")

    @property
    def supported_extensions(self) -> List[str]:
        """Return file extensions this extractor handles."""
        return ['.graphql', '.gql', '.graphqls']

    def extract(self, file_info: Dict, content: str, tree: Optional[Any] = None) -> Dict[str, List]:
        """Extract GraphQL schema structure from SDL content.

        Args:
            file_info: Dictionary with file metadata (path, size, etc.)
            content: SDL file content as string
            tree: Unused (graphql-core provides its own AST)

        Returns:
            Dictionary with keys:
            - graphql_schemas: [schema_record]
            - graphql_types: [type_records...]
            - graphql_fields: [field_records...]
            - graphql_field_args: [arg_records...]
        """
        file_path = file_info['path']

        try:
            # Parse SDL to AST using graphql-core
            document = parse(content)
        except Exception as e:
            # Syntax error in SDL - skip with debug log
            if self._debug:
                print(f"[DEBUG] GraphQL parse error in {file_path}: {e}")
            return {}

        # Compute schema hash for deduplication
        schema_hash = hashlib.sha256(content.encode()).hexdigest()

        # Initialize extraction results
        schema_record = {
            'file_path': file_path,
            'schema_hash': schema_hash,
            'language': 'sdl',
            'last_modified': file_info.get('last_modified')
        }

        type_records = []
        field_records = []
        arg_records = []

        # Walk AST definitions
        for definition in document.definitions:
            if isinstance(definition, graphql_ast.ObjectTypeDefinitionNode):
                self._extract_object_type(definition, file_path, type_records, field_records, arg_records)
            elif isinstance(definition, graphql_ast.InterfaceTypeDefinitionNode):
                self._extract_interface_type(definition, file_path, type_records, field_records, arg_records)
            elif isinstance(definition, graphql_ast.UnionTypeDefinitionNode):
                self._extract_union_type(definition, file_path, type_records)
            elif isinstance(definition, graphql_ast.EnumTypeDefinitionNode):
                self._extract_enum_type(definition, file_path, type_records)
            elif isinstance(definition, graphql_ast.InputObjectTypeDefinitionNode):
                self._extract_input_type(definition, file_path, type_records, field_records, arg_records)
            elif isinstance(definition, graphql_ast.ScalarTypeDefinitionNode):
                self._extract_scalar_type(definition, file_path, type_records)

        return {
            'graphql_schemas': [schema_record],
            'graphql_types': type_records,
            'graphql_fields': field_records,
            'graphql_field_args': arg_records
        }

    def _extract_object_type(self, node: graphql_ast.ObjectTypeDefinitionNode,
                            file_path: str, type_records: List, field_records: List,
                            arg_records: List):
        """Extract ObjectType definition (Query, Mutation, custom types)."""
        type_id = self._generate_type_id(file_path, node.name.value)

        # Extract interfaces this type implements
        implements = None
        if node.interfaces:
            implements = json.dumps([iface.name.value for iface in node.interfaces])

        # Extract directives
        directives_json = self._extract_directives(node.directives)

        type_records.append({
            'type_id': type_id,
            'schema_path': file_path,
            'type_name': node.name.value,
            'kind': 'OBJECT',
            'implements': implements,
            'description': self._extract_description(node),
            'line': node.loc.start_token.line if node.loc else None,
            'column': node.loc.start_token.column if node.loc else None
        })

        # Extract fields
        if node.fields:
            for field in node.fields:
                self._extract_field(field, type_id, file_path, field_records, arg_records)

    def _extract_interface_type(self, node: graphql_ast.InterfaceTypeDefinitionNode,
                                file_path: str, type_records: List, field_records: List,
                                arg_records: List):
        """Extract Interface definition."""
        type_id = self._generate_type_id(file_path, node.name.value)

        # Interfaces can implement other interfaces (GraphQL spec)
        implements = None
        if hasattr(node, 'interfaces') and node.interfaces:
            implements = json.dumps([iface.name.value for iface in node.interfaces])

        type_records.append({
            'type_id': type_id,
            'schema_path': file_path,
            'type_name': node.name.value,
            'kind': 'INTERFACE',
            'implements': implements,
            'description': self._extract_description(node),
            'line': node.loc.start_token.line if node.loc else None,
            'column': node.loc.start_token.column if node.loc else None
        })

        # Extract fields
        if node.fields:
            for field in node.fields:
                self._extract_field(field, type_id, file_path, field_records, arg_records)

    def _extract_union_type(self, node: graphql_ast.UnionTypeDefinitionNode,
                           file_path: str, type_records: List):
        """Extract Union definition."""
        type_id = self._generate_type_id(file_path, node.name.value)

        # Union types list in implements field (reusing column for member types)
        implements = None
        if node.types:
            implements = json.dumps([t.name.value for t in node.types])

        type_records.append({
            'type_id': type_id,
            'schema_path': file_path,
            'type_name': node.name.value,
            'kind': 'UNION',
            'implements': implements,
            'description': self._extract_description(node),
            'line': node.loc.start_token.line if node.loc else None,
            'column': node.loc.start_token.column if node.loc else None
        })

    def _extract_enum_type(self, node: graphql_ast.EnumTypeDefinitionNode,
                          file_path: str, type_records: List):
        """Extract Enum definition."""
        type_id = self._generate_type_id(file_path, node.name.value)

        # Enum values stored in implements as JSON array (reusing column)
        implements = None
        if node.values:
            implements = json.dumps([v.name.value for v in node.values])

        type_records.append({
            'type_id': type_id,
            'schema_path': file_path,
            'type_name': node.name.value,
            'kind': 'ENUM',
            'implements': implements,
            'description': self._extract_description(node),
            'line': node.loc.start_token.line if node.loc else None,
            'column': node.loc.start_token.column if node.loc else None
        })

    def _extract_input_type(self, node: graphql_ast.InputObjectTypeDefinitionNode,
                           file_path: str, type_records: List, field_records: List,
                           arg_records: List):
        """Extract InputObject definition (for mutation inputs)."""
        type_id = self._generate_type_id(file_path, node.name.value)

        type_records.append({
            'type_id': type_id,
            'schema_path': file_path,
            'type_name': node.name.value,
            'kind': 'INPUT_OBJECT',
            'implements': None,
            'description': self._extract_description(node),
            'line': node.loc.start_token.line if node.loc else None,
            'column': node.loc.start_token.column if node.loc else None
        })

        # Extract input fields (treated as field + arg combined)
        if node.fields:
            for input_field in node.fields:
                self._extract_input_field(input_field, type_id, file_path, field_records)

    def _extract_scalar_type(self, node: graphql_ast.ScalarTypeDefinitionNode,
                            file_path: str, type_records: List):
        """Extract custom Scalar definition."""
        type_id = self._generate_type_id(file_path, node.name.value)

        type_records.append({
            'type_id': type_id,
            'schema_path': file_path,
            'type_name': node.name.value,
            'kind': 'SCALAR',
            'implements': None,
            'description': self._extract_description(node),
            'line': node.loc.start_token.line if node.loc else None,
            'column': node.loc.start_token.column if node.loc else None
        })

    def _extract_field(self, field_node: graphql_ast.FieldDefinitionNode,
                      type_id: int, file_path: str, field_records: List,
                      arg_records: List):
        """Extract field definition from type."""
        field_id = self._generate_field_id(file_path, type_id, field_node.name.value)

        # Parse return type (handles NonNull, List wrappers)
        return_type, is_list, is_nullable = self._parse_type(field_node.type)

        # Extract directives (@deprecated, @auth, etc.)
        directives_json = self._extract_directives(field_node.directives)

        field_records.append({
            'field_id': field_id,
            'type_id': type_id,
            'field_name': field_node.name.value,
            'return_type': return_type,
            'is_list': is_list,
            'is_nullable': is_nullable,
            'directives_json': directives_json,
            'description': self._extract_description(field_node),
            'line': field_node.loc.start_token.line if field_node.loc else None,
            'column': field_node.loc.start_token.column if field_node.loc else None
        })

        # Extract field arguments
        if field_node.arguments:
            for arg in field_node.arguments:
                self._extract_argument(arg, field_id, arg_records)

    def _extract_argument(self, arg_node: graphql_ast.InputValueDefinitionNode,
                         field_id: int, arg_records: List):
        """Extract field argument definition."""
        # Parse argument type
        arg_type, _, is_nullable = self._parse_type(arg_node.type)

        # Check for default value
        has_default = arg_node.default_value is not None
        default_value = None
        if has_default:
            default_value = self._serialize_value(arg_node.default_value)

        # Extract directives
        directives_json = self._extract_directives(arg_node.directives)

        arg_records.append({
            'field_id': field_id,
            'arg_name': arg_node.name.value,
            'arg_type': arg_type,
            'has_default': has_default,
            'default_value': default_value,
            'is_nullable': is_nullable,
            'directives_json': directives_json
        })

    def _parse_type(self, type_node) -> tuple:
        """Parse GraphQL type recursively handling NonNull and List wrappers.

        Returns:
            (base_type_name, is_list, is_nullable)
        """
        is_list = False
        is_nullable = True

        # Unwrap NonNull
        if isinstance(type_node, graphql_ast.NonNullTypeNode):
            is_nullable = False
            type_node = type_node.type

        # Unwrap List
        if isinstance(type_node, graphql_ast.ListTypeNode):
            is_list = True
            type_node = type_node.type
            # Check if list elements are nullable
            if isinstance(type_node, graphql_ast.NonNullTypeNode):
                type_node = type_node.type

        # Get base type name
        if isinstance(type_node, graphql_ast.NamedTypeNode):
            return (type_node.name.value, is_list, is_nullable)

        return ('Unknown', is_list, is_nullable)

    def _extract_directives(self, directives) -> Optional[str]:
        """Extract directives as JSON array."""
        if not directives:
            return None

        directive_list = []
        for directive in directives:
            directive_dict = {
                'name': directive.name.value,
                'arguments': {}
            }
            if directive.arguments:
                for arg in directive.arguments:
                    directive_dict['arguments'][arg.name.value] = self._serialize_value(arg.value)
            directive_list.append(directive_dict)

        return json.dumps(directive_list)

    def _extract_description(self, node) -> Optional[str]:
        """Extract description/docstring from node."""
        if hasattr(node, 'description') and node.description:
            return node.description.value
        return None

    def _serialize_value(self, value_node) -> str:
        """Serialize AST value node to JSON-compatible string."""
        if isinstance(value_node, graphql_ast.IntValueNode):
            return value_node.value
        elif isinstance(value_node, graphql_ast.FloatValueNode):
            return value_node.value
        elif isinstance(value_node, graphql_ast.StringValueNode):
            return value_node.value
        elif isinstance(value_node, graphql_ast.BooleanValueNode):
            return str(value_node.value).lower()
        elif isinstance(value_node, graphql_ast.NullValueNode):
            return 'null'
        elif isinstance(value_node, graphql_ast.EnumValueNode):
            return value_node.value
        elif isinstance(value_node, graphql_ast.ListValueNode):
            return json.dumps([self._serialize_value(v) for v in value_node.values])
        elif isinstance(value_node, graphql_ast.ObjectValueNode):
            return json.dumps({f.name.value: self._serialize_value(f.value) for f in value_node.fields})
        return 'null'

    def _generate_type_id(self, file_path: str, type_name: str) -> int:
        """Generate deterministic type ID from file path and type name."""
        return hash(f"{file_path}:{type_name}") & 0x7FFFFFFF  # Positive int

    def _generate_field_id(self, file_path: str, type_id: int, field_name: str) -> int:
        """Generate deterministic field ID."""
        return hash(f"{file_path}:{type_id}:{field_name}") & 0x7FFFFFFF
```
- **AND** extractor returns dict with 4 keys matching DataStorer handler names
- **AND** uses graphql-core parse() for SDL parsing (not regex)
- **AND** handles all GraphQL type kinds (OBJECT, INTERFACE, UNION, ENUM, INPUT_OBJECT, SCALAR)
- **AND** extracts directives as JSON for rule consumption
- **AND** computes schema_hash for deduplication

### Requirement: Config Extension Registration
The config module MUST add GraphQL extensions to SUPPORTED_AST_EXTENSIONS list.

#### Scenario: Extensions Added to Config
- **GIVEN** `theauditor/indexer/config.py` defines SUPPORTED_AST_EXTENSIONS list
- **WHEN** adding GraphQL support
- **THEN** it includes GraphQL extensions:
```python
# File extensions that support AST parsing
SUPPORTED_AST_EXTENSIONS: List[str] = [
    ".py",      # Python
    ".js",      # JavaScript
    ".jsx",     # React JavaScript
    ".ts",      # TypeScript
    ".tsx",     # React TypeScript
    ".mjs",     # ES Module JavaScript
    ".cjs",     # CommonJS JavaScript
    ".tf",      # Terraform/HCL
    ".tfvars",  # Terraform variables
    ".graphql", # GraphQL SDL (NEW)
    ".gql",     # GraphQL SDL shorthand (NEW)
    ".graphqls",# GraphQL SDL schema (NEW)
]
```
- **AND** extensions appear after Terraform extensions alphabetically
- **AND** FileWalker will now discover .graphql/.gql/.graphqls files during indexing

### Requirement: Extractor Registry Auto-Discovery
The extractor registry MUST automatically discover and register GraphQLExtractor via decorator.

#### Scenario: Extractor Registration Happens Automatically
- **GIVEN** ExtractorRegistry scans for @register_extractor decorated classes
- **WHEN** GraphQLExtractor module is imported
- **THEN** it's automatically registered:
```python
# In theauditor/indexer/extractors/__init__.py
from .graphql import GraphQLExtractor  # Import triggers registration

# ExtractorRegistry automatically includes GraphQLExtractor
# No manual registration needed
```
- **AND** registry maps ['.graphql', '.gql', '.graphqls'] → GraphQLExtractor instance
- **AND** FileWalker will route .graphql files to GraphQLExtractor during indexing
- **AND** verification command confirms registration:
```python
from theauditor.indexer.extractors import ExtractorRegistry
from pathlib import Path

registry = ExtractorRegistry(Path('.'), None)
print([e.__class__.__name__ for e in registry.extractors.values()])
# Output includes: [..., 'GraphQLExtractor', ...]
```
