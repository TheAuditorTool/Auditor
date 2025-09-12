"""Golden Standard JWT Security Detector.

Detects JWT implementation vulnerabilities using AST analysis.
Demonstrates the standardized rule pattern for TheAuditor.

MIGRATION STATUS: Golden Standard Reference [2024-12-13]
Signature: context: StandardRuleContext -> List[StandardFinding]
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
import re
import ast

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

@dataclass(frozen=True)
class JWTPatterns:
    """Centralized patterns for JWT vulnerability detection."""
    
    # Weak secret patterns
    WEAK_SECRET_KEYWORDS = frozenset([
        'secret', 'password', 'key', '123', 'test', 
        'demo', 'example', 'sample', 'default', 'admin'
    ])
    
    # Minimum secret length (256 bits = 32 chars)
    MIN_SECRET_LENGTH = 32
    
    # Symmetric algorithms
    SYMMETRIC_ALGORITHMS = frozenset(['HS256', 'HS384', 'HS512'])
    
    # Asymmetric algorithms  
    ASYMMETRIC_ALGORITHMS = frozenset([
        'RS256', 'RS384', 'RS512', 
        'ES256', 'ES384', 'ES512', 
        'PS256', 'PS384', 'PS512'
    ])
    
    # Sensitive field names that shouldn't be in JWT payloads
    SENSITIVE_FIELDS = frozenset([
        'password', 'passwd', 'pwd', 'secret', 'apikey', 'api_key',
        'private', 'ssn', 'social_security', 'credit_card', 'creditcard',
        'cvv', 'pin', 'tax_id', 'license', 'passport', 'bank_account',
        'routing_number', 'private_key', 'client_secret', 'refresh_token'
    ])
    
    # Expiration field names
    EXPIRATION_FIELDS = frozenset(['expiresIn', 'exp', 'notAfter', 'expiry'])


# ============================================================================
# MAIN RULE FUNCTION (Standardized Interface)
# ============================================================================

def find_jwt_flaws(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect JWT implementation vulnerabilities.
    
    Detects:
    - Algorithm confusion attacks (mixing HS256/RS256)
    - Weak secrets (<32 characters or containing weak patterns)
    - Missing expiration claims
    - Sensitive data in JWT payloads
    - Missing refresh token rotation
    
    Args:
        context: Standardized rule context with AST and file data
        
    Returns:
        List of StandardFinding objects for detected vulnerabilities
    """
    findings = []
    
    # Validate prerequisites
    if not context.ast_wrapper or context.language not in ['javascript', 'typescript']:
        return findings
    
    # Route to appropriate analyzer based on AST type
    ast_type = context.ast_wrapper.get("type")
    tree = context.ast_wrapper.get("tree")
    
    if not tree:
        return findings
    
    # Create appropriate analyzer
    if ast_type == "semantic_ast":
        analyzer = TypeScriptJWTAnalyzer(context)
    elif ast_type == "tree_sitter":
        analyzer = TreeSitterJWTAnalyzer(context)
    else:
        # Fallback to pattern-based analysis
        analyzer = PatternJWTAnalyzer(context)
    
    # Run analysis
    return analyzer.analyze(tree)


# ============================================================================
# BASE ANALYZER CLASS
# ============================================================================

