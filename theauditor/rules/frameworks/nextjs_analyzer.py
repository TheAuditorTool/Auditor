"""Next.js framework-specific security analyzer using AST."""

from typing import Any, Dict, List


def find_nextjs_issues(tree: Any, file_path: str = None, content: str = None, **kwargs) -> List[Dict[str, Any]]:
    """Find Next.js security issues using AST analysis.
    
    Args:
        tree: AST tree from parser
        file_path: Path to the file being analyzed
        content: File content
        **kwargs: Additional context
        
    Returns:
        List of security findings
    """
    findings = []
    
    if not tree or not content:
        return findings
    
    # Check if this is a Next.js file
    is_nextjs = (
        'next/' in content or
        'NextResponse' in content or
        'getServerSideProps' in content or
        'getStaticProps' in content or
        'getInitialProps' in content or
        'app/api/' in str(file_path) if file_path else False or
        'pages/api/' in str(file_path) if file_path else False
    )
    
    if not is_nextjs:
        return findings
    
    # Check for API route secret exposure
    if _has_api_route_secret_exposure(content):
        findings.append({
            "pattern_name": "nextjs-api-route-secret-exposure",
            "type": "NEXTJS_API_ROUTE_SECRET_EXPOSURE",
            "message": "Server-side environment variables exposed in API route response",
            "file": file_path,
            "line": 1,
            "severity": "critical",
            "category": "security"
        })
    
    # Check for open redirect
    if _has_open_redirect(content):
        findings.append({
            "pattern_name": "nextjs-open-redirect", 
            "type": "NEXTJS_OPEN_REDIRECT",
            "message": "Unvalidated user input in router.push/replace - open redirect vulnerability",
            "file": file_path,
            "line": 1,
            "severity": "medium",
            "category": "security"
        })
    
    # Check for SSR injection
    if _has_ssr_injection(content):
        findings.append({
            "pattern_name": "nextjs-ssr-injection",
            "type": "NEXTJS_SSR_INJECTION", 
            "message": "Server-side rendering with unvalidated user input",
            "file": file_path,
            "line": 1,
            "severity": "high",
            "category": "injection"
        })
    
    # Check for NEXT_PUBLIC sensitive data
    if _has_public_env_exposure(content):
        findings.append({
            "pattern_name": "nextjs-public-env-exposure",
            "type": "NEXTJS_PUBLIC_ENV_EXPOSURE",
            "message": "Sensitive data in NEXT_PUBLIC_ variables exposed to client",
            "file": file_path,
            "line": 1,
            "severity": "critical",
            "category": "security"
        })
    
    # Check for missing CSRF in API routes
    if _has_api_csrf_missing(content, file_path):
        findings.append({
            "pattern_name": "nextjs-api-csrf-missing",
            "type": "NEXTJS_API_CSRF_MISSING",
            "message": "API route handling POST/PUT/DELETE without CSRF protection",
            "file": file_path,
            "line": 1,
            "severity": "high",
            "category": "csrf"
        })
    
    # Check for Server Actions without validation
    if _has_server_actions_validation_missing(content):
        findings.append({
            "pattern_name": "nextjs-server-actions-validation",
            "type": "NEXTJS_SERVER_ACTIONS_VALIDATION",
            "message": "Server Actions without input validation - injection risk",
            "file": file_path,
            "line": 1,
            "severity": "high",
            "category": "validation"
        })
    
    return findings


def register_taint_patterns(taint_registry):
    """Register Next.js-specific taint patterns."""
    
    # Next.js response sinks
    NEXTJS_SINKS = [
        "NextResponse.json",
        "NextResponse.redirect", 
        "res.json",
        "res.send",
        "router.push",
        "router.replace",
        "redirect",
        "revalidatePath",
        "revalidateTag"
    ]
    
    for pattern in NEXTJS_SINKS:
        taint_registry.register_sink(pattern, "nextjs", "javascript")
    
    # Next.js input sources
    NEXTJS_SOURCES = [
        "req.query",
        "req.body",
        "searchParams",
        "params",
        "cookies",
        "headers",
        "formData"
    ]
    
    for pattern in NEXTJS_SOURCES:
        taint_registry.register_source(pattern, "user_input", "javascript")


# Helper functions
def _has_api_route_secret_exposure(content: str) -> bool:
    """Check for environment variable exposure in API routes."""
    import re
    return bool(re.search(r'(?:res\.(?:json|send)|NextResponse\.json)\s*\([^)]*process\.env', content))

def _has_open_redirect(content: str) -> bool:
    """Check for open redirect vulnerability."""
    import re
    return bool(re.search(r'router\.(?:push|replace)\s*\([^)]*(?:query|params|searchParams)\.', content))

def _has_ssr_injection(content: str) -> bool:
    """Check for SSR injection."""
    import re
    pattern = r'getServerSideProps[^}]*(?:req\.query|req\.body|params)'
    if re.search(pattern, content):
        return 'sanitize' not in content and 'escape' not in content and 'validate' not in content
    return False

def _has_public_env_exposure(content: str) -> bool:
    """Check for sensitive data in NEXT_PUBLIC variables."""
    import re
    return bool(re.search(r'NEXT_PUBLIC_[A-Z_]*(?:SECRET|PRIVATE|KEY|TOKEN|PASSWORD)', content))

def _has_api_csrf_missing(content: str, file_path: str) -> bool:
    """Check for missing CSRF in API routes."""
    if file_path and ('pages/api/' in str(file_path) or 'app/api/' in str(file_path)):
        if any(method in content for method in ['POST', 'PUT', 'DELETE']):
            return 'csrf' not in content.lower()
    return False

def _has_server_actions_validation_missing(content: str) -> bool:
    """Check for Server Actions without validation."""
    if '"use server"' in content or "'use server'" in content:
        if 'formData.get' in content or 'searchParams.get' in content:
            return not any(validator in content for validator in ['zod', 'yup', 'joi', 'validate'])
    return False