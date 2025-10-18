"""Tests for JWT security analyzer (theauditor/rules/auth/jwt_analyze.py).

Tests verify JWT security detection including:
- Hardcoded secrets (CRITICAL)
- Weak algorithms ('none' algorithm)
- Algorithm confusion (HS256 + RS256)
- Sensitive data in payloads
- Insecure storage (localStorage)
- Environment variable patterns
"""

import pytest
import sqlite3
import subprocess
import json
from pathlib import Path


class TestJWTHardcodedSecrets:
    """Test detection of hardcoded JWT secrets."""

    def test_detects_hardcoded_secret_python(self, sample_project):
        """Verify detection of hardcoded JWT secret in Python."""
        # Create Python file with hardcoded JWT secret
        (sample_project / "auth.py").write_text('''
import jwt

def create_token(user_id):
    payload = {"user_id": user_id}
    # CRITICAL: Hardcoded secret
    token = jwt.encode(payload, "super-secret-key-123", algorithm="HS256")
    return token
''')

        # Run indexer to extract JWT patterns
        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        # Verify JWT pattern was extracted to database
        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM jwt_patterns WHERE secret_source = 'hardcoded'")
        hardcoded_count = cursor.fetchone()[0]
        conn.close()

        assert hardcoded_count >= 1, f"Expected hardcoded JWT secret, got {hardcoded_count}"

    def test_detects_hardcoded_secret_javascript(self, sample_project):
        """Verify detection of hardcoded JWT secret in JavaScript."""
        (sample_project / "auth.js").write_text('''
const jwt = require('jsonwebtoken');

function createToken(userId) {
    const payload = { userId: userId };
    // CRITICAL: Hardcoded secret
    const token = jwt.sign(payload, "my-hardcoded-secret", { algorithm: 'HS256' });
    return token;
}
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM jwt_patterns WHERE secret_source = 'hardcoded'")
        hardcoded_count = cursor.fetchone()[0]
        conn.close()

        assert hardcoded_count >= 1, "Should detect hardcoded JWT secret in JS"


class TestJWTWeakAlgorithms:
    """Test detection of weak JWT algorithms."""

    def test_detects_none_algorithm(self, sample_project):
        """Verify detection of dangerous 'none' algorithm."""
        (sample_project / "verify.js").write_text('''
const jwt = require('jsonwebtoken');

function verifyToken(token) {
    // CRITICAL: Allows 'none' algorithm
    return jwt.verify(token, secret, { algorithms: ['HS256', 'none'] });
}
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check for 'none' algorithm vulnerability
        cursor.execute("SELECT COUNT(*) FROM jwt_patterns WHERE allows_none = 1")
        allows_none_count = cursor.fetchone()[0]
        conn.close()

        assert allows_none_count >= 1, "Should detect 'none' algorithm vulnerability"

    def test_detects_algorithm_confusion(self, sample_project):
        """Verify detection of algorithm confusion (HS256 + RS256)."""
        (sample_project / "mixed_algo.js").write_text('''
const jwt = require('jsonwebtoken');

function verifyTokenMixed(token) {
    // CRITICAL: Algorithm confusion - both symmetric and asymmetric
    return jwt.verify(token, secret, { algorithms: ['HS256', 'RS256'] });
}
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM jwt_patterns WHERE has_confusion = 1")
        confusion_count = cursor.fetchone()[0]
        conn.close()

        assert confusion_count >= 1, "Should detect algorithm confusion"


class TestJWTSensitiveData:
    """Test detection of sensitive data in JWT payloads."""

    def test_detects_password_in_payload(self, sample_project):
        """Verify detection of password in JWT payload."""
        (sample_project / "bad_payload.py").write_text('''
import jwt

def create_user_token(user):
    # CRITICAL: Password in JWT payload
    payload = {
        "user_id": user.id,
        "email": user.email,
        "password": user.password  # NEVER do this
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT sensitive_fields FROM jwt_patterns WHERE sensitive_fields IS NOT NULL")
        sensitive_rows = cursor.fetchall()
        conn.close()

        assert len(sensitive_rows) >= 1, "Should detect sensitive data in JWT payload"

    def test_detects_credit_card_in_payload(self, sample_project):
        """Verify detection of credit card in JWT payload."""
        (sample_project / "payment_token.js").write_text('''
const jwt = require('jsonwebtoken');

function createPaymentToken(payment) {
    // CRITICAL: Credit card in JWT
    const payload = {
        userId: payment.userId,
        creditCard: payment.cardNumber,  // NEVER do this
        cvv: payment.cvv
    };
    return jwt.sign(payload, process.env.JWT_SECRET, { algorithm: 'HS256' });
}
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT sensitive_fields FROM jwt_patterns WHERE sensitive_fields IS NOT NULL")
        sensitive_rows = cursor.fetchall()
        conn.close()

        assert len(sensitive_rows) >= 1, "Should detect credit card in JWT payload"


class TestJWTEnvironmentVariables:
    """Test detection of safe vs unsafe environment variables."""

    def test_accepts_env_secret(self, sample_project):
        """Verify that environment variable secrets are not flagged (safe pattern)."""
        (sample_project / "safe_auth.py").write_text('''
import os
import jwt

def create_token(user_id):
    payload = {"user_id": user_id}
    # SAFE: Environment variable
    secret = os.environ.get("JWT_SECRET")
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Should detect as 'env' source, not 'hardcoded'
        cursor.execute("SELECT COUNT(*) FROM jwt_patterns WHERE secret_source = 'env'")
        env_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM jwt_patterns WHERE secret_source = 'hardcoded'")
        hardcoded_count = cursor.fetchone()[0]

        conn.close()

        assert env_count >= 1, "Should detect environment variable usage"
        assert hardcoded_count == 0, "Should not flag env vars as hardcoded"


class TestJWTInsecureDecode:
    """Test detection of insecure JWT decode (no verification)."""

    def test_detects_insecure_decode(self, sample_project):
        """Verify detection of jwt.decode() without verification."""
        (sample_project / "insecure_decode.js").write_text('''
const jwt = require('jsonwebtoken');

function getUserFromToken(token) {
    // CRITICAL: Decode without verification
    const decoded = jwt.decode(token);
    return decoded.userId;
}
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM jwt_patterns WHERE type = 'jwt_decode'")
        decode_count = cursor.fetchone()[0]
        conn.close()

        assert decode_count >= 1, "Should detect insecure jwt.decode()"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
