# Rule Enhancement Opportunities

This document consolidates all detection gaps and enhancement opportunities identified during the Wave 1 migration. Each entry includes the exact file, what's missing, why it matters, and how to implement it.

---

## auth/jwt_analyze.py

### 1. JWT Header Injection: 'kid' (Key ID)

**What:** Detect when `kid` header parameter is used without validation, allowing attackers to inject arbitrary key IDs.

**Why:** Attackers can manipulate `kid` to point to a file on the server (e.g., `/dev/null`, `/etc/passwd`) or a URL they control, leading to key confusion attacks. CWE-20.

**How:**
```python
def _check_kid_injection(db: RuleDB) -> list[StandardFinding]:
    """Detect unvalidated kid header parameter usage."""
    # Look for jwt.verify/decode calls where options contain 'kid'
    # Flag if no validation/whitelist of kid values before use
    # Check for file path patterns in kid values: /, .., /etc/, /dev/
    # Check for URL patterns in kid values: http://, https://
```

**Severity:** CRITICAL | **CWE:** CWE-20

---

### 2. JWT Header Injection: 'jku' (JWK Set URL)

**What:** Detect when `jku` header is accepted without URL validation, allowing attackers to specify malicious JWK endpoints.

**Why:** Attacker sets `jku` to their server, serves a JWK set with their public key, signs token with their private key. Server fetches attacker's JWK and validates the forged token. CWE-20.

**How:**
```python
def _check_jku_injection(db: RuleDB) -> list[StandardFinding]:
    """Detect unvalidated jku header parameter."""
    # Look for JWT verification that doesn't whitelist jku URLs
    # Flag any dynamic jku fetching without domain validation
    # Check for jose.JWT.verify options accepting jku
```

**Severity:** CRITICAL | **CWE:** CWE-20

---

### 3. JWT Header Injection: 'x5u' (X.509 URL)

**What:** Detect when `x5u` header is accepted without validation, similar to jku but for X.509 certificate chains.

**Why:** Same attack vector as jku - attacker hosts malicious certificate chain. CWE-20.

**How:**
```python
def _check_x5u_injection(db: RuleDB) -> list[StandardFinding]:
    """Detect unvalidated x5u header parameter."""
    # Similar to jku - check for x5u URL acceptance
    # Flag if no certificate chain validation
```

**Severity:** CRITICAL | **CWE:** CWE-20

---

### 4. JWT Replay Attacks (Missing 'jti' Claim)

**What:** Detect JWT tokens created/verified without `jti` (JWT ID) claim for replay protection.

**Why:** Without unique token IDs, captured tokens can be replayed indefinitely until expiration. Critical for financial/sensitive operations. CWE-294.

**How:**
```python
def _check_missing_jti(db: RuleDB) -> list[StandardFinding]:
    """Detect JWT creation without jti claim."""
    # Look for jwt.sign calls
    # Check if payload contains 'jti' field
    # Also check if verification validates jti against a store
```

**Severity:** HIGH | **CWE:** CWE-294

---

### 5. Missing 'aud' (Audience) Claim Validation

**What:** Detect JWT verification that doesn't validate the `aud` claim.

**Why:** Tokens issued for one service can be used on another if audience isn't validated. Token confusion attack. CWE-287.

**How:**
```python
def _check_missing_audience_validation(db: RuleDB) -> list[StandardFinding]:
    """Detect JWT verification without audience validation."""
    # Look for jwt.verify calls
    # Check if options include 'audience' parameter
    # Flag if verification proceeds without audience check
```

**Severity:** HIGH | **CWE:** CWE-287

---

### 6. Missing 'iss' (Issuer) Claim Validation

**What:** Detect JWT verification that doesn't validate the `iss` claim.

**Why:** Tokens from untrusted issuers could be accepted. Multi-tenant systems especially vulnerable. CWE-287.

**How:**
```python
def _check_missing_issuer_validation(db: RuleDB) -> list[StandardFinding]:
    """Detect JWT verification without issuer validation."""
    # Look for jwt.verify calls
    # Check if options include 'issuer' parameter
    # Flag if verification proceeds without issuer check
```

**Severity:** HIGH | **CWE:** CWE-287

---

## auth/oauth_analyze.py

### 7. PKCE Bypass Detection

**What:** Detect OAuth flows that don't implement PKCE (Proof Key for Code Exchange) or implement it incorrectly.

**Why:** Without PKCE, authorization code interception attacks are possible on mobile/SPA apps. PKCE is now recommended for ALL OAuth clients. CWE-352.