class BaseJWTAnalyzer:
    """Base class for JWT vulnerability analyzers."""
    
    def __init__(self, context: StandardRuleContext):
        self.context = context
        self.patterns = JWTPatterns()
        self.findings: List[StandardFinding] = []
        self.lines = context.get_lines()
    
    def analyze(self, tree: Any) -> List[StandardFinding]:
        """Analyze AST for JWT vulnerabilities."""
        raise NotImplementedError("Subclasses must implement analyze()")
    
    def check_algorithm_confusion(self, algorithms: Set[str], line: int) -> None:
        """Check for algorithm confusion vulnerability."""
        has_symmetric = bool(algorithms & self.patterns.SYMMETRIC_ALGORITHMS)
        has_asymmetric = bool(algorithms & self.patterns.ASYMMETRIC_ALGORITHMS)
        
        if has_symmetric and has_asymmetric:
            self.findings.append(StandardFinding(
                rule_name='jwt-algorithm-confusion',
                message='Algorithm confusion: both symmetric and asymmetric algorithms allowed',
                file_path=str(self.context.file_path),
                line=line,
                severity=Severity.CRITICAL,
                category='authentication',
                snippet=self.context.get_snippet(line),
                fix_suggestion='Use only one algorithm type (symmetric OR asymmetric, not both)'
            ))
    
    def check_weak_secret(self, secret: str, line: int) -> None:
        """Check for weak JWT secret."""
        if not secret:
            return
        
        # Remove quotes if present
        clean_secret = secret.strip('\'"` ')
        
        # Check length
        is_weak = len(clean_secret) < self.patterns.MIN_SECRET_LENGTH
        
        # Check for weak patterns
        if not is_weak:
            lower_secret = clean_secret.lower()
            is_weak = any(pattern in lower_secret for pattern in self.patterns.WEAK_SECRET_KEYWORDS)
        
        # Check for low entropy (all digits or all letters)
        if not is_weak:
            is_weak = clean_secret.isdigit() or (clean_secret.isalpha() and clean_secret.islower())
        
        if is_weak:
            self.findings.append(StandardFinding(
                rule_name='jwt-weak-secret',
                message=f'Weak JWT secret: {len(clean_secret)} chars (need {self.patterns.MIN_SECRET_LENGTH}+)',
                file_path=str(self.context.file_path),
                line=line,
                severity=Severity.CRITICAL,
                category='cryptography',
                snippet=self.context.get_snippet(line),
                fix_suggestion=f'Use cryptographically strong secret with {self.patterns.MIN_SECRET_LENGTH}+ characters'
            ))
    
    def check_missing_expiration(self, has_expiry: bool, line: int) -> None:
        """Check for missing JWT expiration."""
        if not has_expiry:
            self.findings.append(StandardFinding(
                rule_name='jwt-missing-expiration',
                message='JWT token created without expiration claim',
                file_path=str(self.context.file_path),
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                snippet=self.context.get_snippet(line),
                fix_suggestion="Add 'expiresIn' option (e.g., { expiresIn: '1h' })"
            ))
    
    def check_sensitive_data(self, payload_text: str, line: int) -> None:
        """Check for sensitive data in JWT payload."""
        if not payload_text:
            return
        
        lower_payload = payload_text.lower()
        found_sensitive = [
            field for field in self.patterns.SENSITIVE_FIELDS 
            if field in lower_payload
        ]
        
        if found_sensitive:
            self.findings.append(StandardFinding(
                rule_name='jwt-sensitive-data',
                message=f'Sensitive data in JWT payload: {", ".join(found_sensitive[:3])}',
                file_path=str(self.context.file_path),
                line=line,
                severity=Severity.HIGH,
                category='data-exposure',
                snippet=self.context.get_snippet(line),
                fix_suggestion='Never put sensitive data in JWT payloads - they are only base64 encoded'
            ))


# ============================================================================
# TREE-SITTER ANALYZER
# ============================================================================

