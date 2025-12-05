# Tasks: Migrate Rules to Fidelity Layer (Phase 2)

## CRITICAL READS BEFORE ANY WORK

**STOP. Read these files FIRST. Do NOT touch any rule file until you have read ALL of these.**

Every terminal MUST read these files in order:

| Priority | File | Why | Time |
|----------|------|-----|------|
| 1 | `CLAUDE.md` | ALL sections - ZERO FALLBACK, environment, forbidden patterns | 5 min |
| 2 | `theauditor/rules/RULES_HANDOFF.md` | Fidelity philosophy, Q class cheat sheet, common gotchas | 5 min |
| 3 | `theauditor/rules/TEMPLATE_FIDELITY_RULE.py` | THE canonical template - copy this structure EXACTLY | 3 min |
| 4 | `theauditor/rules/base.py` | StandardFinding, StandardRuleContext, RuleMetadata definitions | 3 min |
| 5 | `theauditor/indexer/schema.py` | TABLES dict - know what tables/columns exist | 2 min |
| 6 | This file's "Common Patterns" section | Quick conversion reference | 2 min |
| 7 | `design.md` in this directory | Schema Reference, Q Class API, Quality Mandate | 5 min |

**Total: ~25 minutes of reading BEFORE starting. This is mandatory.**

**If you skip RULES_HANDOFF.md and TEMPLATE_FIDELITY_RULE.py, you WILL write rules incorrectly and your work will be rejected.**

---

## RuleMetadata Definition (EMBEDDED - Do NOT Hunt)

Location: `theauditor/rules/base.py:145-159`

```python
from theauditor.rules.base import RuleMetadata

@dataclass
class RuleMetadata:
    """Metadata describing rule requirements for smart orchestrator filtering."""

    name: str                                           # Unique rule identifier
    category: str                                       # Grouping category

    target_extensions: list[str] | None = None          # File extensions to analyze
    exclude_patterns: list[str] | None = None           # Patterns to skip
    target_file_patterns: list[str] | None = None       # Specific file patterns

    execution_scope: Literal["database", "file"] | None = None  # "database" or "file"

    requires_jsx_pass: bool = False                     # JSX extraction required?
    jsx_pass_mode: str = "preserved"                    # JSX mode
```

**Usage in rules:**
```python
METADATA = RuleMetadata(
    name="sql_injection",
    category="security",
    target_extensions=[".py", ".js", ".ts"],
    exclude_patterns=["test/", "node_modules/", "migration/"],
    requires_jsx_pass=False,
    execution_scope="database",
)
```

---

## RULE QUALITY MANDATE - READ THIS CAREFULLY

**THIS IS NOT JUST A MECHANICAL MIGRATION.**

Rules are the billion-dollar valuation of TheAuditor. If rules miss vulnerabilities, have false positives, or don't detect modern attack patterns - the entire tool is worthless.

This migration is the ONLY time we will comprehensively touch all 95 rules. Every terminal MUST evaluate rule quality, not just convert syntax.

### Per-Rule Quality Evaluation (MANDATORY)

For EACH rule file you process, you MUST answer these questions:

| Question | What to Look For |
|----------|------------------|
| **What does this rule detect?** | Can you explain in one sentence? |
| **Is detection logic sound?** | Does it actually catch the vulnerability? |
| **False positive patterns?** | Logging, testing, comments, dead code, safe wrappers |
| **Missing attack patterns?** | Modern frameworks, alternative syntax, edge cases |
| **CWE-ID correct?** | Does it match what the rule actually detects? |
| **Severity appropriate?** | CRITICAL=RCE, HIGH=data breach, MEDIUM=info leak, LOW=best practice |

### What To Do With Quality Findings

| Finding Type | Action |
|--------------|--------|
| **Simple fix** | Fix inline now (add pattern, adjust severity) |
| **Needs research** | Add `# TODO(quality): <description>` comment |
| **Major rework** | Document in terminal completion report |

### Quality Gate - Rule NOT Complete Until:

- [ ] Detection logic evaluated (not just read, EVALUATED)
- [ ] False positive patterns identified (at least: logging, testing, dead code)
- [ ] Missing patterns documented as TODO if not fixing now
- [ ] CWE-ID verified against actual detection
- [ ] Severity reviewed for appropriateness
- [ ] Structure matches TEMPLATE_FIDELITY_RULE.py

**If you skip quality evaluation, your work will be rejected.**

---

## PHASE 0: FOUNDATION (Blocking - VERIFY Phase 1 Complete)

**Assigned to: Terminal 0 (Orchestrator/Lead)**

**NOTE:** Phase 0 is VERIFICATION that Phase 1 (`add-rules-data-fidelity`) is complete.
If files don't exist, complete Phase 1 first. Do NOT start Wave 1 until Phase 0 passes.

### 0.1 Verify Query Builder Exists

Location: `theauditor/rules/query.py` (should exist from Phase 1)

- [ ] 0.1.1 VERIFY file exists: `ls theauditor/rules/query.py`
- [ ] 0.1.2 VERIFY Q class has `.select()` method
- [ ] 0.1.3 VERIFY Q class has `.where()` method
- [ ] 0.1.4 VERIFY Q class has `.join()` method with FK auto-detect
- [ ] 0.1.5 VERIFY Q class has `.with_cte()` method for CTE support
- [ ] 0.1.6 VERIFY Q class has `.order_by()` method
- [ ] 0.1.7 VERIFY Q class has `.limit()` method
- [ ] 0.1.8 VERIFY Q class has `.group_by()` method
- [ ] 0.1.9 VERIFY Q class has `.build()` method returning (sql, params)
- [ ] 0.1.10 VERIFY `Q.raw()` escape hatch exists

**If any VERIFY fails:** Complete Phase 1 tasks for that item first.

### 0.2 Verify Fidelity Infrastructure Exists

Location: `theauditor/rules/fidelity.py` (should exist from Phase 1)

