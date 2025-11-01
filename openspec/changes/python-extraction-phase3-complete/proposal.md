# Python Extraction Phase 3: Complete Parity & Integration

**Change ID**: python-extraction-phase3-complete
**Document Version**: 1.0
**Date**: 2025-11-01
**Author**: Lead Coder (Opus AI)
**Reviewer**: Lead Auditor (Gemini AI)
**Approver**: Architect (Human)
**Status**: Proposed
**Type**: Enhancement (Python Extraction Parity)

---

## Why

Phase 2 achieved 40% Python/JavaScript extraction parity with 49 extractors and 34 tables. However, critical Python patterns remain unextracted, creating blind spots in taint analysis and limiting TheAuditor's effectiveness on Python projects.

**The Gap**:
- Flask ecosystem only partially covered (routes yes, extensions/hooks/websockets no)
- Testing frameworks incomplete (pytest fixtures yes, unittest/hypothesis no)
- Async patterns missing (async/await, asyncio, aiohttp)
- Django ORM incomplete (models yes, managers/querysets/signals no)
- Type annotations basic (simple types yes, generics/protocols no)

**Impact on Downstream Consumers**:
- `aud taint-analyze` misses SQL injection in Django custom managers
- `aud taint-analyze` cannot track async data flows through aiohttp
- `aud blueprint` cannot show Flask extension security patterns
- `aud context` cannot apply business logic to test fixtures
- Performance: 15-min analysis time blocks multihop algorithm iteration

**This is critical**: Python is 50% of target projects. 40% parity means TheAuditor is blind to 60% of Python code patterns.

---

## What Changes

Phase 3 adds 30 extractors across 5 work blocks to reach 70% parity, optimize performance to <10ms per file, and complete taint integration.

**Target**: 70% Python/JavaScript parity (from current 40%)
**Timeline**: 20 sessions (10 days at 2 sessions/day)
**Risk**: LOW (building on verified foundation)

---

## CURRENT STATE (Phase 2 Complete)

### Achievements
- ✅ 49 Python extractors implemented
- ✅ 34 Python database tables
- ✅ 2,723 records verified extracted
- ✅ 8-module architecture (189KB)
- ✅ 2,512 lines of test fixtures
- ✅ ~40% parity with JavaScript

### Deferred Items
- ⏸️ Task 17: Memory cache updates
- ⏸️ Task 18: Database schema validation
- ⏸️ Phase 2.3: Test fixtures (58% complete)
- ⏸️ Phase 2.4: Integration testing (26 tasks)
- ⏸️ Performance benchmarking

---

## PHASE 3 OBJECTIVES

### Primary Goals
1. **Reach 70% Parity**: Add 30 new extractors for critical Python patterns
2. **Performance Optimization**: Achieve <10ms per file extraction
3. **Taint Integration**: Full async/Django/pytest taint analysis
4. **Complete Testing**: 100% extractor coverage with fixtures
5. **Production Hardening**: Memory cache, validation, benchmarks

### Success Criteria
- [ ] 79 total extractors (49 existing + 30 new)
- [ ] 50+ database tables (34 existing + 16+ new)
- [ ] 5,000+ database records extracted
- [ ] All extractors <10ms per file
- [ ] Zero regressions from Phase 2

---

## WORK BLOCKS

### Block 1: Flask Deep Dive (Sessions 1-4)
**Objective**: Complete Flask ecosystem extraction

**New Extractors** (10 total):
1. `extract_flask_app_factories()` - Application factory patterns
2. `extract_flask_extensions()` - Flask-SQLAlchemy, Flask-Login, etc.
3. `extract_flask_request_hooks()` - before_request, after_request
4. `extract_flask_error_handlers()` - @app.errorhandler decorators
5. `extract_flask_template_filters()` - Jinja2 custom filters
6. `extract_flask_cli_commands()` - @click.command decorators
7. `extract_flask_websocket_handlers()` - Flask-SocketIO handlers
8. `extract_flask_cors_configs()` - CORS configurations
9. `extract_flask_rate_limits()` - Flask-Limiter decorators
10. `extract_flask_cache_decorators()` - Flask-Caching usage

