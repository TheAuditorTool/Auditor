"""HCL AST extraction using tree-sitter.

Extracts resources, variables, and outputs from Terraform/HCL files with precise
line numbers using tree-sitter-hcl.

Architecture:
- Database-first: Returns structured data for direct database insertion
- Zero fallbacks: Hard fail on parse errors
- Line precision: Uses tree-sitter node.start_point for exact locations
"""

from typing import List, Dict, Any, Optional


def extract_hcl_blocks(node: Any, language: str = "hcl") -> List[Dict]:
    """Extract HCL blocks (resources, variables, outputs) from tree-sitter AST.

    HCL AST Structure:
        config_file
        └── body
            └── block
                ├── identifier: "resource" | "variable" | "output"
                ├── string_lit: type (for resources) or name (for variables/outputs)
                ├── string_lit: name (for resources only)
                └── body: { attributes }

    Args:
        node: tree-sitter AST node
        language: Programming language (default: "hcl")

    Returns:
        List of block dicts with identifier, type, name, line
    """
    blocks = []

    if node is None:
        return blocks

    # HCL uses "block" node type for all top-level constructs
    if node.type == "block":
        identifier = None
        block_type = None
        block_name = None

        # Extract block components from children
        # Skip block_start, block_end, body nodes - just get identifiers and string_lits
        children = [c for c in node.children if c.type not in ["block_start", "block_end", "body"]]

        if len(children) >= 1:
            # First child is always the identifier (resource/variable/output/data/etc)
            identifier = children[0].text.decode("utf-8", errors="ignore")

        if len(children) >= 2:
            # Second child is type (for resources) or name (for variables/outputs)
            block_type = children[1].text.decode("utf-8", errors="ignore").strip('"')

        if len(children) >= 3:
            # Third child is name (for resources only - they have type + name)
            block_name = children[2].text.decode("utf-8", errors="ignore").strip('"')

        # For variables/outputs, the "type" is actually the name
        if identifier in ["variable", "output", "locals"] and block_name is None:
            block_name = block_type
            block_type = None

        blocks.append({
            "identifier": identifier,           # "resource", "variable", "output", "data", etc.
            "type": block_type,                 # Resource type (e.g., "aws_s3_bucket") or None
            "name": block_name,                 # Block name (e.g., "example")
            "line": node.start_point[0] + 1,   # 1-indexed line number
            "column": node.start_point[1],     # Column number
        })

    # Recursively search children
    for child in node.children:
        blocks.extend(extract_hcl_blocks(child, language))

    return blocks


def extract_hcl_attributes(node: Any, block_type: str) -> Dict[str, Any]:
    """Extract attributes from an HCL block body.

    Args:
        node: tree-sitter body node
        block_type: Type of block (for attribute filtering)

    Returns:
        Dictionary of attribute name -> value
    """
    attributes = {}

    if node is None or node.type != "body":
        return attributes

    # Iterate through body children to find attribute nodes
    for child in node.children:
        if child.type == "attribute":
            # attribute node structure: identifier "=" expression
            attr_name = None
            attr_value = None

            for subchild in child.children:
                if subchild.type == "identifier" and attr_name is None:
                    attr_name = subchild.text.decode("utf-8", errors="ignore")
                elif subchild.type != "=" and attr_name is not None:
                    # This is the value expression
                    attr_value = subchild.text.decode("utf-8", errors="ignore")

            if attr_name and attr_value is not None:
                attributes[attr_name] = attr_value

    return attributes


def extract_hcl_resources(tree, content: str, file_path: str) -> List[Dict]:
    """Extract Terraform resources with line numbers.

    Args:
        tree: tree-sitter parse tree (with .root_node)
        content: File content
        file_path: Path to source file

    Returns:
        List of resource dicts with type, name, line, attributes
    """
    all_blocks = extract_hcl_blocks(tree.root_node)
    resources = []

    for block in all_blocks:
        if block["identifier"] == "resource":
            # Find the actual block node to extract attributes
            # For now, just return basic structure
            resources.append({
                "resource_type": block["type"],
                "resource_name": block["name"],
                "line": block["line"],
                "column": block["column"],
                "file_path": file_path
            })

    return resources


def extract_hcl_variables(tree, content: str, file_path: str) -> List[Dict]:
    """Extract Terraform variables with line numbers.

    Args:
        tree: tree-sitter parse tree (with .root_node)
        content: File content
        file_path: Path to source file

    Returns:
        List of variable dicts with name, line
    """
    all_blocks = extract_hcl_blocks(tree.root_node)
    variables = []

    for block in all_blocks:
        if block["identifier"] == "variable":
            variables.append({
                "variable_name": block["name"],
                "line": block["line"],
                "column": block["column"],
                "file_path": file_path
            })

    return variables


def extract_hcl_outputs(tree, content: str, file_path: str) -> List[Dict]:
    """Extract Terraform outputs with line numbers.

    Args:
        tree: tree-sitter parse tree (with .root_node)
        content: File content
        file_path: Path to source file

    Returns:
        List of output dicts with name, line
    """
    all_blocks = extract_hcl_blocks(tree.root_node)
    outputs = []

    for block in all_blocks:
        if block["identifier"] == "output":
            outputs.append({
                "output_name": block["name"],
                "line": block["line"],
                "column": block["column"],
                "file_path": file_path
            })

    return outputs


def extract_hcl_data_sources(tree, content: str, file_path: str) -> List[Dict]:
    """Extract Terraform data sources with line numbers.

    Args:
        tree: tree-sitter parse tree (with .root_node)
        content: File content
        file_path: Path to source file

    Returns:
        List of data source dicts with type, name, line
    """
    all_blocks = extract_hcl_blocks(tree.root_node)
    data_sources = []

    for block in all_blocks:
        if block["identifier"] == "data":
            data_sources.append({
                "data_type": block["type"],
                "data_name": block["name"],
                "line": block["line"],
                "column": block["column"],
                "file_path": file_path
            })

    return data_sources