**How:**
```python
def _check_missing_pkce(db: RuleDB) -> list[StandardFinding]:
    """Detect OAuth authorization requests without PKCE."""
    # Look for authorization URL construction
    # Check for code_challenge and code_challenge_method parameters
    # Also check token exchange for code_verifier
    # Flag if using authorization_code grant without PKCE
```

**Severity:** HIGH | **CWE:** CWE-352

---

### 8. OAuth State Fixation

**What:** Detect when OAuth state parameter is predictable or reused across sessions.

**Why:** Attacker can pre-generate state, trick victim into using it, then hijack the OAuth callback. CWE-384.

**How:**
```python
def _check_state_fixation(db: RuleDB) -> list[StandardFinding]:
    """Detect predictable or reused OAuth state parameters."""
    # Look for state generation
    # Flag if state is not cryptographically random
    # Flag if state is stored in URL or predictable location
    # Check for state reuse patterns
```

**Severity:** HIGH | **CWE:** CWE-384

---

### 9. OAuth Scope Escalation

**What:** Detect when OAuth scope validation is missing or scopes can be escalated.

**Why:** Users might grant minimal scopes, but application requests or accepts broader scopes. Privilege escalation. CWE-269.

**How:**
```python
def _check_scope_escalation(db: RuleDB) -> list[StandardFinding]:
    """Detect OAuth scope validation issues."""
    # Look for scope handling in token response
    # Flag if granted scopes aren't validated against requested
    # Check for dynamic scope modification
```

**Severity:** MEDIUM | **CWE:** CWE-269

---

## auth/password_analyze.py

### 10. Password Reset Token Timing Attacks

**What:** Detect password reset token verification vulnerable to timing attacks.

**Why:** Non-constant-time comparison of reset tokens allows attackers to brute-force tokens character by character. CWE-208.

**How:**
```python
def _check_reset_token_timing(db: RuleDB) -> list[StandardFinding]:
    """Detect timing-vulnerable token comparisons."""
    # Look for password reset token verification
    # Flag if using == instead of constant-time comparison
    # Check for hmac.compare_digest, secrets.compare_digest usage
    # Flag direct string comparison of tokens
```

**Severity:** HIGH | **CWE:** CWE-208

---

### 11. Insecure Password Recovery Flows

**What:** Detect insecure password recovery implementations (security questions, email-only, predictable tokens).

**Why:** Weak recovery flows are often the weakest link in authentication. CWE-640.

**How:**
```python
def _check_insecure_recovery(db: RuleDB) -> list[StandardFinding]:
    """Detect insecure password recovery patterns."""
    # Look for security question implementations
    # Flag password hints storage
    # Check reset token entropy (should be 128+ bits)
    # Flag reset tokens without expiration
```

**Severity:** HIGH | **CWE:** CWE-640

---

### 12. Credential Stuffing Mitigations

**What:** Detect missing rate limiting, account lockout, or CAPTCHA on login endpoints.

**Why:** Without these controls, attackers can test millions of stolen credentials. CWE-307.

**How:**
```python
def _check_credential_stuffing_protection(db: RuleDB) -> list[StandardFinding]:
    """Detect missing credential stuffing protections."""
    # Look for login/authentication endpoints
    # Check for rate limiting middleware
    # Check for account lockout after failed attempts
    # Check for CAPTCHA integration
```

**Severity:** MEDIUM | **CWE:** CWE-307

---

### 13. Passwords in Logging Statements

**What:** Detect when password variables are passed to logging functions.

**Why:** Passwords in logs are exposed to anyone with log access, stored in plain text. CWE-532.

**How:**
```python
def _check_password_logging(db: RuleDB) -> list[StandardFinding]:
    """Detect passwords being logged."""
    # Look for logging function calls (logger.info, console.log, print)
    # Check if arguments contain password variables
    # Flag any password keyword in log arguments
```

**Severity:** CRITICAL | **CWE:** CWE-532

---

### 14. Bcrypt Cost Factor Too Low

**What:** Detect bcrypt usage with cost factor below 12.

**Why:** Cost factor 10 (default) is now too fast with modern GPUs. OWASP recommends 12+. CWE-916.

**How:**
```python
def _check_bcrypt_cost(db: RuleDB) -> list[StandardFinding]:
    """Detect bcrypt with insufficient cost factor."""
    # Look for bcrypt.hash, bcrypt.hashSync calls
    # Check the rounds/cost parameter
    # Flag if < 12 or using default
```

**Severity:** MEDIUM | **CWE:** CWE-916

---

## auth/session_analyze.py

### 15. Session ID in URL Parameters

**What:** Detect session IDs passed via URL query parameters or path.