- [ ] 0.2.1 VERIFY file exists: `ls theauditor/rules/fidelity.py`
- [ ] 0.2.2 VERIFY `RuleResult` dataclass exists (findings + manifest)
- [ ] 0.2.3 VERIFY `RuleManifest` class exists
- [ ] 0.2.4 VERIFY `RuleDB` class exists with `query()` and `execute()` methods
- [ ] 0.2.5 VERIFY `FidelityError` exception class exists
- [ ] 0.2.6 VERIFY `verify_fidelity()` function exists

**If any VERIFY fails:** Complete Phase 1 tasks for that item first.

### 0.3 Verify Base Module Updated

Location: `theauditor/rules/base.py:132` (RuleFunction type hint)

- [ ] 0.3.1 VERIFY `RuleResult` is imported from fidelity
- [ ] 0.3.2 VERIFY `RuleResult` in exports (if `__all__` exists)
- [ ] 0.3.3 VERIFY `RuleFunction` type hint allows `RuleResult` return

### 0.4 Verify Orchestrator Updated

Location: `theauditor/rules/orchestrator.py`

**Hook Points (VERIFIED 2025-12-04):**
- `RulesOrchestrator.__init__`: line 57
- `_execute_rule()` method: lines 483-499
- Rule function call: line 490 (`findings = rule.function(std_context)`)

- [ ] 0.4.1 VERIFY `RuleResult` import exists at top of file
- [ ] 0.4.2 VERIFY `_fidelity_failures` list in `__init__` (around line 68)
- [ ] 0.4.3 VERIFY `_execute_rule()` at line 483-499 handles `RuleResult` return type
- [ ] 0.4.4 VERIFY `_compute_expected()` method exists
- [ ] 0.4.5 VERIFY `get_aggregated_manifests()` method exists

**If any VERIFY fails:** Complete Phase 1 orchestrator integration first.

### 0.5 Validate Foundation (All Phase 1 Complete)

- [ ] 0.5.1 Run import validation:
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.rules.query import Q
from theauditor.rules.fidelity import RuleResult, RuleDB, RuleManifest
from theauditor.rules.base import RuleResult as BaseRuleResult
print('Foundation OK')
"
```
- [ ] 0.5.2 Test Q class against live database:
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.rules.query import Q
sql, params = Q('symbols').select('name', 'line').where('type = ?', 'function').limit(3).build()
print(f'SQL: {sql}')
print(f'Params: {params}')
"
```

---

## WAVE 1: Files 1-50

**REMINDER: You MUST have read ALL Critical Reads + Quality Mandate sections before starting.**

### Task Format for ALL Files

Each file task includes BOTH mechanical and quality work:

```
- [ ] T#.## filename.py:
  - [ ] Read file FULLY
  - [ ] QUALITY: Evaluate detection logic effectiveness
  - [ ] QUALITY: Identify false positive patterns
  - [ ] QUALITY: Document missing attack patterns (TODO if not fixing)
  - [ ] QUALITY: Verify CWE-ID and severity
  - [ ] Convert to Q class + RuleDB + RuleResult
  - [ ] Fix any CLAUDE.md violations
  - [ ] Verify structure matches TEMPLATE_FIDELITY_RULE.py
  - [ ] Validate import works
```

---

### Terminal 1: Files 01-05

**Files:**
```
theauditor/rules/auth/jwt_analyze.py
theauditor/rules/auth/oauth_analyze.py
theauditor/rules/auth/password_analyze.py
theauditor/rules/auth/session_analyze.py
theauditor/rules/bash/dangerous_patterns_analyze.py
```

**Tasks (full format - mechanical + quality):**

- [ ] T1.01 jwt_analyze.py:
  - [ ] Read FULLY, understand JWT vulnerability detection
  - [ ] QUALITY: Evaluate - does it catch weak algorithms (none, HS256 with public key)?
  - [ ] QUALITY: False positives - safe JWT libraries, test fixtures?
  - [ ] QUALITY: Missing - modern JWT attacks (alg confusion, kid injection)?
  - [ ] QUALITY: Verify CWE (should be CWE-327 weak crypto or CWE-347 improper verification)
  - [ ] Convert to Q/RuleDB, return RuleResult
  - [ ] Match TEMPLATE_FIDELITY_RULE.py structure
  - [ ] Validate import

- [ ] T1.02 oauth_analyze.py:
  - [ ] Read FULLY, understand OAuth vulnerability detection
  - [ ] QUALITY: Evaluate - CSRF in OAuth flow, open redirects, token leakage?
  - [ ] QUALITY: False positives - legitimate OAuth configs?
  - [ ] QUALITY: Missing - PKCE bypass, state fixation, scope escalation?
  - [ ] QUALITY: Verify CWE (CWE-352 CSRF, CWE-601 open redirect)
  - [ ] Convert to Q/RuleDB, return RuleResult
  - [ ] Match TEMPLATE_FIDELITY_RULE.py structure
  - [ ] Validate import

- [ ] T1.03 password_analyze.py:
  - [ ] Read FULLY, understand password handling detection
  - [ ] QUALITY: Evaluate - weak hashing, plaintext storage, no salt?
  - [ ] QUALITY: False positives - password strength checkers, test data?
  - [ ] QUALITY: Missing - timing attacks, credential stuffing patterns?
  - [ ] QUALITY: Verify CWE (CWE-916 weak hash, CWE-256 plaintext storage)
  - [ ] Convert to Q/RuleDB, return RuleResult
  - [ ] Match TEMPLATE_FIDELITY_RULE.py structure
  - [ ] Validate import

