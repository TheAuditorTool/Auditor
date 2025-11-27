"""AWS CDK Infrastructure-as-Code security analysis module.

This module provides security analysis capabilities for AWS CDK Python code,
detecting infrastructure misconfigurations before deployment.

Components:
- analyzer.py: AWSCdkAnalyzer class for running CDK security rules
"""

from .analyzer import AWSCdkAnalyzer

__all__ = ["AWSCdkAnalyzer"]
