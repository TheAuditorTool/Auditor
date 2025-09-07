"""Database-aware API endpoint security analysis rule.

This module queries the repo_index.db to identify API endpoints that perform 
state-changing operations (POST, PUT, DELETE, PATCH) without proper authentication controls.
This is a high-fidelity rule that operates on the fully indexed database rather than 
individual files, making it part of the new generation of database-aware rules.
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any


def find_missing_api_authentication(db_path: str) -> List[Dict[str, Any]]:
    """
    Analyze API endpoints for missing authentication on state-changing operations.
    
    This is a high-fidelity rule that queries the repo_index.db to identify
    API endpoints that perform state-changing operations (POST, PUT, DELETE, PATCH)
    without proper authentication controls.
    
    Args:
        db_path: Path to repo_index.db
        
    Returns:
        List of security findings in normalized format compatible with Finding dataclass
    """
    findings = []
    
    # Connect to database
    if not Path(db_path).exists():
        return findings
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if api_endpoints table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='api_endpoints'"
    )
    if not cursor.fetchone():
        # Table doesn't exist, might be old schema or no API endpoints indexed
        conn.close()
        return findings
    
    # Query all API endpoints with their security controls
    cursor.execute(
        """
        SELECT file, method, pattern, controls, line
        FROM api_endpoints
        ORDER BY file, pattern
        """
    )
    endpoints = cursor.fetchall()
    
    # Define authentication control keywords (comprehensive list preserved from original)
    auth_keywords = [
        # Generic authentication
        'auth', 'authenticate', 'authenticated', 'authorization', 'authorize',
        'authorized', 'requireAuth', 'requiresAuth', 'isAuthenticated',
        'ensureAuthenticated', 'protect', 'protected', 'secure', 'secured',
        
        # JWT specific
        'jwt', 'verifyToken', 'validateToken', 'checkToken', 'jwtAuth',
        'verifyJWT', 'validateJWT', 'checkJWT', 'decodeToken', 'verifyJwt',
        
        # Session/Cookie
        'session', 'checkSession', 'validateSession', 'requireSession',
        'cookie', 'checkCookie', 'validateCookie', 'sessionAuth',
        
        # Framework specific
        'login_required',  # Flask-Login
        'permission_required',  # Flask permissions
        'requires_auth',  # Common pattern
        'passport',  # Passport.js
        'ensureLoggedIn',  # Connect-ensure-login
        'requireUser',  # Common pattern
        'currentUser',  # If checking current user
        '@auth',  # Decorator pattern
        '@authenticated',  # Decorator pattern
        
        # Role-based
        'role', 'checkRole', 'hasRole', 'requireRole',
        'permission', 'checkPermission', 'hasPermission',
        'admin', 'requireAdmin', 'isAdmin', 'checkAdmin',
        'rbac', 'acl', 'checkAcl', 'hasAccess',
        
        # API Key
        'apiKey', 'api_key', 'checkApiKey', 'validateApiKey',
        'requireApiKey', 'verifyApiKey', 'x-api-key',
        
        # OAuth
        'oauth', 'checkOAuth', 'validateOAuth', 'oauthAuth',
        
        # Other security middleware
        'guard', 'Guard', 'authGuard', 'AuthGuard',
        'middleware', 'authMiddleware', 'securityMiddleware'
    ]
    
    # Convert to lowercase for case-insensitive matching
    auth_keywords_lower = [k.lower() for k in auth_keywords]
    
    # Analyze each endpoint
    for file, method, pattern, controls_json, line in endpoints:
        # Parse controls
        try:
            controls = json.loads(controls_json) if controls_json else []
        except json.JSONDecodeError:
            controls = []
        
        # Convert controls to lowercase for matching
        controls_lower = [c.lower() for c in controls]
        
        # Check if this is a state-changing operation
        if method.upper() in ['POST', 'PUT', 'PATCH', 'DELETE']:
            # Check for authentication controls
            has_auth = False
            for control in controls_lower:
                if any(keyword in control for keyword in auth_keywords_lower):
                    has_auth = True
                    break
            
            # Generate finding if no auth found
            if not has_auth:
                # Format the message and snippet for compatibility with Finding dataclass
                message = f'State-changing endpoint lacks authentication: {method} {pattern}'
                snippet = f'{method} {pattern} - No auth middleware detected'
                
                finding = {
                    'pattern_name': 'MISSING_API_AUTHENTICATION',
                    'message': message,
                    'file': file,
                    'line': line if line else 0,
                    'column': 0,
                    'severity': 'high',
                    'snippet': snippet,
                    'category': 'security',
                    'match_type': 'database',
                    'framework': None,
                    'details': {
                        'method': method,
                        'pattern': pattern,
                        'controls': controls,
                        'recommendation': 'Add authentication middleware or decorator to protect this endpoint'
                    }
                }
                findings.append(finding)
    
    conn.close()
    return findings