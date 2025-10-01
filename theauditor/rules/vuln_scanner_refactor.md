# Vulnerability Scanner Complete Rewrite - Pre-Implementation Plan

**Document Version:** 1.0
**Date:** 2025-10-02
**Status:** PRE-IMPLEMENTATION REPORT (No Code Changes)
**Follows:** TeamSOP v4.20 Protocols


ultrathink hmm, you make it sound like vulnability scanner should become a shim and all of it transformed into rules, confirm
or deny, yes or no, brief reasoning

● CONFIRM

  Reasoning:

  6-10 categories should be rules (ghost deps, pinning, bloat, update lag, unused deps, bundle size, license checks, peer
  conflicts, abandonment, supply chain depth):
  - Pure database queries (package_configs, import_styles, lock_analysis)
  - Follow existing rules pattern perfectly
  - Already write to findings_consolidated
  - Rules orchestrator handles parallel execution

  2-4 categories stay in scanner shim (CVE detection, typosquatting with external APIs):
  - npm audit/pip-audit subprocess (native tools)
  - OSV.dev API calls (external network)
  - API enrichment (npm registry, PyPI metadata)

  Scanner becomes ~500 lines:
  - Tier 1: Native tool wrapper (npm audit, pip-audit)
  - Tier 2: OSV.dev API client
  - Write findings → database
  - Delegate Tiers 3-6 to rules orchestrator (already exists)

  Benefit: Rules architecture already has metadata filtering, error handling, parallel execution, FCE integration. Don't
  reinvent the wheel.


---

## Executive Summary

The current `vulnerability_scanner.py.bak` is a **subprocess-based tool wrapper** that runs `npm audit` and `pip-audit`, parses their output, and writes to JSON. It was **completely omitted from the v1.1 database-first refactor** and does not integrate with TheAuditor's gold standard architecture.