- [ ] T1.04 session_analyze.py:
  - [ ] Read FULLY, understand session vulnerability detection
  - [ ] QUALITY: Evaluate - fixation, prediction, insufficient expiry?
  - [ ] QUALITY: False positives - secure session configs?
  - [ ] QUALITY: Missing - cookie flags, session binding, regeneration?
  - [ ] QUALITY: Verify CWE (CWE-384 session fixation, CWE-613 insufficient expiry)
  - [ ] Convert to Q/RuleDB, return RuleResult
  - [ ] Match TEMPLATE_FIDELITY_RULE.py structure
  - [ ] Validate import

- [ ] T1.05 dangerous_patterns_analyze.py:
  - [ ] Read FULLY, understand bash dangerous pattern detection
  - [ ] QUALITY: Evaluate - command injection, unsafe expansion, eval?
  - [ ] QUALITY: False positives - quoted/escaped patterns, comments?
  - [ ] QUALITY: Missing - modern shell injection vectors, heredoc issues?
  - [ ] QUALITY: Verify CWE (CWE-78 OS command injection)
  - [ ] Convert to Q/RuleDB, return RuleResult
  - [ ] Match TEMPLATE_FIDELITY_RULE.py structure
  - [ ] Validate import

- [ ] T1.V1 Validate all 5 files import correctly
- [ ] T1.QR Quality Report: Document any major findings that need follow-up

---

### Terminal 2: Files 06-10

**Files:**
```
theauditor/rules/bash/injection_analyze.py
theauditor/rules/bash/quoting_analyze.py
theauditor/rules/build/bundle_analyze.py
theauditor/rules/dependency/bundle_size.py
theauditor/rules/dependency/dependency_bloat.py
```

**Tasks (apply full format from Terminal 1 template):**

- [ ] T2.01 injection_analyze.py:
  - [ ] Read + QUALITY evaluate (shell injection - CWE-78)
  - [ ] Check: variable interpolation, backticks, $() in untrusted input
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T2.02 quoting_analyze.py:
  - [ ] Read + QUALITY evaluate (improper quoting - CWE-78)
  - [ ] Check: unquoted variables, word splitting, glob expansion
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T2.03 bundle_analyze.py:
  - [ ] Read + QUALITY evaluate (build security - CWE-829)
  - [ ] Check: eval in webpack, dynamic imports, source map exposure
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T2.04 bundle_size.py:
  - [ ] Read + QUALITY evaluate (performance/bloat - informational)
  - [ ] Check: unused code, duplicate dependencies, tree-shaking issues
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T2.05 dependency_bloat.py:
  - [ ] Read + QUALITY evaluate (dependency issues - CWE-1104)
  - [ ] Check: redundant deps, abandoned packages, heavy alternatives
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T2.V1 Validate all 5 files import correctly
- [ ] T2.QR Quality Report: Document findings needing follow-up

---

### Terminal 3: Files 11-15

**Files:**
```
theauditor/rules/dependency/ghost_dependencies.py
theauditor/rules/dependency/peer_conflicts.py
theauditor/rules/dependency/suspicious_versions.py
theauditor/rules/dependency/typosquatting.py
theauditor/rules/dependency/unused_dependencies.py
```

**Tasks (apply full format from Terminal 1 template):**

- [ ] T3.01 ghost_dependencies.py:
  - [ ] Read + QUALITY evaluate (supply chain - CWE-1104)
  - [ ] Check: imported but not in package.json, phantom requires
  - [ ] Convert to Q/RuleDB, match template, validate
  - [ ] NOTE: This was already migrated as POC - verify quality

- [ ] T3.02 peer_conflicts.py:
  - [ ] Read + QUALITY evaluate (dependency conflict - CWE-1104)
  - [ ] Check: version mismatches, peer dep violations
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T3.03 suspicious_versions.py:
  - [ ] Read + QUALITY evaluate (supply chain - CWE-1104)
  - [ ] Check: yanked versions, malicious semver, prerelease in prod
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T3.04 typosquatting.py:
  - [ ] Read + QUALITY evaluate (supply chain attack - CWE-494)
  - [ ] Check: common typos of popular packages, homoglyph attacks
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T3.05 unused_dependencies.py:
  - [ ] Read + QUALITY evaluate (attack surface - CWE-1104)
  - [ ] Check: declared but never imported, dead devDependencies
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T3.V1 Validate all 5 files import correctly
- [ ] T3.QR Quality Report: Document findings needing follow-up

---

### Terminal 4: Files 16-20

**Files:**
```
theauditor/rules/dependency/update_lag.py
theauditor/rules/dependency/version_pinning.py
theauditor/rules/deployment/aws_cdk_encryption_analyze.py
theauditor/rules/deployment/aws_cdk_iam_wildcards_analyze.py
theauditor/rules/deployment/aws_cdk_s3_public_analyze.py
```

**Tasks (apply full format from Terminal 1 template):**

- [ ] T4.01 update_lag.py:
  - [ ] Read + QUALITY evaluate (outdated deps - CWE-1104)
  - [ ] Check: security patches behind, major versions behind
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T4.02 version_pinning.py:
  - [ ] Read + QUALITY evaluate (supply chain - CWE-1104)
  - [ ] Check: unpinned versions, floating ranges, git refs
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T4.03 aws_cdk_encryption_analyze.py:
  - [ ] Read + QUALITY evaluate (cloud misconfig - CWE-311)
  - [ ] Check: unencrypted S3/EBS/RDS, weak KMS, missing CMK
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T4.04 aws_cdk_iam_wildcards_analyze.py:
  - [ ] Read + QUALITY evaluate (privilege escalation - CWE-269)
  - [ ] Check: Action/Resource wildcards, overly permissive policies
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T4.05 aws_cdk_s3_public_analyze.py:
  - [ ] Read + QUALITY evaluate (data exposure - CWE-200)
  - [ ] Check: public ACLs, website hosting, cross-account access
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T4.V1 Validate all 5 files import correctly
- [ ] T4.QR Quality Report: Document findings needing follow-up

---

### Terminal 5: Files 21-25

