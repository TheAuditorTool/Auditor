"""AWS CDK (Cloud Development Kit) Infrastructure-as-Code extractor.

This module extracts AWS CDK construct instantiations from Python code for
infrastructure security analysis. Supports CDK v2 only.

Extracts:
- CDK construct calls (s3.Bucket, rds.DatabaseInstance, ec2.SecurityGroup, etc.)
- Construct properties (public_read_access, storage_encrypted, etc.)
- Property values serialized via ast.unparse()

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'cdk_class', 'construct_name', 'properties'
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
"""


import ast
import logging
from typing import Any, Dict, List, Optional

from ..base import get_node_name
from .utils.context import FileContext

logger = logging.getLogger(__name__)


# ============================================================================
# CDK Construct Detection Patterns
# ============================================================================

# CDK v2 construct patterns (aws_cdk.aws_*)
CDK_V2_PATTERNS = {
    'aws_cdk.aws_s3',
    'aws_cdk.aws_rds',
    'aws_cdk.aws_ec2',
    'aws_cdk.aws_iam',
    'aws_cdk.aws_lambda',
    'aws_cdk.aws_dynamodb',
    'aws_cdk.aws_ecs',
    'aws_cdk.aws_eks',
    'aws_cdk.aws_kms',
    'aws_cdk.aws_secretsmanager',
    'aws_cdk.aws_apigateway',
    'aws_cdk.aws_cloudfront',
    'aws_cdk.aws_elasticloadbalancingv2',
}

# Common CDK module aliases (from imports)
CDK_ALIAS_PATTERNS = {
    's3',
    'rds',
    'ec2',
    'iam',
    'lambda_',  # Python keyword workaround
    'dynamodb',
    'ecs',
    'eks',
    'kms',
    'secretsmanager',
    'apigateway',
    'cloudfront',
    'elbv2',
}

# CDK construct base classes (for inheritance detection - Phase 2)
CDK_BASE_CLASSES = {
    'Construct',
    'Stack',
    'Stage',
}


# ============================================================================
# Helper Functions
# ============================================================================

def _is_cdk_construct_call(node: ast.Call) -> bool:
    """Check if an ast.Call node represents a CDK construct instantiation.

    Detects patterns like:
    - s3.Bucket(self, "MyBucket", ...)
    - ec2.SecurityGroup(self, "MySG", ...)
    - aws_cdk.aws_s3.Bucket(self, "MyBucket", ...)
    - rds.DatabaseInstance(self, "MyDB", ...)

    CDK constructs MUST have:
    1. At least 2 positional arguments (scope, id, ...)
    2. Second argument must be a string literal (construct ID)

    This excludes factory methods like:
    - ec2.InstanceType.of(...) - No string ID argument
    - s3.BucketEncryption.S3_MANAGED - Property access, not a constructor

    Args:
        node: AST Call node to check

    Returns:
        True if this appears to be a CDK construct call
    """
    func_name = get_node_name(node.func)
    if not func_name:
        return False

    # Check for CDK v2 patterns (aws_cdk.aws_*)
    matches_pattern = False
    if any(pattern in func_name for pattern in CDK_V2_PATTERNS):
        matches_pattern = True
    elif '.' in func_name:
        # Check for common aliases (s3., rds., ec2., etc.)
        # Must start with alias and contain a dot (module.Class pattern)
        module_part = func_name.split('.')[0]
        if module_part in CDK_ALIAS_PATTERNS:
            matches_pattern = True

    if not matches_pattern:
        return False

    # CRITICAL: Validate CDK constructor signature
    # CDK constructs MUST have: (scope, id, props)
    # where id (2nd arg) is a string literal
    if len(node.args) < 2:
        return False

    # Check if second argument is a string literal (construct ID)
    second_arg = node.args[1]
    if isinstance(second_arg, ast.Constant) and isinstance(second_arg.value, str):
        return True
    elif (isinstance(second_arg, ast.Constant) and isinstance(second_arg.value, str)):  # Python <3.8 compatibility
        return True

    # Not a valid CDK construct call (e.g., factory method like ec2.InstanceType.of)
    return False


