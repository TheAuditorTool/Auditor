"""AWS CDK (Cloud Development Kit) Infrastructure-as-Code extractor."""

import ast

from theauditor.utils.logging import logger

from ..base import get_node_name
from .utils.context import FileContext

CDK_V2_PATTERNS = {
    "aws_cdk.aws_s3",
    "aws_cdk.aws_rds",
    "aws_cdk.aws_ec2",
    "aws_cdk.aws_iam",
    "aws_cdk.aws_lambda",
    "aws_cdk.aws_dynamodb",
    "aws_cdk.aws_ecs",
    "aws_cdk.aws_eks",
    "aws_cdk.aws_kms",
    "aws_cdk.aws_secretsmanager",
    "aws_cdk.aws_apigateway",
    "aws_cdk.aws_cloudfront",
    "aws_cdk.aws_elasticloadbalancingv2",
}


CDK_ALIAS_PATTERNS = {
    "s3",
    "rds",
    "ec2",
    "iam",
    "lambda_",
    "dynamodb",
    "ecs",
    "eks",
    "kms",
    "secretsmanager",
    "apigateway",
    "cloudfront",
    "elbv2",
}


CDK_BASE_CLASSES = {
    "Construct",
    "Stack",
    "Stage",
}


def _is_cdk_construct_call(node: ast.Call) -> bool:
    """Check if an ast.Call node represents a CDK construct instantiation."""
    func_name = get_node_name(node.func)
    if not func_name:
        return False

    matches_pattern = False
    if any(pattern in func_name for pattern in CDK_V2_PATTERNS):
        matches_pattern = True
    elif "." in func_name:
        module_part = func_name.split(".")[0]
        if module_part in CDK_ALIAS_PATTERNS:
            matches_pattern = True

    if not matches_pattern:
        return False

    if len(node.args) < 2:
        return False

    second_arg = node.args[1]
    return isinstance(second_arg, ast.Constant) and isinstance(second_arg.value, str)


def _extract_construct_name(call_node: ast.Call) -> str | None:
    """Extract CDK logical ID (construct name) from call arguments."""

    if len(call_node.args) >= 2:
        name_arg = call_node.args[1]

        if isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str):
            return name_arg.value
        elif isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str):
            return name_arg.s

    return None


def _serialize_property_value(value_node: ast.AST) -> str:
    """Serialize property value AST node to string."""
    try:
        if hasattr(ast, "unparse"):
            return ast.unparse(value_node)
        else:
            if isinstance(value_node, ast.Constant):
                return repr(value_node.value)
            elif isinstance(value_node, ast.Name):
                return value_node.id
            elif isinstance(value_node, ast.Attribute):
                parts = []
                node = value_node
                while isinstance(node, ast.Attribute):
                    parts.insert(0, node.attr)
                    node = node.value
                if isinstance(node, ast.Name):
                    parts.insert(0, node.id)
                return ".".join(parts)
            else:
                return "<complex_expression>"
    except Exception as e:
        logger.warning(f"Failed to serialize property value: {e}")
        return "<unparseable>"


def extract_python_cdk_constructs(context: FileContext) -> list[dict]:
    """Extract AWS CDK construct instantiations from Python AST."""
    constructs = []

    if not context.tree:
        return constructs

    for node in context.walk_tree():
        if not isinstance(node, ast.Call):
            continue

        if not _is_cdk_construct_call(node):
            continue

        cdk_class = get_node_name(node.func)
        if not cdk_class:
            continue

        construct_name = _extract_construct_name(node)
        line = getattr(node, "lineno", 0)

        properties = []
        for keyword in node.keywords:
            if keyword.arg is None:
                continue

            prop_name = keyword.arg
            prop_value_expr = _serialize_property_value(keyword.value)
            prop_line = getattr(keyword, "lineno", line)

            properties.append({"name": prop_name, "value_expr": prop_value_expr, "line": prop_line})

        construct_record = {
            "line": line,
            "cdk_class": cdk_class,
            "construct_name": construct_name,
            "properties": properties,
        }

        constructs.append(construct_record)

        logger.debug(
            f"Extracted CDK construct: {cdk_class} at line {line} with {len(properties)} properties"
        )

    return constructs