**Files:**
```
theauditor/rules/deployment/aws_cdk_sg_open_analyze.py
theauditor/rules/deployment/compose_analyze.py
theauditor/rules/deployment/docker_analyze.py
theauditor/rules/deployment/nginx_analyze.py
theauditor/rules/frameworks/express_analyze.py
```

**Tasks (apply full format from Terminal 1 template):**

- [ ] T5.01 aws_cdk_sg_open_analyze.py:
  - [ ] Read + QUALITY evaluate (network exposure - CWE-284)
  - [ ] Check: 0.0.0.0/0 ingress, open ports, missing egress rules
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T5.02 compose_analyze.py:
  - [ ] Read + QUALITY evaluate (container misconfig - CWE-250)
  - [ ] Check: privileged mode, host networking, volume mounts
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T5.03 docker_analyze.py:
  - [ ] Read + QUALITY evaluate (container security - CWE-250)
  - [ ] Check: root user, secrets in build, insecure base images
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T5.04 nginx_analyze.py:
  - [ ] Read + QUALITY evaluate (web server misconfig - CWE-16)
  - [ ] Check: missing headers, directory listing, weak SSL
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T5.05 express_analyze.py:
  - [ ] Read + QUALITY evaluate (Express security - multiple CWEs)
  - [ ] Check: missing helmet, unsafe middleware, SSRF patterns
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T5.V1 Validate all 5 files import correctly
- [ ] T5.QR Quality Report: Document findings needing follow-up

---

### Terminal 6: Files 26-30

**Files:**
```
theauditor/rules/frameworks/fastapi_analyze.py
theauditor/rules/frameworks/flask_analyze.py
theauditor/rules/frameworks/nextjs_analyze.py
theauditor/rules/frameworks/react_analyze.py
theauditor/rules/frameworks/vue_analyze.py
```

**Tasks (apply full format from Terminal 1 template):**

- [ ] T6.01 fastapi_analyze.py:
  - [ ] Read + QUALITY evaluate (FastAPI security - multiple CWEs)
  - [ ] Check: missing auth on routes, unsafe Depends, SQLi in ORM
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T6.02 flask_analyze.py:
  - [ ] Read + QUALITY evaluate (Flask security - multiple CWEs)
  - [ ] Check: debug mode, secret key exposure, SSTI, unsafe redirects
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T6.03 nextjs_analyze.py:
  - [ ] Read + QUALITY evaluate (Next.js security - CWE-79, CWE-918)
  - [ ] Check: getServerSideProps SSRF, dangerouslySetInnerHTML, API route auth
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T6.04 react_analyze.py:
  - [ ] Read + QUALITY evaluate (React security - CWE-79)
  - [ ] Check: dangerouslySetInnerHTML, unsafe href, state exposure
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T6.05 vue_analyze.py:
  - [ ] Read + QUALITY evaluate (Vue security - CWE-79)
  - [ ] Check: v-html, dynamic component, template injection
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T6.V1 Validate all 5 files import correctly
- [ ] T6.QR Quality Report: Document findings needing follow-up

---

### Terminal 7: Files 31-35

**Files:**
```
theauditor/rules/github_actions/artifact_poisoning.py
theauditor/rules/github_actions/excessive_permissions.py
theauditor/rules/github_actions/reusable_workflow_risks.py
theauditor/rules/github_actions/script_injection.py
theauditor/rules/github_actions/unpinned_actions.py
```

**Tasks (apply full format from Terminal 1 template):**

- [ ] T7.01 artifact_poisoning.py:
  - [ ] Read + QUALITY evaluate (supply chain - CWE-829)
  - [ ] Check: artifact upload/download without verification, cross-workflow artifacts
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T7.02 excessive_permissions.py:
  - [ ] Read + QUALITY evaluate (privilege escalation - CWE-269)
  - [ ] Check: contents: write, packages: write, id-token without need
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T7.03 reusable_workflow_risks.py:
  - [ ] Read + QUALITY evaluate (supply chain - CWE-829)
  - [ ] Check: inheriting secrets, external workflow refs, version pinning
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T7.04 script_injection.py:
  - [ ] Read + QUALITY evaluate (code injection - CWE-94)
  - [ ] Check: ${{ github.event.* }} in run:, PR title/body injection
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T7.05 unpinned_actions.py:
  - [ ] Read + QUALITY evaluate (supply chain - CWE-829)
  - [ ] Check: @main/@master, missing SHA pins, version tags only
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T7.V1 Validate all 5 files import correctly
- [ ] T7.QR Quality Report: Document findings needing follow-up

---

### Terminal 8: Files 36-40

**Files:**
```
theauditor/rules/github_actions/untrusted_checkout.py
theauditor/rules/go/concurrency_analyze.py
theauditor/rules/go/crypto_analyze.py
theauditor/rules/go/error_handling_analyze.py
theauditor/rules/go/injection_analyze.py
```

**Tasks (apply full format from Terminal 1 template):**

- [ ] T8.01 untrusted_checkout.py:
  - [ ] Read + QUALITY evaluate (code injection - CWE-94)
  - [ ] Check: PR checkout without ref, pull_request_target misuse
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T8.02 concurrency_analyze.py:
  - [ ] Read + QUALITY evaluate (race conditions - CWE-362)
  - [ ] Check: goroutine data races, missing mutexes, channel misuse
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T8.03 crypto_analyze.py:
  - [ ] Read + QUALITY evaluate (weak crypto - CWE-327)
  - [ ] Check: math/rand for crypto, weak ciphers, hardcoded keys
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T8.04 error_handling_analyze.py:
  - [ ] Read + QUALITY evaluate (error handling - CWE-391)
  - [ ] Check: ignored error returns, blank identifier for errors
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T8.05 injection_analyze.py:
  - [ ] Read + QUALITY evaluate (injection - CWE-89, CWE-78)
  - [ ] Check: sql.Query with concatenation, exec.Command with user input
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T8.V1 Validate all 5 files import correctly
- [ ] T8.QR Quality Report: Document findings needing follow-up