def _extract_construct_name(call_node: ast.Call) -> str | None:
    """Extract CDK logical ID (construct name) from call arguments.

    CDK constructs use pattern: Construct(self, "LogicalID", ...)
    The 2nd positional argument is the logical ID string.

    Args:
        call_node: AST Call node

    Returns:
        Construct name string or None if not found/not a string
    """
    # Check for 2nd positional argument (index 1)
    if len(call_node.args) >= 2:
        name_arg = call_node.args[1]

        # Handle string constants
        if isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str):
            return name_arg.value
        elif (isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str)):  # Python <3.8 compatibility
            return name_arg.s

    return None


def _serialize_property_value(value_node: ast.AST) -> str:
    """Serialize property value AST node to string.

    Uses ast.unparse() to convert expression to source code string.
    This preserves the original expression without evaluation.

    Args:
        value_node: AST node representing property value

    Returns:
        String representation of the value expression
    """
    try:
        # ast.unparse() requires Python 3.9+
        if hasattr(ast, 'unparse'):
            return ast.unparse(value_node)
        else:
            # Fallback for Python <3.9 (limited support)
            if isinstance(value_node, ast.Constant):
                return repr(value_node.value)
            elif isinstance(value_node, ast.Name):
                return value_node.id
            elif isinstance(value_node, ast.Attribute):
                # Handle simple attributes like s3.BucketEncryption.UNENCRYPTED
                parts = []
                node = value_node
                while isinstance(node, ast.Attribute):
                    parts.insert(0, node.attr)
                    node = node.value
                if isinstance(node, ast.Name):
                    parts.insert(0, node.id)
                return '.'.join(parts)
            else:
                return '<complex_expression>'
    except Exception as e:
        logger.warning(f"Failed to serialize property value: {e}")
        return '<unparseable>'


# ============================================================================
# Main Extraction Function
# ============================================================================

def extract_python_cdk_constructs(context: FileContext) -> list[dict]:
    """Extract AWS CDK construct instantiations from Python AST.

    Walks the AST to find CDK construct calls and extracts:
    - Construct class name (e.g., 's3.Bucket', 'aws_cdk.aws_s3.Bucket')
    - Construct logical ID (2nd positional arg)
    - Line number of instantiation
    - Properties (keyword arguments) with serialized values

    Args:
        context: FileContext containing AST tree and node index

    Returns:
        List of construct dictionaries, each containing:
        {
            'line': int,
            'cdk_class': str,
            'construct_name': Optional[str],
            'properties': [
                {'name': str, 'value_expr': str, 'line': int},
                ...
            ]
        }

    Example return:
        [
            {
                'line': 42,
                'cdk_class': 's3.Bucket',
                'construct_name': 'MyBucket',
                'properties': [
                    {'name': 'public_read_access', 'value_expr': 'True', 'line': 43},
                    {'name': 'encryption', 'value_expr': 's3.BucketEncryption.UNENCRYPTED', 'line': 44}
                ]
            }
        ]
    """
    constructs = []

    # Check if we have a valid tree
    if not context.tree:
        return constructs

    # Walk AST to find all Call nodes
    for node in context.walk_tree():
        if not isinstance(node, ast.Call):
            continue

        # Check if this is a CDK construct call
        if not _is_cdk_construct_call(node):
            continue

        # Extract construct metadata
        cdk_class = get_node_name(node.func)
        if not cdk_class:
            continue

        construct_name = _extract_construct_name(node)
        line = getattr(node, 'lineno', 0)

        # Extract properties from keyword arguments
        properties = []
        for keyword in node.keywords:
            if keyword.arg is None:
                # Skip **kwargs
                continue

            prop_name = keyword.arg
            prop_value_expr = _serialize_property_value(keyword.value)
            prop_line = getattr(keyword, 'lineno', line)

            properties.append({
                'name': prop_name,
                'value_expr': prop_value_expr,
                'line': prop_line
            })

        # Build construct record
        construct_record = {
            'line': line,
            'cdk_class': cdk_class,
            'construct_name': construct_name,
            'properties': properties
        }

        constructs.append(construct_record)

        logger.debug(
            f"Extracted CDK construct: {cdk_class} at line {line} "
            f"with {len(properties)} properties"
        )

    return constructs
