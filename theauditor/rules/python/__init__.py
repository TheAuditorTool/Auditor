"""Python-specific security and concurrency rules.

This module contains rules for detecting Python-specific issues:
- Race conditions and concurrency problems
- Async/await issues
- Threading and multiprocessing problems
- Lock and synchronization issues
- Cryptography vulnerabilities
- Injection vulnerabilities (SQL, command, code, template, etc.)
- Deserialization vulnerabilities (pickle, YAML, marshal, etc.)
"""

from .async_concurrency_analyze import analyze as find_async_concurrency_issues
from .python_crypto_analyze import analyze as find_crypto_issues
from .python_injection_analyze import analyze as find_injection_issues
from .python_globals_analyze import analyze as find_global_state_issues
from .python_deserialization_analyze import analyze as find_deserialization_issues

__all__ = [
    'find_async_concurrency_issues',
    'find_crypto_issues',
    'find_injection_issues',
    'find_deserialization_issues',
    'find_global_state_issues'
]
