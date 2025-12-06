"""GraphQL SDL extractor for schema definition language files."""

import hashlib
import json
from typing import Any

from graphql import DefinitionNode, parse
from graphql.language.ast import (
    DirectiveNode,
    EnumTypeDefinitionNode,
    FieldDefinitionNode,
    InputObjectTypeDefinitionNode,
    InputValueDefinitionNode,
    InterfaceTypeDefinitionNode,
    ListTypeNode,
    NamedTypeNode,
    NonNullTypeNode,
    ObjectTypeDefinitionNode,
    ScalarTypeDefinitionNode,
    UnionTypeDefinitionNode,
)

from theauditor.utils.logging import logger

from ..fidelity_utils import FidelityToken
from . import BaseExtractor


class GraphQLExtractor(BaseExtractor):
    """Extractor for GraphQL SDL (.graphql/.gql/.graphqls) files."""

    def supported_extensions(self) -> list[str]:
        """Return supported GraphQL file extensions."""
        return [".graphql", ".gql", ".graphqls"]

    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract GraphQL schema metadata from SDL file."""
        file_path = file_info["path"]

        try:
            document = parse(content)
        except Exception as e:
            logger.info(f"GraphQL parse error in {file_path}: {e}")
            raise

        schema_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        graphql_schemas = []
        graphql_types = []
        graphql_fields = []
        graphql_field_args = []

        graphql_schemas.append(
            {
                "file_path": file_path,
                "schema_hash": schema_hash,
                "language": "graphql",
                "last_modified": file_info.get("mtime"),
            }
        )

        type_id_map = {}
        next_type_id = 1
        next_field_id = 1

        for definition in document.definitions:
            if self._is_type_definition(definition):
                type_data = self._extract_type(definition, file_path)
                if type_data:
                    temp_type_id = next_type_id
                    type_id_map[type_data["type_name"]] = temp_type_id
                    next_type_id += 1

                    graphql_types.append(type_data)

                    if hasattr(definition, "fields") and definition.fields:
                        for field_node in definition.fields:
                            field_data = self._extract_field(
                                field_node, temp_type_id, next_field_id, type_data["type_name"]
                            )
                            if field_data:
                                graphql_fields.append(field_data)

                                if hasattr(field_node, "arguments") and field_node.arguments:
                                    for arg_node in field_node.arguments:
                                        arg_data = self._extract_field_arg(
                                            arg_node, next_field_id, field_data["field_name"]
                                        )
                                        if arg_data:
                                            graphql_field_args.append(arg_data)

                                next_field_id += 1

        result = {
            "graphql_schemas": graphql_schemas,
            "graphql_types": graphql_types,
            "graphql_fields": graphql_fields,
            "graphql_field_args": graphql_field_args,
        }

        logger.debug(
            f"GraphQL extraction: {file_path} - "
            f"{len(graphql_types)} types, {len(graphql_fields)} fields, {len(graphql_field_args)} args"
        )

        return FidelityToken.attach_manifest(result)

    def _is_type_definition(self, node: DefinitionNode) -> bool:
        """Check if node is a type definition."""
        return isinstance(
            node,
            ObjectTypeDefinitionNode
            | InterfaceTypeDefinitionNode
            | InputObjectTypeDefinitionNode
            | EnumTypeDefinitionNode
            | UnionTypeDefinitionNode
            | ScalarTypeDefinitionNode,
        )

    def _extract_type(self, node: DefinitionNode, schema_path: str) -> dict[str, Any] | None:
        """Extract type metadata from AST node."""
        if not hasattr(node, "name") or not node.name:
            return None

        type_name = node.name.value

        if isinstance(node, ObjectTypeDefinitionNode):
            kind = "object"
        elif isinstance(node, InterfaceTypeDefinitionNode):
            kind = "interface"
        elif isinstance(node, InputObjectTypeDefinitionNode):
            kind = "input"
        elif isinstance(node, EnumTypeDefinitionNode):
            kind = "enum"
        elif isinstance(node, UnionTypeDefinitionNode):
            kind = "union"
        elif isinstance(node, ScalarTypeDefinitionNode):
            kind = "scalar"
        else:
            return None

        implements = None
        if hasattr(node, "interfaces") and node.interfaces:
            interface_names = [
                iface.name.value for iface in node.interfaces if hasattr(iface, "name")
            ]
            if interface_names:
                implements = json.dumps(interface_names)

        description = None
        if hasattr(node, "description") and node.description:
            description = node.description.value

        line = 0
        if hasattr(node, "loc") and node.loc and hasattr(node.loc, "start_token"):
            line = node.loc.start_token.line

        return {
            "schema_path": schema_path,
            "type_name": type_name,
            "kind": kind,
            "implements": implements,
            "description": description,
            "line": line,
        }

    def _extract_field(
        self, node: FieldDefinitionNode, type_id: int, field_id: int, type_name: str = None
    ) -> dict[str, Any] | None:
        """Extract field metadata from AST node."""
        if not hasattr(node, "name") or not node.name:
            return None

        field_name = node.name.value

        if not hasattr(node, "type") or not node.type:
            return None

        return_type, is_list, is_nullable = self._parse_type(node.type)

        directives_json = None
        if hasattr(node, "directives") and node.directives:
            directives = self._extract_directives(node.directives)
            if directives:
                directives_json = json.dumps(directives)

        line = node.loc.start_token.line if hasattr(node, "loc") and node.loc else None
        column = node.loc.start_token.column if hasattr(node, "loc") and node.loc else None

        result = {
            "type_id": type_id,
            "field_name": field_name,
            "return_type": return_type,
            "is_list": is_list,
            "is_nullable": is_nullable,
            "directives_json": directives_json,
            "line": line,
            "column": column,
        }

        if type_name:
            result["type_name"] = type_name

        return result

    def _extract_field_arg(
        self, node: InputValueDefinitionNode, field_id: int, field_name: str = None
    ) -> dict[str, Any] | None:
        """Extract field argument metadata from AST node."""
        if not hasattr(node, "name") or not node.name:
            return None

        arg_name = node.name.value

        if not hasattr(node, "type") or not node.type:
            return None

        arg_type, _, is_nullable = self._parse_type(node.type)

        has_default = hasattr(node, "default_value") and node.default_value is not None
        default_value = None
        if has_default:
            default_value = str(node.default_value)

        directives_json = None
        if hasattr(node, "directives") and node.directives:
            directives = self._extract_directives(node.directives)
            if directives:
                directives_json = json.dumps(directives)

        result = {
            "field_id": field_id,
            "arg_name": arg_name,
            "arg_type": arg_type,
            "has_default": has_default,
            "default_value": default_value,
            "is_nullable": is_nullable,
            "directives_json": directives_json,
        }

        if field_name:
            result["field_name"] = field_name

        return result

    def _parse_type(self, type_node) -> tuple:
        """Parse GraphQL type node into (type_string, is_list, is_nullable)."""
        is_nullable = True
        is_list = False
        type_string = ""

        if isinstance(type_node, NonNullTypeNode):
            is_nullable = False
            type_node = type_node.type

        if isinstance(type_node, ListTypeNode):
            is_list = True
            inner_type = type_node.type

            if isinstance(inner_type, NonNullTypeNode):
                type_string = f"[{inner_type.type.name.value}!]"
            else:
                type_string = f"[{inner_type.name.value}]"

            if not is_nullable:
                type_string += "!"
        elif isinstance(type_node, NamedTypeNode):
            type_string = type_node.name.value
            if not is_nullable:
                type_string += "!"
        else:
            type_string = "Unknown"

        return (type_string, is_list, is_nullable)

    def _extract_directives(self, directives: list[DirectiveNode]) -> list[dict[str, Any]]:
        """Extract directive metadata from AST nodes."""
        result = []
        for directive in directives:
            if not hasattr(directive, "name") or not directive.name:
                continue

            directive_data = {"name": f"@{directive.name.value}"}

            if hasattr(directive, "arguments") and directive.arguments:
                args = {}
                for arg in directive.arguments:
                    if hasattr(arg, "name") and hasattr(arg, "value"):
                        args[arg.name.value] = str(arg.value)
                if args:
                    directive_data["arguments"] = args

            result.append(directive_data)

        return result