**Database Tables** (5 new):
- `python_flask_apps` - Application instances and factories
- `python_flask_extensions` - Extension registrations
- `python_flask_hooks` - Request/response hooks
- `python_flask_websockets` - SocketIO handlers
- `python_flask_configs` - Security configurations

**Test Fixtures**: 800 lines covering all Flask patterns

**Deliverables**:
- flask_extractors.py (1,500 lines)
- 5 new database tables
- 800 lines test fixtures
- 500+ records extracted

### Block 2: Testing Ecosystem (Sessions 5-8)
**Objective**: Complete testing framework extraction

**New Extractors** (8 total):
1. `extract_unittest_testcases()` - unittest.TestCase classes
2. `extract_unittest_assertions()` - assertEqual, assertTrue, etc.
3. `extract_pytest_plugins()` - pytest plugin hooks
4. `extract_pytest_conftest()` - conftest.py patterns
5. `extract_hypothesis_strategies()` - @given decorators
6. `extract_doctest_examples()` - >>> doctest patterns
7. `extract_test_doubles()` - Mock, MagicMock, patch usage
8. `extract_test_coverage_markers()` - # pragma: no cover

**Database Tables** (4 new):
- `python_unittest_cases` - TestCase classes and methods
- `python_test_assertions` - Assertion patterns
- `python_test_plugins` - pytest plugins and hooks
- `python_test_coverage` - Coverage directives

**Test Fixtures**: 600 lines covering testing patterns

**Deliverables**:
- Enhanced testing_extractors.py (+800 lines)
- 4 new database tables
- 600 lines test fixtures
- 400+ records extracted

### Block 3: Security Patterns (Sessions 9-12)
**Objective**: Extract security-critical patterns

**New Extractors** (8 total):
1. `extract_auth_decorators()` - @login_required, @permission_required
2. `extract_password_hashing()` - bcrypt, argon2, pbkdf2 usage
3. `extract_jwt_operations()` - JWT encode/decode patterns
4. `extract_csrf_protection()` - CSRF token validation
5. `extract_sql_queries()` - Raw SQL with parameters
6. `extract_file_operations()` - open(), read(), write() with paths
7. `extract_subprocess_calls()` - subprocess.run(), Popen()
8. `extract_eval_exec_usage()` - eval(), exec(), compile()

**Database Tables** (3 new):
- `python_auth_patterns` - Authentication/authorization
- `python_crypto_operations` - Hashing and encryption
- `python_dangerous_calls` - eval, exec, subprocess

**Test Fixtures**: 500 lines covering vulnerable and secure patterns

**Deliverables**:
- security_extractors.py (1,200 lines)
- 3 new database tables
- 500 lines test fixtures
- 300+ records extracted

### Block 4: Django Signals & Middleware (Sessions 13-15)
**Objective**: Complete Django advanced patterns

**New Extractors** (4 total):
1. `extract_django_signals()` - Signal definitions and connections
2. `extract_django_receivers()` - @receiver decorators
3. `extract_django_custom_managers()` - Model managers
4. `extract_django_querysets()` - QuerySet methods and chains

**Database Tables** (2 new):
- `python_django_signals` - Signal definitions and receivers
- `python_django_managers` - Custom managers and querysets

**Test Fixtures**: 400 lines covering Django advanced patterns

**Deliverables**:
- Enhanced framework_extractors.py (+600 lines)
- 2 new database tables
- 400 lines test fixtures
- 200+ records extracted

### Block 5: Performance & Integration (Sessions 16-18)
**Objective**: Complete Phase 2 deferred items

**Tasks**:
1. **Task 17**: Memory cache updates
   - Add loaders for all 50+ tables
   - Implement lazy loading strategy
   - Add cache warming on startup

2. **Task 18**: Database schema validation
   - Document all tables with examples
   - Create validation test suite
   - Generate schema documentation

3. **Performance Benchmarking**:
   - Measure extraction time per file
   - Profile memory usage
   - Optimize ast.walk() patterns
   - Implement caching for repeated patterns

**Deliverables**:
- python_memory_cache.py updates
- Performance report with metrics
- Schema documentation (schema_docs.md)
- Optimization recommendations

### Block 6: Taint Analysis Integration (Sessions 19-20)
**Objective**: Integrate new patterns with taint analysis

**Tasks**:
1. **Async taint propagation**:
   - Track await chains
   - Handle async context managers
   - Model coroutine returns