---

### Terminal 9: Files 41-45

**Files:**
```
theauditor/rules/graphql/injection.py
theauditor/rules/graphql/input_validation.py
theauditor/rules/graphql/mutation_auth.py
theauditor/rules/graphql/nplus1.py
theauditor/rules/graphql/overfetch.py
```

**Tasks (apply full format from Terminal 1 template):**

- [ ] T9.01 injection.py:
  - [ ] Read + QUALITY evaluate (GraphQL injection - CWE-89, CWE-943)
  - [ ] Check: query string concatenation, resolver SQL injection
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T9.02 input_validation.py:
  - [ ] Read + QUALITY evaluate (input validation - CWE-20)
  - [ ] Check: missing scalar validation, untyped arguments
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T9.03 mutation_auth.py:
  - [ ] Read + QUALITY evaluate (broken access control - CWE-862)
  - [ ] Check: mutations without auth directives, IDOR patterns
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T9.04 nplus1.py:
  - [ ] Read + QUALITY evaluate (performance - informational)
  - [ ] Check: resolver loops without DataLoader, nested queries
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T9.05 overfetch.py:
  - [ ] Read + QUALITY evaluate (information disclosure - CWE-200)
  - [ ] Check: unbounded queries, missing field restrictions
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T9.V1 Validate all 5 files import correctly
- [ ] T9.QR Quality Report: Document findings needing follow-up

---

### Terminal 10: Files 46-50

**Files:**
```
theauditor/rules/graphql/query_depth.py
theauditor/rules/graphql/sensitive_fields.py
theauditor/rules/logic/general_logic_analyze.py
theauditor/rules/node/async_concurrency_analyze.py
theauditor/rules/node/runtime_issue_analyze.py
```

**Tasks (apply full format from Terminal 1 template):**

- [ ] T10.01 query_depth.py:
  - [ ] Read + QUALITY evaluate (DoS - CWE-400)
  - [ ] Check: recursive queries, missing depth limits
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T10.02 sensitive_fields.py:
  - [ ] Read + QUALITY evaluate (information disclosure - CWE-200)
  - [ ] Check: password/token fields exposed, introspection enabled
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T10.03 general_logic_analyze.py:
  - [ ] Read + QUALITY evaluate (logic flaws - various CWEs)
  - [ ] Check: dead code, unreachable conditions, comparison issues
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T10.04 async_concurrency_analyze.py:
  - [ ] Read + QUALITY evaluate (race conditions - CWE-362)
  - [ ] Check: unhandled rejections, race conditions, callback hell
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T10.05 runtime_issue_analyze.py:
  - [ ] Read + QUALITY evaluate (runtime security - various CWEs)
  - [ ] Check: prototype pollution, eval, Function constructor
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T10.V1 Validate all 5 files import correctly
- [ ] T10.QR Quality Report: Document findings needing follow-up

---

## WAVE 1 CHECKPOINT

Before proceeding to Wave 2:

### Mechanical Validation
- [ ] All 50 files pass import validation
- [ ] Run: `aud full --offline` on test repo - no crashes
- [ ] Zero raw `cursor.execute()` remaining in Wave 1 files

