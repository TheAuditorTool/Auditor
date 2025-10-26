"""Terraform security rule package."""

from .terraform_analyze import find_terraform_issues

__all__ = [
    "find_terraform_issues",
]