**Current State:**
- ❌ No database integration (doesn't use `package_configs`, `lock_analysis`, `findings_consolidated` tables)
- ❌ No indexer integration (doesn't query existing dependency data)
- ❌ Limited detection (only npm/pip-audit, no OSV.dev, no typosquatting, no version analysis)
- ❌ No caching (runs subprocess every time)
- ❌ No rule pattern (doesn't follow `RuleMetadata` structure)
- ❌ No dual-write (only writes JSON, not database)
- ❌ No FCE integration (findings can't be correlated)

**Target State (Gold Standard):**
- ✅ Database-first architecture (reads from `package_configs`, writes to `findings_consolidated`)
- ✅ Multi-tier detection (native tools → OSV.dev → local analysis)
- ✅ Rule-based pattern (follows `RULE_METADATA_GUIDE.md`)
- ✅ Dual-write pattern (database + JSON for AI consumption)
- ✅ Memory cache for performance (OSV.dev responses, typosquatting dictionary)
- ✅ Integration with pipeline (orchestrated like taint/patterns)
- ✅ Offline mode support (graceful degradation)

**Estimated Effort:** 8-12 hours (matches P0 estimate in findings.md)

---

## Phase 0: Verification - Current State Analysis

### Hypothesis 1: vulnerability_scanner.py was omitted from refactor
**Verification:** ✅ CONFIRMED
- File renamed to `.bak` by user
- No import in `theauditor/commands/deps.py` after line 69 (still imports from old location)
- No database writes in current implementation
- No `VulnerabilityScanner` class in indexer/taint architecture pattern

### Hypothesis 2: Current implementation is subprocess-only
**Verification:** ✅ CONFIRMED
```python
# Lines 59-199: run_npm_audit() - subprocess wrapper
result = subprocess.run(npm_cmd, capture_output=True, text=True, timeout=60)

# Lines 202-287: run_pip_audit() - subprocess wrapper
result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

# NO database queries, NO OSV.dev API, NO local analysis
```

### Hypothesis 3: No integration with indexer's package_configs table
**Verification:** ✅ CONFIRMED
```python
# Line 69: Uses deps from deps.py parameter, not database
def scan_dependencies(deps: List[Dict[str, Any]], ...)

# Expected: Query package_configs table populated by indexer
# Actual: Receives in-memory list, no database interaction
```

### Hypothesis 4: Findings not written to findings_consolidated table
**Verification:** ✅ CONFIRMED
```python
# Lines 290-335: write_vulnerabilities_json() - Only writes JSON
with open(output, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, sort_keys=True)

# NO db_manager.write_findings_batch() call
# NO findings_consolidated table usage
```

### Hypothesis 5: No caching strategy
**Verification:** ✅ CONFIRMED
- No cache directory usage (line 23: `cache_dir` parameter unused)
- Runs subprocess every time (no hash-based skip logic)
- No OSV.dev response cache
- No persistent typosquatting dictionary

### Discrepancies Found
1. **Architecture Mismatch:** Current implementation follows old "run tool → parse → JSON" pattern, not the database-first architecture established in v1.1 refactor
2. **Missing Detection Tiers:** Only uses native tools (npm audit, pip-audit), missing OSV.dev, version analysis, typosquatting detection documented in findings.md
3. **No Integration:** Doesn't read from `package_configs` table or write to `findings_consolidated` table
4. **Performance Gap:** No caching means repeated scans are slow
5. **Correlation Gap:** Findings can't be correlated by FCE because they're not in database

---

## Phase 1: Deep Root Cause Analysis

### Surface Symptom
"Dependency vulnerability scanner detected 0 vulnerabilities across all 4 test projects despite documented issues (findings.md reports 0% detection rate)"

### Problem Chain Analysis

1. **Original Design (Pre-v1.1):**
   - TheAuditor had modular tool wrappers (deps.py, vulnerability_scanner.py)
   - Each tool ran independently, wrote to `.pf/raw/` directory
   - No shared database, no cross-tool correlation

2. **v1.1 Refactor Decision:**
   - Moved to database-first architecture for performance and correlation
   - Refactored: indexer → package, taint → package, rules → database-aware
   - **vulnerability_scanner.py was NOT refactored** (oversight during sprint)

3. **Integration Breakage:**
   - `deps.py` command still imports from `vulnerability_scanner` (line 69)
   - But `vulnerability_scanner` doesn't follow new patterns
   - Findings written to JSON only, not database
   - FCE can't correlate findings (not in `findings_consolidated`)

4. **Detection Failure:**
   - Subprocess-only approach means:
     - npm audit only runs if `node_modules` exists (line 75)
     - pip-audit only runs if tool is installed (line 212)
     - No fallback to OSV.dev or local analysis
   - Result: 0% detection in validation suite

### Actual Root Cause
**"vulnerability_scanner.py was not included in the v1.1 database-first refactor, creating an architectural inconsistency where the vulnerability scanner operates as an isolated subprocess wrapper instead of an integrated database-aware analysis module."**

### Why This Happened (Historical Context)

**Design Decision:**
- Original TheAuditor (pre-v1.1) used a microservices-style architecture where each analysis tool was independent
- Tools communicated via JSON files in `.pf/raw/` directory
- This worked for MVP but prevented:
  - Cross-tool correlation (FCE couldn't connect findings)
  - Performance optimization (no shared caching)
  - Incremental analysis (re-scan everything every time)

**Refactor Scope:**
- v1.1 refactor focused on core analysis pipeline:
  - indexer: Full package refactor with extractors registry
  - taint: Full package refactor with memory cache
  - rules: Database-first with metadata filtering
  - patterns: Database-aware with orchestrator
- Dependency scanning was considered "auxiliary" and deprioritized

**Missing Safeguard:**
- No integration tests verifying database writes for all analysis modules
- No checklist ensuring all tools follow new architecture patterns
- Code review didn't catch that vulnerability scanner wasn't migrated

---

## Phase 2: Implementation Strategy & Rationale

### Architecture Decision: Database-First Multi-Tier Detection

**Tier System Rationale:**
```
Tier 1 (Native Tools - Subprocess):
├─ npm audit (if node_modules exists)
├─ pip-audit (if installed)
└─ Pros: Official sources, high accuracy
    Cons: Requires installation, slow, offline unavailable

Tier 2 (OSV.dev API - Network):
├─ Query for all packages in package_configs
├─ Unified multi-ecosystem database
└─ Pros: Always available, fast, multi-language
    Cons: Requires network, rate limits

Tier 3 (Local Analysis - Database):
├─ Version comparison (semantic versioning)
├─ Suspicious version detection (0.0.001, latest, *)
├─ Typosquatting detection (requets vs requests)
└─ Pros: Offline, instant, no dependencies
    Cons: Lower accuracy, maintenance overhead

Tier 4 (Usage Analysis - Database):
├─ Cross-reference with import_styles table
├─ Detect unused dependencies (declared but not imported)
├─ Severity boost for actively-used packages
└─ Pros: Context-aware risk scoring
    Cons: Requires indexer completion
```

**Decision:** Implement all 4 tiers with graceful degradation
- Offline mode: Only Tier 3 + Tier 4 (local analysis)
- Network available: All tiers with parallel execution
- No native tools: Tier 2 + Tier 3 + Tier 4

**Alternative Considered:** Subprocess-only (current approach)
**Rejected Because:**
- 0% detection rate in validation suite
- No offline support
- No fallback if tools not installed
- Can't correlate with codebase usage

---

### Pattern Decision: Follow Rules Architecture

**Structure:**
```python
theauditor/
├── vulnerability/                    # NEW PACKAGE
│   ├── __init__.py                   # Public API + backward compat
│   ├── scanner.py                    # Main VulnerabilityScanner class
│   ├── sources/                      # Detection sources
│   │   ├── __init__.py
│   │   ├── native_tools.py           # Tier 1: npm audit, pip-audit
│   │   ├── osv_api.py                # Tier 2: OSV.dev integration
│   │   ├── local_checks.py           # Tier 3: Version/typo checks
│   │   └── usage_analysis.py         # Tier 4: Import correlation
│   ├── database.py                   # Database operations
│   ├── cache.py                      # Memory + disk caching
│   ├── config.py                     # Constants (typo dict, API limits)
│   └── findings.py                   # Finding normalization
```

**Rationale:**
- Mirrors taint package structure (proven pattern)
- Separation of concerns (each tier is a module)
- Testable (mock each tier independently)
- Extensible (add Snyk/GitHub Advisory later)

**Alternative Considered:** Single monolithic file
**Rejected Because:**
- 400+ lines already, would exceed 1000 with new features
- Hard to test tiers independently
- Doesn't follow established package pattern

---

### Database Integration Decision: Dual-Write + Query Pattern

**Read Operations (Database-First):**
```python
# Step 1: Query package_configs table (populated by indexer)
cursor.execute("""
    SELECT file_path, package_name, version, dependencies
    FROM package_configs
""")
packages = cursor.fetchall()

# Step 2: Query lock_analysis table (if available)
cursor.execute("""
    SELECT file_path, total_packages, duplicate_packages
    FROM lock_analysis
""")
locks = cursor.fetchall()

# Step 3: Query import_styles table (usage detection)
cursor.execute("""
    SELECT package, COUNT(*) as usage_count
    FROM import_styles
    GROUP BY package
""")
usage = cursor.fetchall()
```

**Write Operations (Dual-Write Pattern):**
```python
# Write to findings_consolidated table (FCE correlation)
findings_batch = [
    {
        'file': 'package.json',
        'line': 0,  # Dependencies don't have line numbers
        'rule': f'CVE-{vuln_id}',
        'tool': 'vulnerability_scanner',
        'message': vuln['summary'],
        'severity': vuln['severity'],
        'category': 'dependency',
        'confidence': 1.0,
        'cwe': extract_cwe(vuln),
        'code_snippet': f"{pkg_name}@{version}"
    }
    for vuln in vulnerabilities
]
db_manager.write_findings_batch(findings_batch, 'vulnerability_scanner')

# ALSO write to JSON (AI consumption in readthis/)
write_vulnerabilities_json(vulnerabilities, '.pf/raw/vulnerabilities.json')
```

**Rationale:**
- Consistent with pattern detection (writes to findings_consolidated)
- Enables FCE correlation (can detect "outdated package + unused import")
- Supports incremental updates (cache based on package version hash)

**Alternative Considered:** JSON-only (current approach)
**Rejected Because:**
- Findings can't be correlated by FCE
- Can't query "show all critical findings" across tools
- Doesn't match v1.1 architecture

---

### Caching Decision: Multi-Layer Cache Strategy

**Layer 1: Memory Cache (In-Process)**
```python
# Typosquatting dictionary (loaded once per run)
TYPO_DICT = load_typo_dictionary()  # ~1000 entries, <100KB

# OSV.dev responses (TTL: current run only)
osv_cache = {}  # Reset each run, prevents stale data
```

**Layer 2: Disk Cache (Persistent)**
```python
# OSV.dev responses (24-hour TTL)
.pf/vuln_cache/
├── osv_npm_lodash_4.17.11.json      # Cached API response
├── osv_pypi_requests_2.25.0.json
└── cache_index.json                  # Metadata: timestamp, TTL

# Native tool results (hash-based)
.pf/vuln_cache/
└── npm_audit_hash_abc123.json       # Cache key: node_modules hash
```

**Cache Invalidation:**
```python
# OSV.dev: 24-hour TTL (vulnerabilities don't change rapidly)
if cache_age > timedelta(hours=24):
    fetch_fresh()

# Native tools: hash-based (invalidate if package.json changed)
current_hash = hash_file('package.json')
if current_hash != cached_hash:
    run_npm_audit()
```

**Rationale:**
- OSV.dev has rate limits (1000 req/hour), caching is mandatory
- npm audit is slow (~10-30s), caching improves UX
- 24-hour TTL balances freshness vs performance
- Memory cache prevents disk I/O in hot paths

**Alternative Considered:** No caching (current approach)
**Rejected Because:**
- OSV.dev rate limits would block analysis
- Repeated runs take 30+ seconds each
- Network failures cause complete failure

---

### Error Handling Decision: Graceful Degradation

**Failure Modes:**
```python
# Tier 1 failure: npm audit not available
if not npm_available:
    logger.warning("npm audit unavailable, falling back to OSV.dev")
    use_tier2 = True
else:
    use_tier1 = True

# Tier 2 failure: OSV.dev API down
try:
    response = requests.post(OSV_API, ...)
except (RequestException, Timeout):
    logger.warning("OSV.dev unavailable, using local checks only")
    use_tier3_only = True

# Tier 3: Always works (no external dependencies)
local_findings = check_versions(packages)
local_findings.extend(check_typosquatting(packages))

# Result: At least some findings, never zero if issues exist
```

**Rationale:**
- Current implementation: Any failure = 0 findings
- New implementation: Tier 3 always runs (offline-safe)
- Degraded results > No results

**Alternative Considered:** Fail-fast on any error
**Rejected Because:**
- Offline mode would be unusable
- Network issues would block entire pipeline
- Users expect partial results over complete failure

---

## Phase 3: Detailed Implementation Plan

### Module 1: `vulnerability/scanner.py` (Core Orchestrator)

**Responsibility:** Coordinate all detection tiers, manage database operations

**Key Methods:**
```python
class VulnerabilityScanner:
    def __init__(self, db_path: str, offline: bool = False):
        """Initialize scanner with database connection."""
        self.db = VulnerabilityDatabase(db_path)
        self.cache = VulnerabilityCache('.pf/vuln_cache')
        self.offline = offline

    def scan_all(self) -> List[Finding]:
        """Main entry point - orchestrate all tiers."""
        # Step 1: Read packages from database
        packages = self.db.get_packages_from_configs()
        if not packages:
            return []

        # Step 2: Check cache (skip unchanged packages)
        uncached_packages = self.cache.filter_cached(packages)

        # Step 3: Run detection tiers
        findings = []
        if not self.offline:
            findings.extend(self._tier1_native_tools(packages))
            findings.extend(self._tier2_osv_api(uncached_packages))
        findings.extend(self._tier3_local_checks(packages))
        findings.extend(self._tier4_usage_analysis(packages))

        # Step 4: Deduplicate (same CVE from multiple sources)
        findings = self._deduplicate(findings)

        # Step 5: Dual-write (database + JSON)
        self.db.write_findings(findings)
        self._write_json(findings)

        return findings

    def _tier1_native_tools(self, packages):
        """Run npm audit and pip-audit."""
        from .sources.native_tools import run_native_scanners
        return run_native_scanners(packages, cache=self.cache)

    def _tier2_osv_api(self, packages):
        """Query OSV.dev for vulnerabilities."""
        from .sources.osv_api import query_osv_batch
        return query_osv_batch(packages, cache=self.cache)

    def _tier3_local_checks(self, packages):
        """Version comparison and typosquatting detection."""
        from .sources.local_checks import check_versions, check_typosquatting
        findings = check_versions(packages)
        findings.extend(check_typosquatting(packages))
        return findings

    def _tier4_usage_analysis(self, packages):
        """Cross-reference with actual imports."""
        from .sources.usage_analysis import analyze_usage
        return analyze_usage(packages, self.db)
```

**Testing Strategy:**
```python
# Unit tests (mock each tier)
def test_tier1_native_tools_unavailable():
    scanner = VulnerabilityScanner(db_path, offline=False)
    with mock.patch('shutil.which', return_value=None):
        findings = scanner._tier1_native_tools([])
        assert findings == []  # Graceful degradation

def test_tier2_osv_api_network_error():
    scanner = VulnerabilityScanner(db_path, offline=False)
    with mock.patch('requests.post', side_effect=RequestException):
        findings = scanner._tier2_osv_api([{'name': 'lodash', 'version': '4.17.11'}])
        assert findings == []  # Graceful degradation

def test_tier3_always_works():
    scanner = VulnerabilityScanner(db_path, offline=True)
    packages = [{'name': 'requets', 'version': '0.0.001', 'manager': 'py'}]
    findings = scanner._tier3_local_checks(packages)
    assert len(findings) == 2  # Typo + suspicious version
```

---

### Module 2: `vulnerability/sources/osv_api.py` (OSV.dev Integration)

**Responsibility:** Query OSV.dev, handle rate limits, cache responses

**Key Functions:**
```python
def query_osv_batch(packages: List[Dict], cache: VulnerabilityCache) -> List[Finding]:
    """Query OSV.dev API with batching and caching.

    OSV.dev Rate Limits:
    - 1000 requests/hour per IP
    - Batch queries supported (max 10 packages per request)

    Strategy:
    - Check cache first (24-hour TTL)
    - Batch uncached queries (10 per request)
    - Parallel requests (max 5 concurrent)
    """
    findings = []

    # Group by ecosystem for efficient batching
    npm_packages = [p for p in packages if p['manager'] == 'npm']
    pypi_packages = [p for p in packages if p['manager'] == 'py']

    # Check cache
    npm_uncached = [p for p in npm_packages if not cache.has_osv_result(p)]
    pypi_uncached = [p for p in pypi_packages if not cache.has_osv_result(p)]

    # Batch query OSV.dev
    with ThreadPoolExecutor(max_workers=5) as executor:
        npm_futures = [
            executor.submit(_query_osv_batch_single, batch, 'npm')
            for batch in chunk_list(npm_uncached, 10)
        ]
        pypi_futures = [
            executor.submit(_query_osv_batch_single, batch, 'PyPI')
            for batch in chunk_list(pypi_uncached, 10)
        ]

        # Collect results
        for future in as_completed(npm_futures + pypi_futures):
            try:
                batch_findings = future.result(timeout=30)
                findings.extend(batch_findings)

                # Cache responses
                for finding in batch_findings:
                    cache.store_osv_result(finding)
            except (Timeout, RequestException) as e:
                logger.warning(f"OSV.dev query failed: {e}")
                # Continue with other batches

    return findings

def _query_osv_batch_single(packages: List[Dict], ecosystem: str) -> List[Finding]:
    """Query OSV.dev for a single batch of packages."""
    url = "https://api.osv.dev/v1/querybatch"

    # Build batch query
    queries = [
        {
            "package": {"name": p['name'], "ecosystem": ecosystem},
            "version": p['version']
        }
        for p in packages
    ]

    response = requests.post(url, json={"queries": queries}, timeout=30)
    response.raise_for_status()

    # Parse response
    findings = []
    for i, result in enumerate(response.json()['results']):
        if result.get('vulns'):
            for vuln in result['vulns']:
                findings.append(Finding(
                    package=packages[i]['name'],
                    version=packages[i]['version'],
                    vulnerability_id=vuln['id'],
                    severity=_extract_severity(vuln),
                    summary=vuln.get('summary', ''),
                    source='OSV.dev',
                    cwe=_extract_cwe(vuln),
                    cvss_score=_extract_cvss(vuln)
                ))

    return findings
```

**Error Handling:**
```python
# Rate limit handling (429 response)
if response.status_code == 429:
    retry_after = int(response.headers.get('Retry-After', 60))
    logger.warning(f"OSV.dev rate limit, retrying after {retry_after}s")
    time.sleep(retry_after)
    return _query_osv_batch_single(packages, ecosystem)  # Retry

# Network errors (use cached data if available)
except RequestException as e:
    logger.warning(f"OSV.dev network error: {e}, using cached data")
    return [cache.get_osv_result(p) for p in packages if cache.has_osv_result(p)]
```

---

### Module 3: `vulnerability/sources/local_checks.py` (Offline Analysis)

**Responsibility:** Version comparison, typosquatting, suspicious patterns

**Key Functions:**
```python
def check_versions(packages: List[Dict]) -> List[Finding]:
    """Detect suspicious and outdated versions.

    Detection Rules:
    1. Version = "0.0.001" → CRITICAL (placeholder/typo)
    2. Version = "latest" → HIGH (non-deterministic)
    3. Version = "*" → HIGH (non-deterministic)
    4. Major version gap > 2 → MEDIUM (very outdated)
    """
    findings = []

    for pkg in packages:
        version = pkg['version']

        # Suspicious version patterns
        if version in ['0.0.001', '0.0.0', 'latest', '*', 'unknown']:
            findings.append(Finding(
                package=pkg['name'],
                version=version,
                vulnerability_id=f"SUSPICIOUS_VERSION_{pkg['name']}",
                severity='critical' if version == '0.0.001' else 'high',
                summary=f"Suspicious version '{version}' detected",
                source='local_check',
                category='dependency',
                recommendation="Specify exact version number"
            ))

    return findings

def check_typosquatting(packages: List[Dict]) -> List[Finding]:
    """Detect common package name typos.

    Typosquatting Database:
    - Top 100 PyPI packages (requests, numpy, pandas, etc.)
    - Top 100 npm packages (react, lodash, axios, etc.)
    - Common misspellings (requets → requests, loadsh → lodash)
    """
    findings = []

    # Load typo dictionary (cached in memory)
    typo_dict = load_typo_dictionary()

    for pkg in packages:
        name = pkg['name']
        manager = pkg['manager']

        # Check if typo
        if (manager, name) in typo_dict:
            correct_name = typo_dict[(manager, name)]
            findings.append(Finding(
                package=name,
                version=pkg['version'],
                vulnerability_id=f"TYPOSQUATTING_{name}",
                severity='critical',
                summary=f"Possible typosquatting: '{name}' should be '{correct_name}'",
                source='local_check',
                category='typosquatting',
                recommendation=f"Replace '{name}' with '{correct_name}'"
            ))

    return findings

def load_typo_dictionary() -> Dict[Tuple[str, str], str]:
    """Load typosquatting dictionary from config."""
    from ..config import KNOWN_TYPOS_NPM, KNOWN_TYPOS_PYPI

    typo_dict = {}

    # npm typos
    for typo, correct in KNOWN_TYPOS_NPM.items():
        typo_dict[('npm', typo)] = correct

    # PyPI typos (case-sensitive)
    for typo, correct in KNOWN_TYPOS_PYPI.items():
        typo_dict[('py', typo)] = correct

    return typo_dict
```

---

### Module 4: `vulnerability/sources/usage_analysis.py` (Import Correlation)

**Responsibility:** Cross-reference dependencies with actual imports

**Key Functions:**
```python
def analyze_usage(packages: List[Dict], db: VulnerabilityDatabase) -> List[Finding]:
    """Detect unused dependencies and boost severity for used packages.

    Algorithm:
    1. Query import_styles table for all imports
    2. Match imports to declared dependencies
    3. Flag dependencies with 0 imports as unused
    4. Boost vulnerability severity if package is actively used
    """
    findings = []

    # Get actual imports from codebase
    imports = db.get_all_imports()  # Query import_styles table
    import_counts = Counter(imp['package'] for imp in imports)

    # Check each dependency
    for pkg in packages:
        name = pkg['name']
        usage_count = import_counts.get(name, 0)

        # Unused dependency (declared but never imported)
        if usage_count == 0:
            findings.append(Finding(
                package=name,
                version=pkg['version'],
                vulnerability_id=f"UNUSED_DEPENDENCY_{name}",
                severity='low',
                summary=f"Dependency '{name}' is declared but never imported",
                source='usage_analysis',
                category='unused_dependency',
                recommendation=f"Remove '{name}' from dependencies"
            ))

    return findings

def boost_severity_if_used(finding: Finding, usage_count: int) -> Finding:
    """Increase vulnerability severity if package is actively used.

    Rationale:
    - Unused package with CVE: LOW impact (not in attack surface)
    - Heavily used package with CVE: CRITICAL impact (high exposure)
    """
    if usage_count == 0:
        # Downgrade severity for unused packages
        severity_map = {'critical': 'high', 'high': 'medium', 'medium': 'low'}
        finding.severity = severity_map.get(finding.severity, finding.severity)
        finding.summary += f" (UNUSED - lower risk)"
    elif usage_count > 10:
        # Upgrade severity for heavily used packages
        severity_map = {'high': 'critical', 'medium': 'high', 'low': 'medium'}
        finding.severity = severity_map.get(finding.severity, finding.severity)
        finding.summary += f" (USED {usage_count}x - higher risk)"

    return finding
```

---

### Module 5: `vulnerability/database.py` (Database Operations)

**Responsibility:** Query package_configs, write to findings_consolidated

**Key Methods:**
```python
class VulnerabilityDatabase:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def get_packages_from_configs(self) -> List[Dict]:
        """Read packages from package_configs table (populated by indexer).

        Returns:
            List of dicts: [{'name': 'lodash', 'version': '4.17.11', 'manager': 'npm', 'file': 'package.json'}]
        """
        self.cursor.execute("""
            SELECT file_path, package_name, version, dependencies, dev_dependencies
            FROM package_configs
        """)

        packages = []
        for row in self.cursor.fetchall():
            file_path, name, version, deps, dev_deps = row

            # Extract all dependencies from JSON
            if deps:
                deps_dict = json.loads(deps)
                for dep_name, dep_version in deps_dict.items():
                    packages.append({
                        'name': dep_name,
                        'version': dep_version,
                        'manager': self._infer_manager(file_path),
                        'file': file_path,
                        'type': 'production'
                    })

            if dev_deps:
                dev_dict = json.loads(dev_deps)
                for dep_name, dep_version in dev_dict.items():
                    packages.append({
                        'name': dep_name,
                        'version': dep_version,
                        'manager': self._infer_manager(file_path),
                        'file': file_path,
                        'type': 'development'
                    })

        return packages

    def get_all_imports(self) -> List[Dict]:
        """Query import_styles table for actual usage."""
        self.cursor.execute("""
            SELECT package, COUNT(*) as count
            FROM import_styles
            GROUP BY package
        """)
        return [{'package': row[0], 'count': row[1]} for row in self.cursor.fetchall()]

    def write_findings(self, findings: List[Finding]):
        """Dual-write: findings_consolidated table + JSON file.

        Follows pattern from pattern detection (theauditor/rules/orchestrator.py).
        """
        if not findings:
            return

        from datetime import datetime, UTC

        # Convert to findings_consolidated format
        findings_batch = []
        for finding in findings:
            findings_batch.append({
                'file': finding.file or 'package.json',
                'line': 0,  # Dependencies don't have line numbers
                'column': None,
                'rule': finding.vulnerability_id,
                'tool': 'vulnerability_scanner',
                'message': finding.summary,
                'severity': finding.severity,
                'category': finding.category or 'dependency',
                'confidence': finding.confidence or 1.0,
                'code_snippet': f"{finding.package}@{finding.version}",
                'cwe': finding.cwe,
                'timestamp': datetime.now(UTC).isoformat()
            })

        # Batch insert
        self.cursor.executemany(
            """INSERT INTO findings_consolidated
               (file, line, column, rule, tool, message, severity, category,
                confidence, code_snippet, cwe, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (f['file'], f['line'], f['column'], f['rule'], f['tool'],
                 f['message'], f['severity'], f['category'], f['confidence'],
                 f['code_snippet'], f['cwe'], f['timestamp'])
                for f in findings_batch
            ]
        )
        self.conn.commit()

    def _infer_manager(self, file_path: str) -> str:
        """Infer package manager from file path."""
        if 'package.json' in file_path:
            return 'npm'
        elif 'requirements.txt' in file_path or 'pyproject.toml' in file_path:
            return 'py'
        else:
            return 'unknown'
```

---

### Module 6: `vulnerability/cache.py` (Caching Strategy)

**Responsibility:** Memory + disk cache for OSV.dev, native tools

**Key Methods:**
```python
class VulnerabilityCache:
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache (current run only)
        self.memory_cache = {}

        # Load cache index
        self.index = self._load_index()

    def has_osv_result(self, package: Dict) -> bool:
        """Check if OSV.dev result is cached and fresh."""
        cache_key = f"osv_{package['manager']}_{package['name']}_{package['version']}"

        # Check memory first
        if cache_key in self.memory_cache:
            return True

        # Check disk
        if cache_key in self.index:
            cache_entry = self.index[cache_key]
            cache_age = datetime.now(UTC) - datetime.fromisoformat(cache_entry['timestamp'])

            # 24-hour TTL
            if cache_age < timedelta(hours=24):
                return True
            else:
                # Expired, remove from index
                del self.index[cache_key]
                self._save_index()

        return False

    def get_osv_result(self, package: Dict) -> Optional[Finding]:
        """Retrieve cached OSV.dev result."""
        cache_key = f"osv_{package['manager']}_{package['name']}_{package['version']}"

        # Check memory
        if cache_key in self.memory_cache:
            return self.memory_cache[cache_key]

        # Check disk
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                data = json.load(f)
                finding = Finding(**data)

                # Store in memory for this run
                self.memory_cache[cache_key] = finding
                return finding

        return None

    def store_osv_result(self, finding: Finding):
        """Cache OSV.dev result (memory + disk)."""
        cache_key = f"osv_{finding.package['manager']}_{finding.package}_{finding.version}"

        # Memory cache
        self.memory_cache[cache_key] = finding

        # Disk cache
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, 'w') as f:
            json.dump(finding.to_dict(), f, indent=2)

        # Update index
        self.index[cache_key] = {
            'timestamp': datetime.now(UTC).isoformat(),
            'file': str(cache_file)
        }
        self._save_index()

    def _load_index(self) -> Dict:
        """Load cache index from disk."""
        index_file = self.cache_dir / 'cache_index.json'
        if index_file.exists():
            with open(index_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_index(self):
        """Save cache index to disk."""
        index_file = self.cache_dir / 'cache_index.json'
        with open(index_file, 'w') as f:
            json.dump(self.index, f, indent=2)
```

---

### Module 7: `vulnerability/config.py` (Constants & Configuration)

**Responsibility:** Typosquatting dictionary, API limits, severity mappings

**Key Constants:**
```python
"""Configuration for vulnerability scanner."""

# OSV.dev API Configuration
OSV_API_URL = "https://api.osv.dev/v1/querybatch"
OSV_RATE_LIMIT = 1000  # requests per hour
OSV_BATCH_SIZE = 10    # packages per request
OSV_CACHE_TTL_HOURS = 24

# Typosquatting Dictionary - Top 100 npm packages
KNOWN_TYPOS_NPM = {
    'reacct': 'react',
    'react.js': 'react',
    'expres': 'express',
    'expresss': 'express',
    'loadsh': 'lodash',
    'lodas': 'lodash',
    'lodash-es': 'lodash',  # Not a typo, but often confused
    'axios': 'axios',  # Correct
    'axois': 'axios',
    'vue': 'vue',  # Correct
    'vuejs': 'vue',
    'vue-js': 'vue',
    # ... expand to 100 packages
}

# Typosquatting Dictionary - Top 100 PyPI packages (CASE SENSITIVE!)
KNOWN_TYPOS_PYPI = {
    'requets': 'requests',
    'reqeusts': 'requests',
    'request': 'requests',
    'beatifulsoup': 'beautifulsoup4',
    'beautifulsop': 'beautifulsoup4',
    'numpy': 'numpy',  # Correct
    'numpi': 'numpy',
    'pandas': 'pandas',  # Correct
    'panda': 'pandas',
    'flask': 'flask',  # Correct
    'falsk': 'flask',
    'django': 'django',  # Correct
    'jango': 'django',
    # ... expand to 100 packages
}

# Suspicious Version Patterns
SUSPICIOUS_VERSIONS = {
    '0.0.001': 'critical',  # Likely placeholder/typo
    '0.0.0': 'critical',
    'latest': 'high',       # Non-deterministic
    '*': 'high',            # Non-deterministic
    'unknown': 'medium',    # Parsing failure
}

# CVSS Score to Severity Mapping
CVSS_SEVERITY_MAP = {
    (9.0, 10.0): 'critical',
    (7.0, 8.9): 'high',
    (4.0, 6.9): 'medium',
    (0.1, 3.9): 'low',
}

# Native Tool Paths (sandboxed)
NPM_AUDIT_PATH = ".auditor_venv/.theauditor_tools/node-runtime"
PIP_AUDIT_BIN = "pip-audit"  # System-wide or venv
```

---

## Phase 4: Integration with Existing Systems

### Integration Point 1: Pipeline Orchestrator

**Location:** `theauditor/pipelines.py`

**Current State:**
```python
# Line 287-295: Dependency checking in Track C (Network I/O)
if not offline and deps_list:
    run_dependency_checks(deps_list, pf_dir, project_path, allow_net=True, offline=offline)
    deps_end = time.time()
    print(f"   └─ deps: {deps_end - deps_start:.1f}s")
else:
    print(f"   └─ deps: skipped (offline mode)")
```

**Required Changes:**
```python
# Add vulnerability scanning after dependency checking
if not offline and deps_list:
    # Existing deps check
    run_dependency_checks(deps_list, pf_dir, project_path, allow_net=True, offline=offline)
    deps_end = time.time()
    print(f"   └─ deps: {deps_end - deps_start:.1f}s")

    # NEW: Vulnerability scanning
    vuln_start = time.time()
    from theauditor.vulnerability import scan_vulnerabilities
    scan_vulnerabilities(db_path=str(pf_dir / 'repo_index.db'), offline=offline)
    vuln_end = time.time()
    print(f"   └─ vulnerability scan: {vuln_end - vuln_start:.1f}s")
else:
    print(f"   └─ deps: skipped (offline mode)")
    # NEW: Offline vulnerability scan (local checks only)
    vuln_start = time.time()
    from theauditor.vulnerability import scan_vulnerabilities
    scan_vulnerabilities(db_path=str(pf_dir / 'repo_index.db'), offline=True)
    vuln_end = time.time()
    print(f"   └─ vulnerability scan (offline): {vuln_end - vuln_start:.1f}s")
```

**Testing:**
```bash
# Test offline mode (should use Tier 3 + Tier 4 only)
aud full --offline

# Test online mode (should use all tiers)
aud full

# Verify findings in database
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM findings_consolidated WHERE tool='vulnerability_scanner'"
```

---

### Integration Point 2: FCE Correlation Rules

**Location:** `theauditor/correlations/rules/`

**New Correlation Rule: Unused Vulnerable Dependencies**
```python
# theauditor/correlations/rules/unused_vulnerable_deps.py

"""Correlation Rule: Detect unused dependencies with vulnerabilities.

Risk Reasoning:
- Unused dependency with CVE = Low immediate risk (not in attack surface)
- But indicates poor dependency hygiene
- Attack surface could expand if code changes use the package
"""

from theauditor.correlations.base import CorrelationRule, CorrelationFinding

class UnusedVulnerableDependencies(CorrelationRule):
    name = "unused_vulnerable_dependencies"
    category = "dependency_hygiene"

    def analyze(self, db_path: str) -> List[CorrelationFinding]:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Find vulnerabilities in unused dependencies
        cursor.execute("""
            SELECT
                f.rule as cve,
                f.code_snippet as package_version,
                f.severity,
                f.message
            FROM findings_consolidated f
            WHERE f.tool = 'vulnerability_scanner'
              AND f.rule LIKE 'CVE-%'
              AND f.code_snippet IN (
                  -- Subquery: packages with 0 imports
                  SELECT code_snippet FROM findings_consolidated
                  WHERE tool = 'vulnerability_scanner'
                    AND rule LIKE 'UNUSED_DEPENDENCY_%'
              )
        """)

        findings = []
        for row in cursor.fetchall():
            cve, package, severity, message = row
            findings.append(CorrelationFinding(
                title=f"Unused dependency has vulnerability: {package}",
                severity='low',  # Downgraded because unused
                category='dependency_hygiene',
                evidence=[
                    f"Package: {package}",
                    f"CVE: {cve}",
                    f"Original Severity: {severity}",
                    f"Risk: LOW (package not imported in codebase)"
                ],
                recommendation=f"Remove {package} from dependencies to eliminate attack surface"
            ))

        return findings
```

---

### Integration Point 3: Extraction for AI Consumption

**Location:** `theauditor/commands/extract_chunks.py`

**Add vulnerability findings to extraction:**
```python
# Extract vulnerability findings from findings_consolidated
findings_to_extract = [
    'vulnerabilities',  # NEW: Add to extraction list
    'patterns',
    'taint_analysis',
    'lint',
    # ... other sources
]

def extract_vulnerabilities(db_path: str, readthis_dir: Path, budget_kb: int):
    """Extract vulnerability findings from database.

    Strategy:
    - Group by severity (critical first)
    - Group by category (CVE vs typosquatting vs unused)
    - Sample if > 1000 findings
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, line, rule, severity, message, category, code_snippet
        FROM findings_consolidated
        WHERE tool = 'vulnerability_scanner'
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 0
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
            END,
            category
    """)

    findings = [
        {
            'file': row[0],
            'line': row[1],
            'rule': row[2],
            'severity': row[3],
            'message': row[4],
            'category': row[5],
            'package': row[6]
        }
        for row in cursor.fetchall()
    ]

    # Sample if too large (use categorical sampling from findings.md)
    if len(findings) > 1000:
        findings = sample_by_severity(findings, max_count=1000)

    # Write to readthis/
    output_file = readthis_dir / 'vulnerabilities.json'
    with open(output_file, 'w') as f:
        json.dump({
            'findings': findings,
            'metadata': {
                'total': len(findings),
                'sampled': len(findings) > 1000,
                'by_severity': count_by_severity(findings),
                'by_category': count_by_category(findings)
            }
        }, f, indent=2)
```

---

## Phase 5: Testing Strategy

### Unit Tests

**Test Coverage:**
```python
# tests/test_vulnerability_scanner.py

class TestVulnerabilityScanner:
    """Test suite for vulnerability scanner."""

    def test_tier1_npm_audit_success(self, mock_subprocess):
        """Test successful npm audit execution."""
        mock_subprocess.return_value.stdout = '{"vulnerabilities": {...}}'
        scanner = VulnerabilityScanner(db_path)
        findings = scanner._tier1_native_tools([{'name': 'lodash', 'manager': 'npm'}])
        assert len(findings) > 0

    def test_tier1_npm_audit_unavailable(self, mock_subprocess):
        """Test graceful degradation when npm audit unavailable."""
        mock_subprocess.side_effect = FileNotFoundError
        scanner = VulnerabilityScanner(db_path)
        findings = scanner._tier1_native_tools([{'name': 'lodash', 'manager': 'npm'}])
        assert findings == []  # No crash, empty results

    def test_tier2_osv_api_success(self, mock_requests):
        """Test successful OSV.dev query."""
        mock_requests.post.return_value.json.return_value = {
            'results': [{'vulns': [{'id': 'CVE-2021-23337', 'severity': 'HIGH'}]}]
        }
        scanner = VulnerabilityScanner(db_path)
        findings = scanner._tier2_osv_api([{'name': 'lodash', 'version': '4.17.11', 'manager': 'npm'}])
        assert len(findings) == 1
        assert findings[0].vulnerability_id == 'CVE-2021-23337'

    def test_tier2_osv_api_rate_limit(self, mock_requests):
        """Test OSV.dev rate limit handling."""
        mock_requests.post.return_value.status_code = 429
        mock_requests.post.return_value.headers = {'Retry-After': '60'}
        scanner = VulnerabilityScanner(db_path)
        findings = scanner._tier2_osv_api([{'name': 'lodash', 'version': '4.17.11', 'manager': 'npm'}])
        # Should retry or use cache
        assert findings is not None

    def test_tier3_typosquatting_detection(self):
        """Test typosquatting detection."""
        scanner = VulnerabilityScanner(db_path, offline=True)
        findings = scanner._tier3_local_checks([
            {'name': 'requets', 'version': '2.25.0', 'manager': 'py'}
        ])
        assert len(findings) == 1
        assert 'typosquatting' in findings[0].summary.lower()
        assert findings[0].severity == 'critical'

    def test_tier3_suspicious_version(self):
        """Test suspicious version detection."""
        scanner = VulnerabilityScanner(db_path, offline=True)
        findings = scanner._tier3_local_checks([
            {'name': 'some-package', 'version': '0.0.001', 'manager': 'npm'}
        ])
        assert len(findings) == 1
        assert 'suspicious version' in findings[0].summary.lower()
        assert findings[0].severity == 'critical'

    def test_tier4_unused_dependency(self):
        """Test unused dependency detection."""
        # Setup: Mock database with package but no imports
        db = VulnerabilityDatabase(db_path)
        db.mock_packages([{'name': 'unused-package', 'version': '1.0.0'}])
        db.mock_imports([])  # No imports

        scanner = VulnerabilityScanner(db_path)
        findings = scanner._tier4_usage_analysis([{'name': 'unused-package', 'version': '1.0.0'}])
        assert len(findings) == 1
        assert 'unused' in findings[0].summary.lower()

    def test_deduplication(self):
        """Test finding deduplication (same CVE from multiple sources)."""
        findings = [
            Finding(package='lodash', vulnerability_id='CVE-2021-23337', source='npm audit'),
            Finding(package='lodash', vulnerability_id='CVE-2021-23337', source='OSV.dev'),
        ]
        scanner = VulnerabilityScanner(db_path)
        deduplicated = scanner._deduplicate(findings)
        assert len(deduplicated) == 1
        assert 'npm audit, OSV.dev' in deduplicated[0].source  # Combined sources

    def test_database_write(self):
        """Test dual-write to database and JSON."""
        scanner = VulnerabilityScanner(db_path)
        findings = [Finding(package='lodash', vulnerability_id='CVE-2021-23337', severity='high')]
        scanner.scan_all()  # Writes findings

        # Verify database write
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM findings_consolidated WHERE tool='vulnerability_scanner'")
        assert cursor.fetchone()[0] == 1

        # Verify JSON write
        assert Path('.pf/raw/vulnerabilities.json').exists()

    def test_offline_mode(self):
        """Test offline mode uses only local checks."""
        scanner = VulnerabilityScanner(db_path, offline=True)
        with mock.patch.object(scanner, '_tier1_native_tools') as mock_tier1, \
             mock.patch.object(scanner, '_tier2_osv_api') as mock_tier2:

            scanner.scan_all()

            # Tier 1 and 2 should not be called in offline mode
            mock_tier1.assert_not_called()
            mock_tier2.assert_not_called()
```

---

### Integration Tests

**Test Against Validation Suite:**
```bash
#!/bin/bash
# tests/integration/test_vulnerability_scanner.sh

# Test on project_anarchy (403 known errors, 21 dependency issues)
cd fakeproj/project_anarchy

# Run full pipeline
aud full

# Verify detection rate
python3 << EOF
import sqlite3
import json

conn = sqlite3.connect('.pf/repo_index.db')
cursor = conn.cursor()

# Count vulnerability findings
cursor.execute("""
    SELECT COUNT(*) FROM findings_consolidated
    WHERE tool='vulnerability_scanner'
""")
vuln_count = cursor.fetchone()[0]

print(f"Vulnerabilities detected: {vuln_count}")

# Expected: At least 15 findings (from error_count.md)
# - 15 outdated packages
# - 1 typosquatting (requets)
# - Multiple CVEs if npm audit/OSV.dev work
assert vuln_count >= 15, f"Expected ≥15 findings, got {vuln_count}"

# Verify typosquatting detection
cursor.execute("""
    SELECT rule FROM findings_consolidated
    WHERE tool='vulnerability_scanner' AND rule LIKE 'TYPOSQUATTING_%'
""")
typos = cursor.fetchall()
assert len(typos) >= 1, "Expected typosquatting detection"

print("✓ Vulnerability scanner integration test passed")
EOF
```

---

## Phase 6: Performance Analysis

### Baseline Performance (Current subprocess-only approach)
```
npm audit (300 packages):        ~15-30s
pip-audit (50 packages):         ~5-10s
Total:                            ~20-40s
Parallelization:                  None (sequential)
Caching:                          None
```

### Expected Performance (New multi-tier approach)

**First Run (Cold Cache):**
```
Tier 1 (Native Tools):            ~20s (parallel: npm + pip)
Tier 2 (OSV.dev):                 ~10s (batched, 30 packages/sec)
Tier 3 (Local Checks):            ~0.1s (in-memory)
Tier 4 (Usage Analysis):          ~0.5s (database query)
Total First Run:                  ~30s
```

**Subsequent Runs (Warm Cache):**
```
Tier 1 (Native Tools):            ~0s (cache hit, package.json unchanged)
Tier 2 (OSV.dev):                 ~0s (cache hit, <24h old)
Tier 3 (Local Checks):            ~0.1s
Tier 4 (Usage Analysis):          ~0.5s
Total Warm Cache:                 ~0.6s (50x faster!)
```

**Memory Usage:**
```
Typosquatting Dictionary:         ~100KB (200 entries × 500B avg)
OSV.dev Cache (100 packages):     ~500KB (5KB per response)
Memory Cache Objects:             ~1MB peak
Total Memory Overhead:            ~1.6MB (negligible)
```

---

## Phase 7: Rollout Plan

### Stage 1: Core Implementation (Hours 1-4)
1. Create `theauditor/vulnerability/` package structure
2. Implement `scanner.py` orchestrator (Tier coordination)
3. Implement `database.py` (read package_configs, write findings_consolidated)
4. Implement `config.py` (typosquatting dictionary, constants)
5. Write unit tests for database operations

**Deliverable:** Scanner can read packages from database, write findings to database

---

### Stage 2: Detection Tiers (Hours 5-8)
1. Implement `sources/native_tools.py` (Tier 1: npm audit, pip-audit)
2. Implement `sources/osv_api.py` (Tier 2: OSV.dev with batching)
3. Implement `sources/local_checks.py` (Tier 3: typosquatting, version checks)
4. Implement `sources/usage_analysis.py` (Tier 4: import correlation)
5. Write unit tests for each tier

**Deliverable:** All detection tiers functional, tested independently

---

### Stage 3: Caching & Performance (Hours 9-10)
1. Implement `cache.py` (memory + disk cache)
2. Add cache integration to OSV.dev tier
3. Add hash-based caching to native tools tier
4. Benchmark performance (first run vs warm cache)

**Deliverable:** 50x performance improvement on warm cache

---

### Stage 4: Integration & Testing (Hours 11-12)
1. Integrate with `pipelines.py` (add vulnerability scan phase)
2. Add extraction to `extract_chunks.py` (readthis/ output)
3. Add FCE correlation rule (unused vulnerable dependencies)
4. Run integration tests on all 4 validation projects
5. Verify findings in database and readthis/

**Deliverable:** End-to-end pipeline working, validation suite passing

---

## Phase 8: Success Criteria

### Functional Requirements
- [ ] Scanner reads packages from `package_configs` table
- [ ] Scanner writes findings to `findings_consolidated` table
- [ ] Scanner writes JSON to `.pf/raw/vulnerabilities.json`
- [ ] All 4 detection tiers functional
- [ ] Offline mode works (Tier 3 + Tier 4 only)
- [ ] Caching improves performance by 50x
- [ ] Graceful degradation if native tools unavailable

### Detection Requirements
- [ ] project_anarchy: Detect ≥15 dependency issues (from error_count.md)
- [ ] Typosquatting: Detect `requets` → `requests`
- [ ] Suspicious versions: Detect `0.0.001`
- [ ] CVE detection: Find lodash CVE-2021-23337 if present
- [ ] Unused dependencies: Flag packages with 0 imports

### Integration Requirements
- [ ] Pipeline phase "vulnerability scan" completes without error
- [ ] FCE can correlate findings (unused vulnerable deps)
- [ ] Findings appear in readthis/ directory
- [ ] Database queries work (SELECT * FROM findings_consolidated WHERE tool='vulnerability_scanner')

### Performance Requirements
- [ ] First run: ≤30 seconds (300 packages)
- [ ] Warm cache: ≤1 second
- [ ] Memory usage: ≤2MB overhead
- [ ] OSV.dev: ≤1000 requests/hour (rate limit compliance)

---

## Phase 9: Risk Analysis & Mitigation

### Risk 1: OSV.dev Rate Limiting
**Probability:** MEDIUM
**Impact:** HIGH (blocks all scanning if hit)

**Mitigation:**
- Implement 24-hour cache (reduces requests by 95%)
- Batch queries (10 packages per request = 10x reduction)
- Add exponential backoff for 429 responses
- Fallback to Tier 3 if rate limit hit

**Contingency:** If OSV.dev becomes unreliable, add GitHub Advisory API as Tier 2B

---

### Risk 2: Native Tools Not Installed
**Probability:** HIGH (pip-audit not default, sandboxed npm might not exist)
**Impact:** MEDIUM (reduces accuracy, but Tier 2 compensates)

**Mitigation:**
- Check tool availability before running (shutil.which)
- Log warning but don't fail
- Use OSV.dev as primary source (more reliable)

**Contingency:** Document that npm/pip audit are optional enhancements

---

### Risk 3: Database Schema Changes
**Probability:** LOW (schema is stable in v1.1)
**Impact:** HIGH (scanner breaks if package_configs changes)

**Mitigation:**
- Add schema version check (detect if old database)
- Graceful fallback to reading package.json directly
- Unit tests verify expected schema

**Contingency:** Add migration code if schema changes in future

---

### Risk 4: False Positives (Typosquatting)
**Probability:** MEDIUM (dictionary may have errors)
**Impact:** LOW (annoying but not breaking)

**Mitigation:**
- Curate typo dictionary carefully (manual review)
- Add user override config (ignore specific packages)
- Use confidence scores (HIGH for npm/OSV, MEDIUM for typos)

**Contingency:** Allow `.theauditor_ignore` file for false positive suppression

---

## Phase 10: Enhanced Coverage Analysis - Leveraging Rich Database

### Opportunity Assessment: What We Can Detect Now

**Context:** TheAuditor v1.1 database-first architecture provides unprecedented data richness:
- `package_configs`: All declared dependencies with versions
- `lock_analysis`: Lock file integrity, duplicates, conflicts
- `import_styles`: Actual import usage in codebase
- `symbols`: All code symbols (functions, classes, variables)
- `function_call_args`: Every function call with arguments
- `refs`: Import relationships and module dependencies
- `findings_consolidated`: Cross-tool correlation capability

**Current Coverage Gaps:** The old subprocess-only vulnerability scanner only detected:
1. CVEs (via npm audit, pip-audit)
2. Basic version checks

**New Detection Opportunities:** With database integration, we can detect **10 additional categories**:

---

### Enhanced Detection Category 1: Dependency Bloat Analysis

**What It Detects:**
- Packages with massive transitive dependency trees (>50 subdeps)
- Redundant dependencies (multiple packages providing same functionality)
- Heavy packages in frontend bundles (moment.js, lodash-full vs lodash-lite)

**Database Queries:**
```sql
-- Detect packages with large transitive trees
SELECT package_name, COUNT(*) as transitive_count
FROM (
    -- Recursive CTE to traverse dependency tree
    WITH RECURSIVE deps_tree AS (
        SELECT package_name, dependencies
        FROM package_configs
        WHERE package_name = 'target-package'
        UNION ALL
        SELECT pc.package_name, pc.dependencies
        FROM package_configs pc
        JOIN deps_tree dt ON pc.package_name IN (
            SELECT json_each.value FROM json_each(dt.dependencies)
        )
    )
    SELECT * FROM deps_tree
)
GROUP BY package_name
HAVING transitive_count > 50;
```

**Severity Scoring:**
- >100 transitive deps: CRITICAL (maintenance nightmare)
- >50 transitive deps: HIGH (dependency hell risk)
- Duplicate functionality: MEDIUM (bundle bloat)

**Example Finding:**
```json
{
  "rule": "DEPENDENCY_BLOAT_moment",
  "severity": "high",
  "message": "moment.js has 147 transitive dependencies and is 232KB. Consider date-fns (2KB, 0 deps)",
  "category": "dependency_bloat",
  "recommendation": "Replace moment.js with date-fns for 99% size reduction"
}
```

**Estimated Effort:** 2 hours (Tier 5)

---

### Enhanced Detection Category 2: Version Pinning Analysis

**What It Detects:**
- Unpinned versions in production dependencies (`^`, `~`, `*`)
- Semver range violations (^1.0.0 but using 1.2.5)
- Missing lock files (non-deterministic builds)

**Database Queries:**
```sql
-- Find unpinned production dependencies
SELECT package_name, version, file_path
FROM package_configs
WHERE version LIKE '^%' OR version LIKE '~%' OR version = '*'
  AND file_path LIKE '%package.json%'
  AND file_path NOT LIKE '%/test/%';
```

**Risk Reasoning:**
- Production with unpinned versions = non-deterministic builds
- Security patches can introduce breaking changes
- Audit trail requires exact versions

**Severity Scoring:**
- Production unpinned: HIGH
- Development unpinned: LOW (acceptable)
- Missing lock file: CRITICAL

**Example Finding:**
```json
{
  "rule": "UNPINNED_VERSION_express",
  "severity": "high",
  "message": "express version '^4.17.0' is unpinned in production dependencies",
  "category": "version_pinning",
  "recommendation": "Pin to exact version: 'express': '4.17.3'"
}
```

**Estimated Effort:** 1 hour (Tier 5)

---

### Enhanced Detection Category 3: Dependency Freshness & Abandonment

**What It Detects:**
- Last update >2 years ago (abandoned package risk)
- Deprecated packages (marked in npm/PyPI)
- Packages with no maintenance (0 commits in 12 months)

**Data Sources:**
- npm registry API: `GET https://registry.npmjs.org/{package}/latest`
- PyPI JSON API: `GET https://pypi.org/pypi/{package}/json`

**Database Queries:**
```sql
-- Cross-reference with external API data (cached)
SELECT package_name, version, last_updated_days_ago
FROM vulnerability_cache
WHERE cache_type = 'package_metadata'
  AND last_updated_days_ago > 730  -- 2 years
  AND package_name IN (SELECT package_name FROM package_configs);
```

**Risk Reasoning:**
- Abandoned packages won't receive security patches
- Deprecated packages may have known successors
- Stale dependencies indicate technical debt

**Severity Scoring:**
- Abandoned >3 years: HIGH
- Abandoned >2 years: MEDIUM
- Deprecated with successor: MEDIUM

**Example Finding:**
```json
{
  "rule": "ABANDONED_PACKAGE_request",
  "severity": "high",
  "message": "Package 'request' is deprecated (last update: 3.2 years ago). Successor: 'axios'",
  "category": "dependency_freshness",
  "recommendation": "Migrate to 'axios' or 'node-fetch'"
}
```

**Estimated Effort:** 3 hours (Tier 5, requires API integration)

---

### Enhanced Detection Category 4: License Compliance & Compatibility

**What It Detects:**
- GPL contamination (GPL dependency in proprietary codebase)
- License conflicts (MIT + Apache 2.0 compatibility)
- Missing license information (legal risk)
- Copy-left violations (AGPL in SaaS)

**Database Queries:**
```sql
-- Detect GPL packages in proprietary project
SELECT package_name, license
FROM vulnerability_cache
WHERE cache_type = 'package_metadata'
  AND license LIKE '%GPL%'
  AND package_name IN (
      SELECT package_name FROM package_configs
      WHERE file_path LIKE '%package.json%'
  );
```

**License Compatibility Matrix:**
```python
LICENSE_CONFLICTS = {
    ('proprietary', 'GPL-3.0'): 'critical',  # Cannot mix
    ('MIT', 'GPL-3.0'): 'medium',  # Can mix but output is GPL
    ('Apache-2.0', 'GPL-2.0'): 'high',  # Incompatible
    ('MIT', 'Apache-2.0'): None,  # Compatible
}
```

**Severity Scoring:**
- GPL in proprietary: CRITICAL (legal violation)
- AGPL in SaaS: CRITICAL (must open-source)
- License conflict: HIGH
- Missing license: MEDIUM

**Example Finding:**
```json
{
  "rule": "LICENSE_VIOLATION_bcrypt",
  "severity": "critical",
  "message": "GPL-3.0 package 'bcrypt' detected in proprietary codebase",
  "category": "license_compliance",
  "recommendation": "Replace with MIT-licensed 'bcryptjs' or consult legal"
}
```

**Estimated Effort:** 4 hours (Tier 5, requires legal knowledge)

---

### Enhanced Detection Category 5: Peer Dependency Conflicts

**What It Detects:**
- React 17 library used with React 18 project
- Webpack 4 plugin with Webpack 5
- Incompatible TypeScript versions

**Database Queries:**
```sql
-- Detect peer dependency mismatches
SELECT
    p1.package_name as package,
    p1.version as installed_version,
    p2.package_name as peer_package,
    p2.peer_version_required,
    p1.actual_peer_version
FROM package_configs p1
JOIN vulnerability_cache p2 ON p1.package_name = p2.package_name
WHERE p2.cache_type = 'peer_dependencies'
  AND NOT version_satisfies(p1.actual_peer_version, p2.peer_version_required);
```

**Risk Reasoning:**
- Peer dependency violations cause runtime errors
- May work in development but fail in production
- Hard to debug (no clear error message)

**Severity Scoring:**
- Major version mismatch (React 17 vs 19): CRITICAL
- Minor version mismatch (React 19.0 vs 19.1): LOW
- Missing peer dep: HIGH

**Example Finding:**
```json
{
  "rule": "PEER_DEPENDENCY_CONFLICT_react-router-dom",
  "severity": "critical",
  "message": "react-router-dom@6.x requires React ^18.0.0, but project uses React 17.0.2",
  "category": "peer_dependency",
  "recommendation": "Upgrade React to 18.x or downgrade react-router-dom to 5.x"
}
```

**Estimated Effort:** 3 hours (Tier 5, complex version matching)

---

### Enhanced Detection Category 6: Ghost Dependencies (Phantom Imports)

**What It Detects:**
- Importing packages not declared in dependencies (transitive only)
- Code breaks if intermediate dependency removes transitive dep
- Implicit dependencies (using without declaring)

**Database Queries:**
```sql
-- Find imports not in package.json
SELECT DISTINCT i.package
FROM import_styles i
WHERE i.package NOT IN (
    SELECT package_name FROM package_configs
    WHERE file_path LIKE '%package.json%'
)
AND i.package NOT LIKE '@types/%'  -- Exclude type definitions
AND i.package NOT IN ('fs', 'path', 'http')  -- Exclude Node.js built-ins
ORDER BY i.package;
```

**Risk Reasoning:**
- Transitive dependencies can be removed without warning
- Violates explicit dependency principle
- Hidden coupling to package manager implementation

**Severity Scoring:**
- Ghost import in production code: HIGH
- Ghost import in tests: MEDIUM
- Built-in module false positive: Ignore

**Example Finding:**
```json
{
  "rule": "GHOST_DEPENDENCY_express-validator",
  "severity": "high",
  "message": "Code imports 'express-validator' but it's not in package.json (transitive via express-utils)",
  "category": "ghost_dependency",
  "files": ["src/middleware/validation.ts:3", "src/routes/auth.ts:7"],
  "recommendation": "Add 'express-validator' to dependencies explicitly"
}
```

**Estimated Effort:** 2 hours (Tier 4, uses existing import_styles table)

---

### Enhanced Detection Category 7: Dependency Depth & Supply Chain Risk

**What It Detects:**
- Packages with deep transitive chains (>10 levels)
- Single points of failure (1 package used by 50+ others)
- Supply chain attack surface (packages with install scripts)

**Database Queries:**
```sql
-- Calculate dependency depth (recursive)
WITH RECURSIVE dep_depth AS (
    SELECT package_name, 0 as depth
    FROM package_configs
    WHERE file_path LIKE '%package.json%'
    UNION ALL
    SELECT td.package_name, dd.depth + 1
    FROM dep_depth dd
    JOIN transitive_deps td ON dd.package_name = td.parent_package
    WHERE dd.depth < 20  -- Prevent infinite recursion
)
SELECT package_name, MAX(depth) as max_depth
FROM dep_depth
GROUP BY package_name
HAVING max_depth > 10;
```

**Risk Reasoning:**
- Deep chains = more attack surface
- Each level increases compromise risk
- Install scripts can execute arbitrary code

**Severity Scoring:**
- Depth >15: HIGH (supply chain risk)
- Depth >10: MEDIUM
- Install scripts: CRITICAL (if untrusted source)

**Example Finding:**
```json
{
  "rule": "DEEP_DEPENDENCY_CHAIN_babel-loader",
  "severity": "high",
  "message": "babel-loader has dependency depth of 17 levels (attack surface: 143 packages)",
  "category": "supply_chain",
  "recommendation": "Review transitive dependencies, consider webpack alternatives"
}
```

**Estimated Effort:** 4 hours (Tier 6, requires lock file parsing)

---

### Enhanced Detection Category 8: Bundle Size Impact Analysis

**What It Detects:**
- Large packages in frontend projects (>100KB)
- Tree-shaking failures (importing entire library)
- Duplicate modules in bundle (webpack/rollup)

**Database Queries:**
```sql
-- Detect large packages used in frontend
SELECT
    pc.package_name,
    vc.package_size_kb,
    COUNT(DISTINCT is.file) as usage_count
FROM package_configs pc
JOIN vulnerability_cache vc ON pc.package_name = vc.package_name
JOIN import_styles is ON pc.package_name = is.package
WHERE vc.cache_type = 'package_metadata'
  AND vc.package_size_kb > 100
  AND is.file LIKE 'frontend/%'
GROUP BY pc.package_name, vc.package_size_kb;
```

**Risk Reasoning:**
- Large bundles = slow page load
- Affects LCP (Largest Contentful Paint) metric
- User experience degradation on mobile

**Severity Scoring:**
- >500KB package in frontend: CRITICAL
- >200KB package: HIGH
- >100KB package: MEDIUM

**Example Finding:**
```json
{
  "rule": "BUNDLE_SIZE_IMPACT_moment",
  "severity": "critical",
  "message": "moment.js (232KB) used in frontend, impacts bundle by 18% (1.3MB total)",
  "category": "bundle_size",
  "files": ["frontend/src/utils/date.ts", "frontend/src/components/DatePicker.tsx"],
  "recommendation": "Replace with date-fns (2KB) for 99% size reduction"
}
```

**Estimated Effort:** 3 hours (Tier 4, requires webpack stats integration)

---

### Enhanced Detection Category 9: Dependency Update Lag Analysis

**What It Detects:**
- Major versions behind (lodash 3.x when 4.x available for 5 years)
- Security updates not applied (vulnerable version + patch available)
- Breaking change accumulation (skipping too many major versions)

**Database Queries:**
```sql
-- Find packages lagging behind by major versions
SELECT
    pc.package_name,
    pc.version as current_version,
    vc.latest_version,
    vc.major_versions_behind
FROM package_configs pc
JOIN vulnerability_cache vc ON pc.package_name = vc.package_name
WHERE vc.cache_type = 'version_metadata'
  AND vc.major_versions_behind >= 2
ORDER BY vc.major_versions_behind DESC;
```

**Risk Reasoning:**
- Lagging versions accumulate technical debt
- Breaking changes stack up (harder to upgrade)
- Missing performance improvements and features

**Severity Scoring:**
- 5+ major versions behind: CRITICAL
- 3+ major versions behind: HIGH
- 2 major versions behind: MEDIUM

**Example Finding:**
```json
{
  "rule": "UPDATE_LAG_webpack",
  "severity": "critical",
  "message": "webpack version 3.12.0 is 5 major versions behind (current: 5.89.0, age: 6.2 years)",
  "category": "dependency_lag",
  "recommendation": "Plan migration to webpack 5 (breaking changes accumulated)"
}
```

**Estimated Effort:** 2 hours (Tier 5, extends version checking)

---

### Enhanced Detection Category 10: Security Policy Compliance

**What It Detects:**
- Packages failing OWASP Dependency-Check rules
- Packages on known-bad lists (npm malware database)
- Packages with history of CVEs (red flag pattern)
- Maintainer account compromises

**Database Queries:**
```sql
-- Detect packages with CVE history
SELECT
    package_name,
    COUNT(DISTINCT vulnerability_id) as cve_count,
    MAX(published_date) as most_recent_cve
FROM vulnerability_cache
WHERE cache_type = 'historical_cves'
  AND package_name IN (SELECT package_name FROM package_configs)
GROUP BY package_name
HAVING cve_count >= 3  -- 3+ CVEs = pattern
ORDER BY cve_count DESC;
```

**Risk Reasoning:**
- Packages with CVE history are higher risk
- Compromised maintainer accounts can inject malware
- Known-bad lists indicate malicious intent

**Severity Scoring:**
- On malware list: CRITICAL (immediate removal)
- 5+ historical CVEs: HIGH (pattern of issues)
- Compromised maintainer: CRITICAL (supply chain attack)

**Example Finding:**
```json
{
  "rule": "SECURITY_POLICY_event-stream",
  "severity": "critical",
  "message": "Package 'event-stream' has compromised maintainer history (2018 bitcoin theft incident)",
  "category": "security_policy",
  "recommendation": "Remove immediately, use alternative stream library"
}
```

**Estimated Effort:** 4 hours (Tier 5, requires threat intel integration)

---

## Phase 11: Enhanced Detection Implementation Roadmap

### Tier 5 (Local Database + API Enrichment)

**Modules to Add:**
```
theauditor/vulnerability/sources/
├── bloat_analysis.py       (Category 1)
├── pinning_analysis.py     (Category 2)
├── freshness_analysis.py   (Category 3)
├── license_analysis.py     (Category 4)
├── peer_deps_analysis.py   (Category 5)
├── ghost_deps_analysis.py  (Category 6)
├── chain_depth_analysis.py (Category 7)
├── bundle_size_analysis.py (Category 8)
├── update_lag_analysis.py  (Category 9)
└── policy_analysis.py      (Category 10)
```

**API Integrations Required:**
- npm registry API (package metadata, size, last update)
- PyPI JSON API (package metadata, classifiers)
- OSV.dev historical CVE endpoint (CVE history)
- npm malware database (known-bad packages)
- GitHub Advisory Database (security advisories)

**Database Schema Extensions:**
```sql
-- Cache table for enriched metadata
CREATE TABLE IF NOT EXISTS package_metadata_cache (
    package_name TEXT,
    manager TEXT,
    license TEXT,
    size_kb INTEGER,
    last_updated_date TEXT,
    deprecated BOOLEAN,
    successor_package TEXT,
    peer_dependencies TEXT,  -- JSON
    historical_cves TEXT,     -- JSON array
    install_scripts BOOLEAN,
    created_at TEXT,
    PRIMARY KEY (package_name, manager)
);

-- Lock file analysis (enhanced)
CREATE TABLE IF NOT EXISTS lock_file_analysis (
    file_path TEXT,
    package_name TEXT,
    version TEXT,
    depth INTEGER,            -- NEW: dependency depth
    is_dev BOOLEAN,
    is_peer BOOLEAN,          -- NEW: peer dependency flag
    parent_package TEXT,      -- NEW: for graph traversal
    PRIMARY KEY (file_path, package_name)
);
```

---

### Tier 6 (Graph Analysis - Dependency Tree)

**Integration with Graph Module:**
```python
# Extend theauditor/commands/graph.py
def analyze_dependency_graph(db_path: str):
    """Analyze dependency graph for supply chain risks."""
    # Build graph from lock_file_analysis table
    G = nx.DiGraph()

    # Add edges: package -> dependency
    for pkg, dep in cursor.execute("SELECT package_name, parent_package FROM lock_file_analysis"):
        G.add_edge(pkg, dep)

    # Calculate metrics
    depth = nx.dag_longest_path_length(G)  # Deepest chain
    cycles = list(nx.simple_cycles(G))     # Circular dependencies
    critical_packages = [n for n, d in G.in_degree() if d > 50]  # High fan-in

    return {
        'max_depth': depth,
        'circular_dependencies': len(cycles),
        'critical_packages': critical_packages,
        'total_packages': G.number_of_nodes()
    }
```

---

### Priority Matrix for Implementation

| Category | Severity | Effort | Detection Rate | Priority |
|----------|----------|--------|----------------|----------|
| Ghost Dependencies | High | 2h | 90% | **P0** (Easy win) |
| Version Pinning | High | 1h | 95% | **P0** (Easy win) |
| Dependency Bloat | Medium | 2h | 70% | **P1** |
| Update Lag | High | 2h | 90% | **P1** |
| License Compliance | Critical | 4h | 80% | **P1** |
| Peer Dependency Conflicts | Critical | 3h | 60% | **P2** |
| Freshness/Abandonment | Medium | 3h | 70% | **P2** |
| Bundle Size Impact | Medium | 3h | 60% | **P2** |
| Supply Chain Depth | High | 4h | 50% | **P3** |
| Security Policy | Critical | 4h | 40% | **P3** |

**Total Additional Effort:** 28 hours (3-4 days)

---

### Enhanced Coverage ROI Analysis

**Current Detection (4 tiers, 8-12 hours):**
- CVEs: 80-90% (OSV.dev + native tools)
- Typosquatting: 95% (dictionary-based)
- Suspicious versions: 99% (pattern matching)
- Unused dependencies: 85% (import correlation)
- **Total Categories:** 4

**Enhanced Detection (10 additional categories, 28 hours):**
- Ghost dependencies: 90% (database query)
- Version pinning: 95% (regex + policy)
- Dependency bloat: 70% (transitive analysis)
- Update lag: 90% (version comparison)
- License compliance: 80% (API + compatibility matrix)
- Peer dependency conflicts: 60% (version resolution logic)
- Freshness/abandonment: 70% (API + heuristics)
- Bundle size impact: 60% (size API + usage correlation)
- Supply chain depth: 50% (graph traversal)
- Security policy: 40% (threat intel integration)
- **Total Categories:** 14

**ROI Calculation:**
- Effort increase: 28 hours / 12 hours = 2.3x
- Detection categories: 14 / 4 = 3.5x
- Unique findings per project: 50 → 150 (estimated 3x)
- **Value: 3.5x detection coverage for 2.3x effort = 1.5x ROI**

---

### Validation Suite Impact Projection

**Current (4 tiers):**
- project_anarchy: 15-25 findings (CVEs, typos, suspicious versions)

**Enhanced (14 categories):**
- project_anarchy projected: 60-80 findings
  - CVEs: 15 (same)
  - Typosquatting: 1 (same)
  - Suspicious versions: 15 (same)
  - **Ghost dependencies: 8** (importing undeclared)
  - **Version pinning: 12** (unpinned production deps)
  - **Update lag: 10** (2+ major versions behind)
  - **License issues: 3** (GPL conflicts)
  - **Peer conflicts: 2** (React version mismatches)
  - **Bundle size: 5** (large frontend deps)
  - **Abandonment: 4** (2+ years no updates)

---

## Phase 12: Implementation Sequencing

### Sprint 1 (8-12 hours): Core Vulnerability Scanner
- Implement 4-tier detection (CVE, typo, suspicious, unused)
- Database integration (read package_configs, write findings_consolidated)
- Caching layer (OSV.dev, native tools)
- Validation: ≥15 findings in project_anarchy

### Sprint 2 (8 hours): Quick Wins (P0)
- Ghost dependencies (Tier 4, 2h)
- Version pinning (Tier 5, 1h)
- Dependency bloat (Tier 5, 2h)
- Update lag (Tier 5, 2h)
- Validation: ≥40 findings in project_anarchy

### Sprint 3 (12 hours): High-Value Additions (P1)
- License compliance (Tier 5, 4h)
- Peer dependency conflicts (Tier 5, 3h)
- Freshness/abandonment (Tier 5, 3h)
- Bundle size impact (Tier 4, 3h)
- Validation: ≥60 findings in project_anarchy

### Sprint 4 (8 hours): Advanced Features (P2-P3)
- Supply chain depth (Tier 6, 4h)
- Security policy compliance (Tier 5, 4h)
- Validation: ≥70 findings in project_anarchy

**Total Effort:** 36-40 hours (5 days)

---

## Conclusion (Updated)

### Pre-Implementation Summary

**Current State:**
- vulnerability_scanner.py.bak is a subprocess-only tool wrapper
- No database integration, no caching, limited detection (4 categories only)
- 0% detection rate in validation suite
- **Massive missed opportunities** due to lack of database integration

**Target State (Core - Sprint 1):**
- Gold standard database-first architecture
- Multi-tier detection (native tools → OSV.dev → local → usage)
- Dual-write pattern (database + JSON)
- 50x performance improvement with caching
- **4 detection categories:** CVEs, typosquatting, suspicious versions, unused deps

**Target State (Enhanced - Sprints 2-4):**
- **10 additional detection categories** leveraging rich database
- **14 total detection categories** (3.5x coverage increase)
- Ghost dependencies, version pinning, dependency bloat, update lag
- License compliance, peer conflicts, abandonment, bundle size, supply chain depth, security policy
- **ROI:** 3.5x detection for 2.3x effort (1.5x value multiplier)

**Estimated Effort:**
- Core Scanner (Sprint 1): 8-12 hours → **≥15 findings** in project_anarchy
- Enhanced Coverage (Sprints 2-4): 28 hours → **≥70 findings** in project_anarchy
- **Total: 36-40 hours (5 days)** for complete implementation

**Risk Level:** LOW (well-defined architecture, proven patterns)

---

### Verification Findings Summary
- ✅ Confirmed vulnerability_scanner omitted from v1.1 refactor
- ✅ Confirmed no database integration (JSON-only)
- ✅ Confirmed subprocess-only approach (no OSV.dev, no local checks)
- ✅ Confirmed no caching (runs every time)
- ✅ **Identified 10 missed detection opportunities from rich database**

### Root Cause Summary
"vulnerability_scanner.py was not included in the v1.1 database-first refactor, creating an architectural inconsistency where the vulnerability scanner operates as an isolated subprocess wrapper instead of an integrated database-aware analysis module. This also prevented leveraging the rich database (package_configs, import_styles, lock_analysis) for 10 additional detection categories."

### Implementation Logic Summary
"Rewrite as database-first multi-tier detection system following established patterns from taint and rules packages, with graceful degradation, comprehensive caching, and dual-write integration for FCE correlation. Implement in 4 sprints: (1) Core 4-tier scanner, (2) Quick wins (ghost deps, pinning, bloat, lag), (3) High-value additions (licenses, peer conflicts, abandonment, bundle size), (4) Advanced features (supply chain depth, security policy)."

### Enhanced Coverage Impact Summary
- **Current Coverage:** 4 categories (CVEs, typos, suspicious versions, unused)
- **Enhanced Coverage:** 14 categories (10 new leveraging database)
- **Detection Increase:** 15 findings → 70+ findings (4.7x improvement)
- **Unique Value:** Database-first architecture enables detections impossible with subprocess-only approach
  - Ghost dependencies: Requires import_styles table cross-reference
  - Bundle size impact: Requires frontend file detection + usage correlation
  - Peer conflicts: Requires version resolution + semantic analysis
  - License compliance: Requires metadata enrichment + compatibility matrix

### Confidence Level: **HIGH**
- Architecture is proven (follows indexer/taint/rules patterns)
- Detection sources are reliable (OSV.dev, npm audit, pip-audit, npm registry, PyPI API)
- Testing strategy is comprehensive (unit + integration + validation suite)
- Risk mitigation is planned (fallbacks, caching, error handling)
- **Enhanced coverage is database-native** (no external dependencies for 6/10 new categories)

---

**Confirmation of Understanding:**

I confirm that I have followed the Prime Directive and all protocols in SOP v4.20:
- ✅ Verification Phase completed (analyzed current code, confirmed hypotheses)
- ✅ Deep Root Cause Analysis completed (traced omission from v1.1 refactor)
- ✅ Implementation Strategy documented (database-first multi-tier architecture)
- ✅ **Enhanced Coverage Analysis completed** (identified 10 additional detection categories)
- ✅ Testing Strategy defined (unit + integration tests + validation suite)
- ✅ Risk Analysis completed (4 risks identified with mitigation)
- ✅ **ROI Analysis completed** (3.5x coverage for 2.3x effort = 1.5x value)

This document provides a complete blueprint for any AI agent to implement the vulnerability scanner rewrite following TheAuditor's gold standard architecture, including a comprehensive roadmap for leveraging the rich database to detect 10 additional categories beyond traditional vulnerability scanning.

---

## Appendix: Detection Category Reference Table

| # | Category | Data Source | Tier | Effort | Detection Rate | Severity Range |
|---|----------|-------------|------|--------|----------------|----------------|
| 1 | CVEs | OSV.dev + native tools | 1-2 | Included | 80-90% | CRITICAL-LOW |
| 2 | Typosquatting | Config dictionary | 3 | Included | 95% | CRITICAL |
| 3 | Suspicious Versions | Pattern matching | 3 | Included | 99% | CRITICAL-HIGH |
| 4 | Unused Dependencies | import_styles table | 4 | Included | 85% | LOW |
| 5 | Ghost Dependencies | import_styles + package_configs | 4 | 2h | 90% | HIGH-MEDIUM |
| 6 | Version Pinning | package_configs regex | 5 | 1h | 95% | HIGH-LOW |
| 7 | Dependency Bloat | package_configs recursive | 5 | 2h | 70% | HIGH-MEDIUM |
| 8 | Update Lag | Version API + comparison | 5 | 2h | 90% | CRITICAL-MEDIUM |
| 9 | License Compliance | npm/PyPI API + matrix | 5 | 4h | 80% | CRITICAL-MEDIUM |
| 10 | Peer Conflicts | package_configs + version resolution | 5 | 3h | 60% | CRITICAL-LOW |
| 11 | Abandonment | npm/PyPI API dates | 5 | 3h | 70% | HIGH-MEDIUM |
| 12 | Bundle Size | npm API + import_styles | 4 | 3h | 60% | CRITICAL-MEDIUM |
| 13 | Supply Chain Depth | lock_file_analysis graph | 6 | 4h | 50% | HIGH-MEDIUM |
| 14 | Security Policy | OSV.dev + threat intel | 5 | 4h | 40% | CRITICAL-HIGH |

**Total Categories:** 14
**Total Effort:** 36-40 hours
**Average Detection Rate:** 77%
**Unique to Database-First Architecture:** 10 categories (71%)

---

**End of Pre-Implementation Report**

*Document Version: 1.0*
*Last Updated: 2025-10-02*
*Report Mode: Complete - Ready for Implementation*