### Quality Validation
- [ ] All 10 terminals submitted Quality Reports (T#.QR)
- [ ] Quality findings documented (TODO comments or reports)
- [ ] Major rework items flagged for post-migration

### Sync Meeting Agenda
1. Any blockers encountered?
2. Patterns needing Q.raw() escape hatch?
3. Common quality issues found across rules?
4. Rules needing major rework flagged?

---

## WAVE 2: Files 51-95

**REMINDER: Apply same quality mandate as Wave 1. Every rule gets quality evaluation.**

### Terminal 1: Files 51-55

**Files:**
```
theauditor/rules/orm/prisma_analyze.py
theauditor/rules/orm/sequelize_analyze.py
theauditor/rules/orm/typeorm_analyze.py
theauditor/rules/performance/perf_analyze.py
theauditor/rules/python/async_concurrency_analyze.py
```

**Tasks (apply full format from Terminal 1 Wave 1 template):**

- [ ] T1.51 prisma_analyze.py:
  - [ ] Read + QUALITY evaluate (ORM injection - CWE-89)
  - [ ] Check: raw query usage, unsafe where clauses, client exposure
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T1.52 sequelize_analyze.py:
  - [ ] Read + QUALITY evaluate (ORM injection - CWE-89)
  - [ ] Check: literal(), query(), replacements without binding
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T1.53 typeorm_analyze.py:
  - [ ] Read + QUALITY evaluate (ORM injection - CWE-89)
  - [ ] Check: createQueryBuilder().where() with concatenation
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T1.54 perf_analyze.py:
  - [ ] Read + QUALITY evaluate (performance - informational)
  - [ ] Check: N+1 queries, unbounded loops, memory leaks
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T1.55 async_concurrency_analyze.py:
  - [ ] Read + QUALITY evaluate (race conditions - CWE-362)
  - [ ] Check: asyncio races, shared state, deadlocks
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T1.V2 Validate all 5 files import correctly
- [ ] T1.QR2 Quality Report Wave 2: Document findings

---

### Terminal 2: Files 56-60

**Files:**
```
theauditor/rules/python/python_crypto_analyze.py
theauditor/rules/python/python_deserialization_analyze.py
theauditor/rules/python/python_globals_analyze.py
theauditor/rules/python/python_injection_analyze.py
theauditor/rules/quality/deadcode_analyze.py
```

**Tasks (apply full format):**

- [ ] T2.56 python_crypto_analyze.py:
  - [ ] Read + QUALITY evaluate (weak crypto - CWE-327)
  - [ ] Check: MD5/SHA1, DES, hardcoded keys, weak random
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T2.57 python_deserialization_analyze.py:
  - [ ] Read + QUALITY evaluate (deserialization - CWE-502)
  - [ ] Check: pickle.loads, yaml.load, marshal with untrusted
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T2.58 python_globals_analyze.py:
  - [ ] Read + QUALITY evaluate (global state - CWE-362)
  - [ ] Check: mutable default args, global state races
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T2.59 python_injection_analyze.py:
  - [ ] Read + QUALITY evaluate (injection - CWE-78, CWE-94)
  - [ ] Check: os.system, subprocess, eval, exec with user input
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T2.60 deadcode_analyze.py:
  - [ ] Read + QUALITY evaluate (code quality - informational)
  - [ ] Check: unreachable code, unused variables/imports
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T2.V2 Validate all 5 files import correctly
- [ ] T2.QR2 Quality Report Wave 2: Document findings

---

### Terminal 3: Files 61-65

**Files:**
```
theauditor/rules/react/component_analyze.py
theauditor/rules/react/hooks_analyze.py
theauditor/rules/react/render_analyze.py
theauditor/rules/react/state_analyze.py
theauditor/rules/rust/ffi_boundary.py
```

**Tasks (apply full format):**

- [ ] T3.61 component_analyze.py:
  - [ ] Read + QUALITY evaluate (React security - CWE-79)
  - [ ] Check: prop drilling sensitive data, unsafe refs
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T3.62 hooks_analyze.py:
  - [ ] Read + QUALITY evaluate (React hooks - various)
  - [ ] Check: missing deps, stale closures, conditional hooks
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T3.63 render_analyze.py:
  - [ ] Read + QUALITY evaluate (XSS - CWE-79)
  - [ ] Check: dangerouslySetInnerHTML, innerHTML assignment
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T3.64 state_analyze.py:
  - [ ] Read + QUALITY evaluate (state issues - various)
  - [ ] Check: mutating state, derived state in render
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T3.65 ffi_boundary.py:
  - [ ] Read + QUALITY evaluate (memory safety - CWE-119)
  - [ ] Check: unsafe across FFI, unvalidated pointers, lifetime issues
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T3.V2 Validate all 5 files import correctly
- [ ] T3.QR2 Quality Report Wave 2: Document findings

---

### Terminal 4: Files 66-70

**Files:**
```
theauditor/rules/rust/integer_safety.py
theauditor/rules/rust/memory_safety.py
theauditor/rules/rust/panic_paths.py
theauditor/rules/rust/unsafe_analysis.py
theauditor/rules/secrets/hardcoded_secret_analyze.py
```

**Tasks (apply full format):**

- [ ] T4.66 integer_safety.py:
  - [ ] Read + QUALITY evaluate (integer overflow - CWE-190)
  - [ ] Check: unchecked arithmetic, as casts, wrapping behavior
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T4.67 memory_safety.py:
  - [ ] Read + QUALITY evaluate (memory safety - CWE-119)
  - [ ] Check: unsafe blocks, raw pointers, transmute
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T4.68 panic_paths.py:
  - [ ] Read + QUALITY evaluate (DoS - CWE-248)
  - [ ] Check: unwrap(), expect(), index without bounds check
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T4.69 unsafe_analysis.py:
  - [ ] Read + QUALITY evaluate (unsafe Rust - CWE-119)
  - [ ] Check: unsafe justification, FFI soundness, invariants
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T4.70 hardcoded_secret_analyze.py:
  - [ ] Read + QUALITY evaluate (secrets - CWE-798)
  - [ ] Check: API keys, passwords, tokens in code
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T4.V2 Validate all 5 files import correctly
- [ ] T4.QR2 Quality Report Wave 2: Document findings

---

### Terminal 5: Files 71-75

**Files:**
```
theauditor/rules/security/api_auth_analyze.py
theauditor/rules/security/cors_analyze.py
theauditor/rules/security/crypto_analyze.py
theauditor/rules/security/input_validation_analyze.py
theauditor/rules/security/pii_analyze.py
```

**Tasks (apply full format):**

- [ ] T5.71 api_auth_analyze.py:
  - [ ] Read + QUALITY evaluate (broken auth - CWE-287)
  - [ ] Check: missing auth middleware, JWT validation bypass
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T5.72 cors_analyze.py:
  - [ ] Read + QUALITY evaluate (CORS misconfig - CWE-942)
  - [ ] Check: wildcard origin, credentials with *, null origin
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T5.73 crypto_analyze.py:
  - [ ] Read + QUALITY evaluate (weak crypto - CWE-327)
  - [ ] Check: weak algorithms, ECB mode, static IVs
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T5.74 input_validation_analyze.py:
  - [ ] Read + QUALITY evaluate (input validation - CWE-20)
  - [ ] Check: missing validation, regex DoS, type confusion
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T5.75 pii_analyze.py:
  - [ ] Read + QUALITY evaluate (PII exposure - CWE-359)
  - [ ] Check: logging PII, unmasked sensitive data, storage
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T5.V2 Validate all 5 files import correctly
- [ ] T5.QR2 Quality Report Wave 2: Document findings

---

### Terminal 6: Files 76-80

**Files:**
```
theauditor/rules/security/rate_limit_analyze.py
theauditor/rules/security/sourcemap_analyze.py
theauditor/rules/security/websocket_analyze.py
theauditor/rules/sql/multi_tenant_analyze.py
theauditor/rules/sql/sql_injection_analyze.py
```

**SPECIAL NOTE:** `sql_injection_analyze.py` has CTEs - requires Q.with_cte() usage.

**Tasks (apply full format):**

- [ ] T6.76 rate_limit_analyze.py:
  - [ ] Read + QUALITY evaluate (DoS - CWE-400)
  - [ ] Check: missing rate limits on auth, expensive operations
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T6.77 sourcemap_analyze.py:
  - [ ] Read + QUALITY evaluate (info disclosure - CWE-200)
  - [ ] Check: sourcemaps in production, inline sources
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T6.78 websocket_analyze.py:
  - [ ] Read + QUALITY evaluate (websocket security - various)
  - [ ] Check: missing origin validation, auth bypass, XSS via WS
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T6.79 multi_tenant_analyze.py:
  - [ ] Read + QUALITY evaluate (authz - CWE-863)
  - [ ] Check: missing tenant isolation, cross-tenant access
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T6.80 sql_injection_analyze.py:
  - [ ] Read + QUALITY evaluate (SQLi - CWE-89) **CRITICAL RULE**
  - [ ] Check: string concat, f-strings, format(), missing parameterization
  - [ ] QUALITY: This is a flagship rule - thorough detection review
  - [ ] Convert CTEs to Q.with_cte(), match template, validate

- [ ] T6.V2 Validate all 5 files import correctly
- [ ] T6.QR2 Quality Report Wave 2: Document findings

---

### Terminal 7: Files 81-85

**Files:**
```
theauditor/rules/sql/sql_safety_analyze.py
theauditor/rules/terraform/terraform_analyze.py
theauditor/rules/typescript/type_safety_analyze.py
theauditor/rules/vue/component_analyze.py
theauditor/rules/vue/hooks_analyze.py
```

**Tasks (apply full format):**

- [ ] T7.81 sql_safety_analyze.py:
  - [ ] Read + QUALITY evaluate (SQL safety - CWE-89)
  - [ ] Check: transaction handling, prepared statements, escape functions
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T7.82 terraform_analyze.py:
  - [ ] Read + QUALITY evaluate (IaC security - various)
  - [ ] Check: hardcoded creds, public resources, missing encryption
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T7.83 type_safety_analyze.py:
  - [ ] Read + QUALITY evaluate (type safety - CWE-704)
  - [ ] Check: any usage, type assertions, runtime type loss
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T7.84 component_analyze.py (Vue):
  - [ ] Read + QUALITY evaluate (Vue security - CWE-79)
  - [ ] Check: v-html, dynamic templates, prop validation
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T7.85 hooks_analyze.py (Vue):
  - [ ] Read + QUALITY evaluate (Vue hooks/composables)
  - [ ] Check: reactive state issues, lifecycle timing
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T7.V2 Validate all 5 files import correctly
- [ ] T7.QR2 Quality Report Wave 2: Document findings

---

### Terminal 8: Files 86-90

**Files:**
```
theauditor/rules/vue/lifecycle_analyze.py
theauditor/rules/vue/reactivity_analyze.py
theauditor/rules/vue/render_analyze.py
theauditor/rules/vue/state_analyze.py
theauditor/rules/xss/dom_xss_analyze.py
```

**Tasks (apply full format):**

- [ ] T8.86 lifecycle_analyze.py (Vue):
  - [ ] Read + QUALITY evaluate (lifecycle issues)
  - [ ] Check: async in created, missing cleanup, timing bugs
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T8.87 reactivity_analyze.py (Vue):
  - [ ] Read + QUALITY evaluate (reactivity issues)
  - [ ] Check: mutating props, ref unwrapping, reactive loss
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T8.88 render_analyze.py (Vue):
  - [ ] Read + QUALITY evaluate (XSS - CWE-79)
  - [ ] Check: v-html, dynamic component, template injection
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T8.89 state_analyze.py (Vue):
  - [ ] Read + QUALITY evaluate (state management)
  - [ ] Check: store mutations outside actions, shared state
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T8.90 dom_xss_analyze.py:
  - [ ] Read + QUALITY evaluate (DOM XSS - CWE-79) **CRITICAL RULE**
  - [ ] Check: innerHTML, document.write, eval, location manipulation
  - [ ] QUALITY: Flagship XSS rule - thorough detection review
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T8.V2 Validate all 5 files import correctly
- [ ] T8.QR2 Quality Report Wave 2: Document findings

---

### Terminal 9: Files 91-95

**Files:**
```
theauditor/rules/xss/express_xss_analyze.py
theauditor/rules/xss/react_xss_analyze.py
theauditor/rules/xss/template_xss_analyze.py
theauditor/rules/xss/vue_xss_analyze.py
theauditor/rules/xss/xss_analyze.py
```

**Tasks (apply full format):**

- [ ] T9.91 express_xss_analyze.py:
  - [ ] Read + QUALITY evaluate (Express XSS - CWE-79)
  - [ ] Check: res.send with user input, missing sanitization
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T9.92 react_xss_analyze.py:
  - [ ] Read + QUALITY evaluate (React XSS - CWE-79)
  - [ ] Check: dangerouslySetInnerHTML, href=javascript:, SSR issues
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T9.93 template_xss_analyze.py:
  - [ ] Read + QUALITY evaluate (Template XSS - CWE-79)
  - [ ] Check: Jinja2/EJS/Handlebars raw output, autoescape off
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T9.94 vue_xss_analyze.py:
  - [ ] Read + QUALITY evaluate (Vue XSS - CWE-79)
  - [ ] Check: v-html, :href, v-bind, template injection
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T9.95 xss_analyze.py:
  - [ ] Read + QUALITY evaluate (General XSS - CWE-79) **FLAGSHIP RULE**
  - [ ] Check: comprehensive XSS patterns across frameworks
  - [ ] QUALITY: This is a flagship rule - thorough detection review
  - [ ] Convert to Q/RuleDB, match template, validate

- [ ] T9.V2 Validate all 5 files import correctly
- [ ] T9.QR2 Quality Report Wave 2: Document findings

---

### Terminal 10: Integration & Validation

No file assignments in Wave 2. Focus on integration testing and quality aggregation.

**Integration Tasks:**

- [ ] T10.INT1 Run full import validation for all 95 files
- [ ] T10.INT2 Run `aud full --offline` on TheAuditor itself
- [ ] T10.INT3 Run `aud full --offline` on test repository
- [ ] T10.INT4 Verify fidelity manifests are generated for all rules
- [ ] T10.INT5 Check for any remaining raw `cursor.execute()` calls
- [ ] T10.INT6 Verify all rules match TEMPLATE_FIDELITY_RULE.py structure

**Quality Aggregation Tasks:**

- [ ] T10.QA1 Collect all Quality Reports (T#.QR and T#.QR2) from all terminals
- [ ] T10.QA2 Aggregate TODO(quality) comments across all rules
- [ ] T10.QA3 Categorize findings by severity (fix now vs follow-up)
- [ ] T10.QA4 Identify rules needing major rework post-migration
- [ ] T10.QA5 Verify CWE coverage across rule categories
- [ ] T10.QA6 Generate final migration + quality report

---

## FINAL VALIDATION

After all waves complete:

### Mechanical Validation

```bash
# 1. Full import test
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import importlib
import os

rules_dir = 'theauditor/rules'
failed = []

for root, dirs, files in os.walk(rules_dir):
    dirs[:] = [d for d in dirs if not d.startswith('__')]
    for f in files:
        if f.endswith('.py') and not f.startswith('__') and not f.startswith('TEMPLATE'):
            module_path = os.path.join(root, f).replace('/', '.').replace('\\\\', '.')[:-3]
            try:
                importlib.import_module(module_path)
            except Exception as e:
                failed.append((module_path, str(e)))

if failed:
    print(f'FAILED: {len(failed)} modules')
    for m, e in failed:
        print(f'  {m}: {e}')
else:
    print('ALL IMPORTS OK')
"

# 2. Run full pipeline
aud full --offline

# 3. Check for remaining raw SQL
grep -r "cursor.execute" theauditor/rules --include="*.py" | grep -v "Q.raw" | grep -v "__pycache__"

# 4. Check all rules have RuleResult return
grep -rL "RuleResult" theauditor/rules --include="*_analyze.py" | grep -v "__pycache__"

# 5. Check all rules have METADATA
grep -rL "METADATA = RuleMetadata" theauditor/rules --include="*_analyze.py" | grep -v "__pycache__"
```

### Quality Validation

```bash
# 6. Count TODO(quality) comments (should be documented, not zero)
grep -r "TODO(quality)" theauditor/rules --include="*.py" | wc -l

# 7. Verify flagship rules have thorough coverage
# Manual review of: sql_injection_analyze.py, xss_analyze.py, dom_xss_analyze.py
```

### Success Criteria Checklist

**Mechanical (MUST ALL PASS):**
- [ ] All 95 files import successfully
- [ ] `aud full --offline` completes without crashes
- [ ] Zero raw `cursor.execute()` (grep returns empty)
- [ ] All rules return `RuleResult`
- [ ] All rules have `METADATA`
- [ ] All rules match TEMPLATE_FIDELITY_RULE.py structure

**Quality (MUST ALL BE DOCUMENTED):**
- [ ] All 20 Quality Reports collected (T#.QR + T#.QR2)
- [ ] TODO(quality) comments present where issues found
- [ ] Flagship rules (SQLi, XSS) thoroughly reviewed
- [ ] CWE coverage verified
- [ ] Major rework items identified for post-migration

---

## COMMON PATTERNS (REFERENCE)

### Pattern A: Simple Single Table Query

```python
# BEFORE
query = build_query("symbols", ["name", "path", "line"], where="type = 'function'")
cursor.execute(query)
rows = cursor.fetchall()

# AFTER
rows = db.query(
    Q("symbols")
    .select("name", "path", "line")
    .where("type = ?", "function")
)
```

### Pattern B: Two-Table JOIN

```python
# BEFORE
cursor.execute("""
    SELECT a.file, a.line, b.name
    FROM function_call_args a
    JOIN symbols b ON a.callee_function = b.name
    WHERE a.file LIKE '%test%'
""")

# AFTER
rows = db.query(
    Q("function_call_args")
    .select("a.file", "a.line", "b.name")
    .join("symbols", on=[("callee_function", "name")])
    .where("a.file LIKE ?", "%test%")
)
```

### Pattern C: CTE Query

```python
# BEFORE
cursor.execute("""
    WITH tainted_vars AS (
        SELECT file, target_var FROM assignments
        WHERE source_expr LIKE '%request%'
    )
    SELECT f.file, f.line, t.target_var
    FROM function_call_args f
    JOIN tainted_vars t ON f.file = t.file
""")

# AFTER
tainted = Q("assignments") \
    .select("file", "target_var") \
    .where("source_expr LIKE ?", "%request%")

rows = db.query(
    Q("function_call_args")
    .with_cte("tainted_vars", tainted)
    .select("f.file", "f.line", "t.target_var")
    .join("tainted_vars", on=[("file", "file")])
)
```

### Pattern D: Escape Hatch (Complex SQL)

```python
# For truly complex SQL that Q cannot express
sql, params = Q.raw("""
    SELECT ... complex vendor-specific SQL with window functions ...
""", [param1, param2])
rows = db.execute(sql, params)
```

### Pattern E: Full Rule Migration Template

```python
"""Rule description."""

from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext
from theauditor.rules.query import Q
from theauditor.rules.fidelity import RuleDB, RuleResult

METADATA = RuleMetadata(
    name="rule_name",
    category="category",
    target_extensions=[".py", ".js"],
    exclude_patterns=["test/", "node_modules/"],
    requires_jsx_pass=False,
    execution_scope="database",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Main analysis function."""
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        # Query using Q class
        rows = db.query(
            Q("table_name")
            .select("col1", "col2")
            .where("condition = ?", "value")
        )

        for col1, col2 in rows:
            # Process and create findings
            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message="Description",
                    file_path=col1,
                    line=col2,
                    severity=Severity.HIGH,
                    category=METADATA.category,
                    snippet="relevant code",
                    cwe_id="CWE-XXX",
                )
            )

        return RuleResult(findings=findings, manifest=db.get_manifest())
```
