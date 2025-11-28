"""HCL AST extraction using tree-sitter."""

from typing import Any


def _get_body_node(block_node: Any) -> Any | None:
    """Return the body child node for a block if present."""
    for child in getattr(block_node, "children", []) or []:
        if child.type == "body":
            return child
    return None


def extract_hcl_blocks(node: Any, language: str = "hcl") -> list[dict]:
    """Extract HCL blocks (resources, variables, outputs) from tree-sitter AST."""
    blocks = []

    if node is None:
        return blocks

    if node.type == "block":
        identifier = None
        block_type = None
        block_name = None

        children = [
            c
            for c in node.children
            if c.type not in ["block_start", "block_end", "body", "comment"]
        ]

        if len(children) >= 1:
            identifier = children[0].text.decode("utf-8", errors="ignore")

        if len(children) >= 2:
            block_type = children[1].text.decode("utf-8", errors="ignore").strip('"')

        if len(children) >= 3:
            block_name = children[2].text.decode("utf-8", errors="ignore").strip('"')

        if identifier in ["variable", "output", "locals"] and block_name is None:
            block_name = block_type
            block_type = None

        body_node = _get_body_node(node)

        blocks.append(
            {
                "identifier": identifier,
                "type": block_type,
                "name": block_name,
                "line": node.start_point[0] + 1,
                "column": node.start_point[1],
                "node": node,
                "body": body_node,
            }
        )

    for child in node.children:
        blocks.extend(extract_hcl_blocks(child, language))

    return blocks


def extract_hcl_attributes(node: Any, block_type: str) -> dict[str, Any]:
    """Extract attributes from an HCL block body."""
    attributes = {}

    if node is None or node.type != "body":
        return attributes

    for child in node.children:
        if child.type == "attribute":
            attr_name = None
            attr_value = None

            for subchild in child.children:
                if subchild.type == "identifier" and attr_name is None:
                    attr_name = subchild.text.decode("utf-8", errors="ignore")
                elif subchild.type != "=" and attr_name is not None:
                    attr_value = subchild.text.decode("utf-8", errors="ignore")

            if attr_name and attr_value is not None:
                attributes[attr_name] = attr_value

    return attributes


def extract_hcl_resources(tree, content: str, file_path: str) -> list[dict]:
    """Extract Terraform resources with line numbers."""
    all_blocks = extract_hcl_blocks(tree.root_node)
    resources = []

    for block in all_blocks:
        if block["identifier"] == "resource":
            body_node = block.get("body")
            attributes = extract_hcl_attributes(body_node, block["type"]) if body_node else {}

            resources.append(
                {
                    "resource_type": block["type"],
                    "resource_name": block["name"],
                    "line": block["line"],
                    "column": block["column"],
                    "file_path": file_path,
                    "attributes": attributes,
                }
            )

    return resources


def extract_hcl_variables(tree, content: str, file_path: str) -> list[dict]:
    """Extract Terraform variables with line numbers and attributes."""
    all_blocks = extract_hcl_blocks(tree.root_node)
    variables = []

    for block in all_blocks:
        if block["identifier"] == "variable":
            body_node = block.get("body")
            attributes = extract_hcl_attributes(body_node, "variable") if body_node else {}

            variables.append(
                {
                    "variable_name": block["name"],
                    "line": block["line"],
                    "column": block["column"],
                    "file_path": file_path,
                    "attributes": attributes,
                }
            )

    return variables


def extract_hcl_outputs(tree, content: str, file_path: str) -> list[dict]:
    """Extract Terraform outputs with line numbers and attributes."""
    all_blocks = extract_hcl_blocks(tree.root_node)
    outputs = []

    for block in all_blocks:
        if block["identifier"] == "output":
            body_node = block.get("body")
            attributes = extract_hcl_attributes(body_node, "output") if body_node else {}

            outputs.append(
                {
                    "output_name": block["name"],
                    "line": block["line"],
                    "column": block["column"],
                    "file_path": file_path,
                    "attributes": attributes,
                }
            )

    return outputs


def extract_hcl_data_sources(tree, content: str, file_path: str) -> list[dict]:
    """Extract Terraform data sources with line numbers."""
    all_blocks = extract_hcl_blocks(tree.root_node)
    data_sources = []

    for block in all_blocks:
        if block["identifier"] == "data":
            data_sources.append(
                {
                    "data_type": block["type"],
                    "data_name": block["name"],
                    "line": block["line"],
                    "column": block["column"],
                    "file_path": file_path,
                }
            )

    return data_sources
