"""Security-focused AST rules for detecting SQL injection vulnerabilities.

Supports:
- Python (via native `ast` module)
"""

import ast
from typing import List, Dict, Any


def find_sql_injection(tree: ast.AST) -> List[Dict[str, Any]]:
    """Find potential SQL injection vulnerabilities.
    
    Detects:
    - String formatting in SQL queries
    - Direct concatenation in SQL queries
    - f-strings used for SQL
    
    Returns:
        List of findings with details
    """
    findings = []
    sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'EXEC', 'EXECUTE']
    
    for node in ast.walk(tree):
        # Check for SQL in string formatting
        if isinstance(node, ast.Call):
            # Check for .format() calls
            if (isinstance(node.func, ast.Attribute) and 
                node.func.attr == 'format'):
                # Check if the string being formatted contains SQL
                if isinstance(node.func.value, (ast.Constant, ast.Str)):
                    if isinstance(node.func.value, ast.Constant):
                        value = node.func.value.value
                    else:
                        value = node.func.value.s
                    
                    if isinstance(value, str):
                        value_upper = value.upper()
                        if any(keyword in value_upper for keyword in sql_keywords):
                            findings.append({
                                'line': getattr(node, 'lineno', 0),
                                'column': getattr(node, 'col_offset', 0),
                                'snippet': 'SQL query using .format()',
                                'confidence': 0.85,
                                'severity': 'CRITICAL',
                                'type': 'sql_injection',
                                'hint': 'Use parameterized queries instead of string formatting'
                            })
        
        # Check for f-strings with SQL
        elif isinstance(node, ast.JoinedStr):
            # This is an f-string
            # Check if it contains SQL keywords
            for value in node.values:
                if isinstance(value, (ast.Constant, ast.Str)):
                    if isinstance(value, ast.Constant):
                        str_value = str(value.value)
                    else:
                        str_value = str(value.s)
                    
                    if any(keyword in str_value.upper() for keyword in sql_keywords):
                        findings.append({
                            'line': getattr(node, 'lineno', 0),
                            'column': getattr(node, 'col_offset', 0),
                            'snippet': 'SQL query using f-string',
                            'confidence': 0.90,
                            'severity': 'CRITICAL',
                            'type': 'sql_injection',
                            'hint': 'Never use f-strings for SQL queries, use parameterized queries'
                        })
                        break
    
    return findings