**Why:** Session IDs in URLs leak via Referer header, browser history, logs. CWE-598.

**How:**
```python
def _check_session_in_url(db: RuleDB) -> list[StandardFinding]:
    """Detect session IDs in URL parameters."""
    # Look for URL construction with session/sid/token parameters
    # Check for JSESSIONID, PHPSESSID patterns in URLs
    # Flag any session identifier in query strings
```

**Severity:** HIGH | **CWE:** CWE-598

---

### 16. Session ID Predictability

**What:** Detect session ID generation using weak randomness.

**Why:** Predictable session IDs can be brute-forced or guessed. CWE-330.

**How:**
```python
def _check_session_predictability(db: RuleDB) -> list[StandardFinding]:
    """Detect weak session ID generation."""
    # Look for session ID generation code
    # Flag Math.random(), random.random() for session IDs
    # Check for timestamp-based session IDs
    # Recommend crypto.randomBytes, secrets.token_urlsafe
```

**Severity:** CRITICAL | **CWE:** CWE-330

---

### 17. Session Invalidation on Logout

**What:** Detect logout implementations that don't properly invalidate server-side sessions.

**Why:** Client-side only logout leaves session valid for replay. CWE-613.

**How:**
```python
def _check_logout_invalidation(db: RuleDB) -> list[StandardFinding]:
    """Detect improper session invalidation on logout."""
    # Look for logout handlers
    # Check for session.destroy(), req.session = null
    # Flag if only cookie deletion without server-side invalidation
```

**Severity:** HIGH | **CWE:** CWE-613

---

### 18. Concurrent Session Control

**What:** Detect missing concurrent session limits allowing unlimited simultaneous sessions.

**Why:** Compromised credentials can be used indefinitely without detection. CWE-384.

**How:**
```python
def _check_concurrent_sessions(db: RuleDB) -> list[StandardFinding]:
    """Detect missing concurrent session controls."""
    # Look for login/session creation
    # Check for session count validation
    # Flag if no mechanism to limit or alert on concurrent sessions
```

**Severity:** LOW | **CWE:** CWE-384

---

### 19. Session Isolation Issues

**What:** Detect session data that could leak between users (shared caches, global state).

**Why:** Session pollution allows one user to access another's session data. CWE-488.

**How:**
```python
def _check_session_isolation(db: RuleDB) -> list[StandardFinding]:
    """Detect session isolation vulnerabilities."""
    # Look for global/shared state used with session data
    # Check for session data in shared caches without user scoping
    # Flag static variables holding session info
```

**Severity:** HIGH | **CWE:** CWE-488

---

## logic/general_logic_analyze.py

### 20. Integer Overflow in Financial Calculations

**What:** Detect integer arithmetic on financial values that could overflow.

**Why:** Integer overflow in money calculations causes incorrect amounts, potential fraud. CWE-190.

**How:**
```python
def _check_integer_overflow_financial(db: RuleDB) -> list[StandardFinding]:
    """Detect integer overflow risks in financial code."""
    # Look for multiplication/addition on money/price/amount variables
    # Flag operations without overflow checks
    # Check for BigInt/Decimal usage for large amounts
    # Flag 32-bit integers for currency (cents overflow at $21M)
```

**Severity:** CRITICAL | **CWE:** CWE-190

---

### 21. Race Conditions in Concurrent Code

**What:** Detect check-then-act patterns without proper synchronization.

**Why:** TOCTOU (time-of-check-time-of-use) bugs cause security vulnerabilities in concurrent code. CWE-362.

**How:**
```python
def _check_race_conditions(db: RuleDB) -> list[StandardFinding]:
    """Detect potential race conditions."""
    # Look for if-check followed by state modification
    # Flag file existence checks followed by file operations
    # Check for balance checks followed by withdrawals
    # Flag any check-then-act without locking
```

**Severity:** HIGH | **CWE:** CWE-362

---

## Implementation Priority

| Priority | Items | Rationale |
|----------|-------|-----------|
| P0 - Critical | 1, 2, 3, 13, 16, 20 | Direct security bypass or data exposure |
| P1 - High | 4, 5, 6, 7, 8, 10, 11, 15, 17, 19, 21 | Significant security impact |
| P2 - Medium | 9, 12, 14 | Defense in depth |
| P3 - Low | 18 | Nice to have |

---

## Notes

- All new checks should follow the existing pattern: helper function returning `list[StandardFinding]`
- Each check needs appropriate false positive mitigation (test file exclusion, etc.)
- CWE IDs verified against MITRE CWE database
- Consider creating new rule files for complex checks (e.g., `jwt_header_injection_analyze.py`)