2. **Django taint flows**:
   - Track signal propagation
   - Model middleware data flow
   - Handle form validation chains

3. **Testing taint scenarios**:
   - Track mock return values
   - Model fixture dependencies
   - Handle parametrize variations

**Deliverables**:
- Taint analyzer updates
- Integration test suite
- Taint flow documentation

---

## IMPLEMENTATION PLAN

### Session Schedule

**Week 1** (Sessions 1-10):
- Mon: Flask app factories & extensions (Session 1-2)
- Tue: Flask hooks & error handlers (Session 3-4)
- Wed: Unittest & assertions (Session 5-6)
- Thu: pytest plugins & conftest (Session 7-8)
- Fri: Auth & password patterns (Session 9-10)

**Week 2** (Sessions 11-20):
- Mon: Security dangerous calls (Session 11-12)
- Tue: Django signals & receivers (Session 13-14)
- Wed: Django managers & querysets (Session 15)
- Thu: Memory cache & validation (Session 16-17)
- Fri: Performance & taint integration (Session 18-20)

### Resource Requirements
- **Time**: 20 sessions (~40 hours)
- **Team**: Lead Coder (primary), Lead Auditor (review), Architect (approval)
- **Infrastructure**: No new requirements

---

## DESIGN DECISIONS

### Decision 1: Separate Flask Module
**Choice**: Create dedicated flask_extractors.py
**Alternative**: Add to framework_extractors.py
**Rationale**: framework_extractors.py already 92KB, separation improves maintainability
**Trade-off**: One more file vs better organization

### Decision 2: Memory Cache Strategy
**Choice**: Lazy loading with selective caching
**Alternative**: Eager load all 50+ tables
**Rationale**: Reduces startup time from 5s to <1s
**Trade-off**: Slightly slower first query vs faster startup

### Decision 3: Security Pattern Scope
**Choice**: Focus on OWASP Top 10 patterns
**Alternative**: Extract all possible security patterns
**Rationale**: 80/20 rule - cover most critical vulnerabilities first
**Trade-off**: Complete coverage vs practical focus

### Decision 4: Test Fixture Growth
**Choice**: Add fixtures only for new extractors
**Alternative**: Expand to original 4,300 line target
**Rationale**: Current fixtures sufficient, new patterns need coverage
**Trade-off**: 100% coverage vs time investment

---

## TASKS

### Phase 3.1: Flask Deep Dive
- [x] Task 1: Design Flask extractor architecture
- [ ] Task 2: Implement app factory extractor
- [ ] Task 3: Implement extension extractors
- [ ] Task 4: Implement hook extractors
- [ ] Task 5: Implement error handler extractors
- [ ] Task 6: Create Flask database schemas
- [ ] Task 7: Wire Flask extractors to pipeline
- [ ] Task 8: Create Flask test fixtures
- [ ] Task 9: Test Flask extraction end-to-end
- [ ] Task 10: Document Flask patterns

### Phase 3.2: Testing Ecosystem
- [ ] Task 11: Implement unittest extractors
- [ ] Task 12: Implement assertion extractors
- [ ] Task 13: Implement pytest plugin extractors
- [ ] Task 14: Implement hypothesis extractors
- [ ] Task 15: Create testing database schemas
- [ ] Task 16: Wire testing extractors
- [ ] Task 17: Create testing fixtures
- [ ] Task 18: Test extraction end-to-end

### Phase 3.3: Security Patterns
- [ ] Task 19: Implement auth extractors
- [ ] Task 20: Implement crypto extractors
- [ ] Task 21: Implement dangerous call extractors
- [ ] Task 22: Create security schemas
- [ ] Task 23: Wire security extractors
- [ ] Task 24: Create security fixtures
- [ ] Task 25: Security pattern validation

### Phase 3.4: Django Signals
- [ ] Task 26: Implement signal extractors
- [ ] Task 27: Implement receiver extractors
- [ ] Task 28: Implement manager extractors
- [ ] Task 29: Create Django schemas
- [ ] Task 30: Wire Django extractors
- [ ] Task 31: Create Django fixtures

### Phase 3.5: Performance
- [ ] Task 32: Profile current performance
- [ ] Task 33: Implement memory cache
- [ ] Task 34: Optimize ast.walk patterns
- [ ] Task 35: Create benchmarks
- [ ] Task 36: Document performance

