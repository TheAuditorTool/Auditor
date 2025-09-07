"""XSS vulnerability detection rules module."""

from .xssdetection import find_xss_vulnerabilities

__all__ = ['find_xss_vulnerabilities']