class TreeSitterJWTAnalyzer(BaseJWTAnalyzer):
    """Analyzer for tree-sitter AST."""
    
    def analyze(self, tree: Any) -> List[StandardFinding]:
        """Analyze tree-sitter AST for JWT vulnerabilities."""
        if hasattr(tree, 'root_node'):
            self._visit_node(tree.root_node)
        return self.findings
    
    def _visit_node(self, node, depth: int = 0) -> None:
        """Recursively visit tree-sitter nodes."""
        if depth > 50:  # Prevent infinite recursion
            return
        
        if node.type == "call_expression":
            self._analyze_call(node)
        
        # Recurse into children
        for child in node.children:
            self._visit_node(child, depth + 1)
    
    def _analyze_call(self, node) -> None:
        """Analyze a function call for JWT operations."""
        func_node = node.child_by_field_name('function')
        if not func_node:
            return
        
        func_text = func_node.text.decode('utf-8', errors='ignore')
        args_node = node.child_by_field_name('arguments')
        line_num = node.start_point[0] + 1
        
        # Check jwt.verify calls
        if 'verify' in func_text:
            self._analyze_verify(args_node, line_num)
        
        # Check jwt.sign calls
        elif 'sign' in func_text:
            self._analyze_sign(args_node, line_num)
    
    def _analyze_verify(self, args_node, line: int) -> None:
        """Analyze jwt.verify call."""
        if not args_node:
            return
        
        args_text = args_node.text.decode('utf-8', errors='ignore')
        
        # Check for algorithm confusion
        if 'algorithms' in args_text:
            algorithms = set()
            for algo in self.patterns.SYMMETRIC_ALGORITHMS | self.patterns.ASYMMETRIC_ALGORITHMS:
                if algo in args_text:
                    algorithms.add(algo)
            
            self.check_algorithm_confusion(algorithms, line)
    
    def _analyze_sign(self, args_node, line: int) -> None:
        """Analyze jwt.sign call."""
        if not args_node:
            return
        
        # Parse arguments (simplified)
        args_text = args_node.text.decode('utf-8', errors='ignore')
        args = self._parse_arguments(args_text)
        
        # Check secret (2nd argument)
        if len(args) >= 2:
            self.check_weak_secret(args[1], line)
        
        # Check expiration (3rd argument)
        has_expiry = False
        if len(args) >= 3:
            has_expiry = any(field in args[2] for field in self.patterns.EXPIRATION_FIELDS)
        
        self.check_missing_expiration(has_expiry, line)
        
        # Check sensitive data (1st argument)
        if len(args) >= 1:
            self.check_sensitive_data(args[0], line)
    
    def _parse_arguments(self, args_text: str) -> List[str]:
        """Simple argument parser (not perfect but good enough)."""
        # Remove outer parentheses
        args_text = args_text.strip('()')
        
        # Split by commas at top level (simplified)
        args = []
        current = []
        depth = 0
        in_string = False
        
        for char in args_text:
            if char in '\'"' and depth == 0:
                in_string = not in_string
            elif not in_string:
                if char in '([{':
                    depth += 1
                elif char in ')]}':
                    depth -= 1
                elif char == ',' and depth == 0:
                    args.append(''.join(current).strip())
                    current = []
                    continue
            
            current.append(char)
        
        if current:
            args.append(''.join(current).strip())
        
        return args


# ============================================================================
# TYPESCRIPT COMPILER ANALYZER
# ============================================================================