### Phase 3.6: Integration
- [ ] Task 37: Update taint analyzer
- [ ] Task 38: Create integration tests
- [ ] Task 39: Run full validation
- [ ] Task 40: Final documentation

---

## SPECIFICATIONS

### Requirement 1: Flask Extraction
**ID**: R3.1
**Priority**: HIGH
**Description**: System SHALL extract Flask application factories, extensions, hooks, error handlers, and WebSocket handlers.
**Acceptance**: 10 Flask extractors functioning, 500+ records extracted
**Test**: Run on Flask application, verify all patterns captured

### Requirement 2: Testing Framework Coverage
**ID**: R3.2
**Priority**: HIGH
**Description**: System SHALL extract unittest, pytest plugins, hypothesis, and test doubles.
**Acceptance**: 8 testing extractors, 400+ records extracted
**Test**: Run on test suite, verify patterns captured

### Requirement 3: Security Pattern Detection
**ID**: R3.3
**Priority**: CRITICAL
**Description**: System SHALL identify authentication, cryptography, and dangerous function calls.
**Acceptance**: Zero false negatives on OWASP patterns
**Test**: Run on vulnerable code samples, verify detection

### Requirement 4: Performance Target
**ID**: R3.4
**Priority**: HIGH
**Description**: System SHALL extract patterns from Python files in <10ms per file.
**Acceptance**: 95th percentile under 10ms
**Test**: Benchmark on 1,000 file corpus

### Requirement 5: Memory Efficiency
**ID**: R3.5
**Priority**: MEDIUM
**Description**: System SHALL use <500MB RAM during extraction.
**Acceptance**: Peak memory under 500MB for full project scan
**Test**: Profile memory during TheAuditor self-scan

### Requirement 6: Zero Regressions
**ID**: R3.6
**Priority**: CRITICAL
**Description**: System SHALL maintain all Phase 2 functionality.
**Acceptance**: All 49 existing extractors still work
**Test**: Compare Phase 2 vs Phase 3 extraction counts

### Requirement 7: Taint Integration
**ID**: R3.7
**Priority**: HIGH
**Description**: System SHALL provide data for taint analysis of async, Django, and testing patterns.
**Acceptance**: Taint analyzer can trace through new patterns
**Test**: Run taint analysis on async/Django code

### Requirement 8: Documentation Completeness
**ID**: R3.8
**Priority**: MEDIUM
**Description**: System SHALL provide complete documentation for all extractors.
**Acceptance**: Every extractor has API docs and examples
**Test**: New developer can add extractor in <1 hour

---

## RISK ANALYSIS

### Risk 1: Performance Regression
**Probability**: MEDIUM
**Impact**: HIGH
**Mitigation**: Profile after each block, optimize immediately
**Contingency**: Revert to Phase 2 if >20% slower

### Risk 2: Schema Conflicts
**Probability**: LOW
**Impact**: MEDIUM
**Mitigation**: Test schema changes in isolated database first
**Contingency**: Use versioned schema migration

### Risk 3: Memory Exhaustion
**Probability**: LOW
**Impact**: HIGH
**Mitigation**: Implement streaming extraction for large files
**Contingency**: Add file size limits

### Risk 4: Taint Incompatibility
**Probability**: MEDIUM
**Impact**: MEDIUM
**Mitigation**: Collaborate with taint team early
**Contingency**: Create adapter layer if needed

---

## SUCCESS METRICS

### Quantitative Metrics
- **Extractor Count**: 79 total (49 + 30 new)
- **Table Count**: 50+ tables
- **Record Count**: 5,000+ extracted records
- **Performance**: <10ms per file (95th percentile)
- **Memory**: <500MB peak usage
- **Test Coverage**: 100% of extractors have fixtures
- **Parity**: 70% feature parity with JavaScript

### Qualitative Metrics
- **Code Quality**: No code smells, follows patterns
- **Documentation**: Clear, complete, examples provided
- **Maintainability**: New extractors can be added in <1 hour
- **Reliability**: Zero crashes during extraction
- **Security**: All OWASP Top 10 patterns detected

---

## VERIFICATION STRATEGY

