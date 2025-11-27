"""Terraform infrastructure analysis subsystem.

Provides Terraform parsing, provisioning graph construction, and security
analysis helpers. Security analysis now delegates to the standardized rule
implementation in theauditor.rules.terraform.terraform_analyze while
preserving backwards compatibility with aud terraform analyze.
"""

from .analyzer import TerraformAnalyzer, TerraformFinding
from .graph import TerraformGraphBuilder
from .parser import TerraformParser

__all__ = [
    "TerraformParser",
    "TerraformAnalyzer",
    "TerraformFinding",
    "TerraformGraphBuilder",
]