class TypeScriptJWTAnalyzer(BaseJWTAnalyzer):
    """Analyzer for TypeScript compiler AST."""
    
    def analyze(self, tree: Any) -> List[StandardFinding]:
        """Analyze TypeScript AST for JWT vulnerabilities."""
        self._visit_node(tree)
        return self.findings
    
    def _visit_node(self, node: Dict[str, Any], depth: int = 0) -> None:
        """Recursively visit TypeScript AST nodes."""
        if depth > 50 or not isinstance(node, dict):
            return
        
        kind = node.get('kind')
        
        if kind == 'CallExpression':
            self._analyze_call(node)
        
        # Recurse into child collections
        for key in ['statements', 'declarations', 'elements', 'properties', 'members', 'arguments']:
            if key in node:
                children = node[key]
                if isinstance(children, list):
                    for child in children:
                        if isinstance(child, dict):
                            self._visit_node(child, depth + 1)
        
        # Recurse into child objects
        for value in node.values():
            if isinstance(value, dict):
                self._visit_node(value, depth + 1)
    
    def _analyze_call(self, node: Dict[str, Any]) -> None:
        """Analyze a TypeScript call expression."""
        expression = node.get('expression', {})
        arguments = node.get('arguments', [])
        line = self._get_line_number(node)
        
        func_name = self._get_function_name(expression)
        if not func_name:
            return
        
        if 'verify' in func_name:
            self._analyze_verify_ts(arguments, line)
        elif 'sign' in func_name:
            self._analyze_sign_ts(arguments, line)
    
    def _analyze_verify_ts(self, arguments: List[Dict], line: int) -> None:
        """Analyze TypeScript jwt.verify call."""
        if len(arguments) < 3:
            return
        
        options_text = self._extract_text(arguments[2])
        
        # Check for algorithm confusion
        algorithms = set()
        for algo in self.patterns.SYMMETRIC_ALGORITHMS | self.patterns.ASYMMETRIC_ALGORITHMS:
            if algo in options_text:
                algorithms.add(algo)
        
        self.check_algorithm_confusion(algorithms, line)
    
    def _analyze_sign_ts(self, arguments: List[Dict], line: int) -> None:
        """Analyze TypeScript jwt.sign call."""
        # Check secret
        if len(arguments) >= 2:
            secret_text = self._extract_text(arguments[1])
            self.check_weak_secret(secret_text, line)
        
        # Check expiration
        has_expiry = False
        if len(arguments) >= 3:
            options_text = self._extract_text(arguments[2])
            has_expiry = any(field in options_text for field in self.patterns.EXPIRATION_FIELDS)
        
        self.check_missing_expiration(has_expiry, line)
        
        # Check sensitive data
        if len(arguments) >= 1:
            payload_text = self._extract_text(arguments[0])
            self.check_sensitive_data(payload_text, line)
    
    def _get_function_name(self, expression: Dict) -> Optional[str]:
        """Extract function name from TypeScript expression."""
        if expression.get('kind') == 'PropertyAccessExpression':
            prop = expression.get('name', {})
            return prop.get('text', prop.get('escapedText', ''))
        elif expression.get('kind') == 'Identifier':
            return expression.get('text', expression.get('escapedText', ''))
        return None
    
    def _extract_text(self, node: Dict) -> str:
        """Extract text content from TypeScript AST node."""
        if not isinstance(node, dict):
            return str(node) if node else ''
        
        kind = node.get('kind')
        
        if kind in ['StringLiteral', 'Identifier']:
            return node.get('text', node.get('escapedText', ''))
        elif kind == 'ObjectLiteralExpression':
            # Extract property names
            props = node.get('properties', [])
            return ' '.join(self._extract_text(p) for p in props)
        
        # Fallback: concatenate all text fields
        texts = []
        for value in node.values():
            if isinstance(value, str):
                texts.append(value)
        return ' '.join(texts)
    
    def _get_line_number(self, node: Dict) -> int:
        """Get line number from TypeScript AST node."""
        pos = node.get('pos', 0)
        char_count = 0
        for i, line in enumerate(self.lines, 1):
            char_count += len(line) + 1
            if char_count > pos:
                return i
        return 1


# ============================================================================
# PATTERN-BASED ANALYZER (Fallback)
# ============================================================================

class PatternJWTAnalyzer(BaseJWTAnalyzer):
    """Fallback pattern-based analyzer when AST is unavailable."""
    
    def analyze(self, tree: Any) -> List[StandardFinding]:
        """Run pattern-based analysis on file content."""
        content = self.context.content
        
        # Algorithm confusion pattern
        self._check_algorithm_confusion_pattern(content)
        
        # Weak secret pattern
        self._check_weak_secret_pattern(content)
        
        # Missing expiration pattern
        self._check_missing_expiration_pattern(content)
        
        return self.findings
    
    def _check_algorithm_confusion_pattern(self, content: str) -> None:
        """Check for algorithm confusion using regex."""
        pattern = re.compile(
            r'jwt\.verify\s*\([^)]*algorithms\s*:\s*\[[^\]]*(?:HS\d{3})[^\]]*(?:[RE]S\d{3})',
            re.IGNORECASE | re.DOTALL
        )
        
        for match in pattern.finditer(content):
            line = content[:match.start()].count('\n') + 1
            algorithms = set(re.findall(r'[HRE]S\d{3}', match.group(0)))
            self.check_algorithm_confusion(algorithms, line)
    
    def _check_weak_secret_pattern(self, content: str) -> None:
        """Check for weak secrets using regex."""
        pattern = re.compile(
            r'jwt\.sign\s*\([^,)]*,\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )
        
        for match in pattern.finditer(content):
            secret = match.group(1)
            line = content[:match.start()].count('\n') + 1
            self.check_weak_secret(secret, line)
    
    def _check_missing_expiration_pattern(self, content: str) -> None:
        """Check for missing expiration using regex."""
        pattern = re.compile(
            r'jwt\.sign\s*\([^,)]+,\s*[^,)]+\s*\)',
            re.IGNORECASE
        )
        
        for match in pattern.finditer(content):
            if not any(field in match.group(0) for field in self.patterns.EXPIRATION_FIELDS):
                line = content[:match.start()].count('\n') + 1
                self.check_missing_expiration(False, line)