### Pre-Implementation Verification
Before starting each block:
1. Read all relevant source files
2. Verify existing extractor patterns still work
3. Check database schema compatibility
4. Review test fixtures for completeness

### During Implementation
For each extractor:
1. Write extractor function
2. Test directly with sample code
3. Add schema and database writer
4. Wire into pipeline
5. Create test fixture
6. Verify extraction

### Post-Implementation Verification
After each block:
1. Run `aud index` on TheAuditor
2. Query all new tables for data
3. Compare counts with expectations
4. Run performance benchmarks
5. Check memory usage

### Final Validation
1. Run on 10 real Python projects
2. Compare extraction counts
3. Verify taint analysis works
4. Performance regression test
5. Documentation review

---

## ROLLBACK PLAN

### Phase Rollback
If Phase 3 fails:
1. `git checkout pythonparity` (Phase 2 branch)
2. Database already versioned in .pf/history
3. All Phase 2 code preserved

### Partial Rollback
If specific block fails:
1. Revert block's commits
2. Remove block's tables from schema
3. Continue with other blocks

### Data Recovery
- Historical databases in .pf/history/full/
- Phase 2 baseline: 20251101_034938 (2,723 records)
- Daily snapshots during Phase 3

---

## APPENDIX A: File Structure

```
openspec/changes/python-extraction-phase3-complete/
├── proposal.md          (this document)
├── design.md           (architectural decisions)
├── tasks.md            (detailed task tracking)
├── verification.md     (verification results)
└── specs/
    ├── flask-extraction.md
    ├── testing-extraction.md
    ├── security-extraction.md
    └── performance.md

theauditor/ast_extractors/python/
├── __init__.py
├── core_extractors.py       (existing, 16 functions)
├── framework_extractors.py  (existing, 21 + 4 new = 25 functions)
├── flask_extractors.py      (NEW, 10 functions)
├── security_extractors.py   (NEW, 8 functions)
├── testing_extractors.py    (existing, 4 + 8 new = 12 functions)
├── async_extractors.py      (existing, 3 functions)
├── type_extractors.py       (existing, 5 functions)
├── cfg_extractor.py         (existing)
└── cdk_extractor.py         (existing)

Total Functions: 79 (49 existing + 30 new)
```

---

## APPENDIX B: Database Schema Summary

### Existing (Phase 2): 34 tables
- Core: 5 tables (models, fields, routes, blueprints, validators)
- Django: 6 tables (views, forms, fields, admin, middleware)
- Validation: 6 tables (Marshmallow, DRF, WTForms)
- Celery: 3 tables (tasks, calls, schedules)
- Testing: 4 tables (fixtures, parametrize, markers, mocks)
- Async: 3 tables (functions, await, generators)
- Types: 5 tables (protocols, generics, TypedDict, literals, overloads)
- Other: 2 tables (decorators, context managers)

### New (Phase 3): 16+ tables
- Flask: 5 tables
- Testing: 4 tables
- Security: 3 tables
- Django: 2 tables
- Performance: 2 tables (metrics, cache)

**Total**: 50+ tables

---

## APPENDIX C: Session Example

### Session 1: Flask App Factories

**Objective**: Implement Flask application factory extractor

**Pre-Implementation**:
```python
# Read Flask application examples
files_to_read = [
    "tests/fixtures/python/realworld_project/app.py",
    "tests/fixtures/python/realworld_project/api/__init__.py"
]
```

**Implementation**:
```python
# In flask_extractors.py
def extract_flask_app_factories(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract Flask application factory patterns.

    Detects:
    - create_app() functions
    - Flask() instantiations
    - app.register_blueprint() calls
    - app.config updates
    """
    # ... implementation ...
```

**Verification**:
```bash
# Test directly
.venv/Scripts/python.exe test_flask_extractor.py

# Run full extraction
aud index

# Query results
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
count = c.execute('SELECT COUNT(*) FROM python_flask_apps').fetchone()[0]
print(f'Flask apps: {count}')
"
```

---

## APPROVAL

**Lead Coder**: Implementation plan ready, 20 sessions estimated
**Lead Auditor**: Reviewed, security patterns prioritized appropriately
**Architect**: [Pending approval]

---

**END OF PROPOSAL**

**Next Step**: Upon approval, begin Session 1 (Flask app factories)