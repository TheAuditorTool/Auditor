Python Extraction Parity & Architecture Overhaul - Merge Request

Pull Request Title

feat: Python extraction parity + complete architecture modernization

Pull Request Description / Merge Commit Body

Summary:
Major release implementing Python framework extraction parity with JavaScript, complete taint analysis rewrite (IFDS-based), schema-driven modular architecture, and comprehensive test fixture expansion.

This merge introduces 132 commits representing a fundamental transformation of the architecture.

Reference Issues:
Closes #19
Closes #21

Executive Summary

This represents TheAuditor's most significant architectural transformation to date. It introduces comprehensive Python framework support (achieving parity with JavaScript analysis), a complete rewrite of the taint analysis engine using IFDS principles, and fundamental performance improvements including a 54.5x speedup in AST extraction.

The update moves the system from a monolithic architecture to a modular, schema-driven design with Zero Fallback policy enforcement.

Detailed Changelog

1. 🔬 Taint Analysis Engine - Complete Rewrite

Architecture Shift:

Deleted (Legacy): database.py, sources.py, registry.py (Hardcoded patterns), propagation.py (Legacy engine), cfg_integration.py (866 lines of mixed logic).

Added (IFDS-Based):

ifds_analyzer.py (628 LOC): Backward taint analysis with access-path sensitivity.

flow_resolver.py (778 LOC): Forward flow analysis with in-memory graph optimization.

discovery.py (684 LOC): Database-driven source/sink discovery (replaces hardcoded patterns).

access_path.py (246 LOC): k-limiting field-sensitive tracking (distinguishes req.body vs req.headers).

sanitizer_util.py & orm_utils.py: Unified sanitizer registry and ORM-aware tracking.

Performance & Features:

Graph Pre-loading: Reduced 10M SQL queries to 1 query + RAM lookups.

Throttling: Adaptive per-entry throttling (Infrastructure vs User Input).

Speedup: Large codebase analysis dropped from 2+ hours to 6.6 minutes (18x+ speedup).

Boundary Analysis: Added security control distance measurement.

Session Analysis: AI agent session behavior analysis integration.

2. 📊 Indexer & Schema - Modular Architecture

Monolith Split:

Split schema.py (1760 LOC) into 8 domain-specific modules.

Split storage.py into domain-specific storage modules (Core, Python, Node, Infra).

Total: 250 tables across 8 schema domains.

New Schema Modules (theauditor/indexer/schemas/):

core_schema.py (24 generic tables)

python_schema.py (59 Python framework tables)

node_schema.py (26 Node/JS/TS tables)

infrastructure_schema.py (18 IaC tables)

graphql_schema.py (8 GraphQL tables)

security_schema.py (7 security tables)

frameworks_schema.py & planning_schema.py

Code Generation System:

generated_types.py (2384 LOC): TypedDict for type-safe row access.

generated_accessors.py (6905 LOC): 250 table accessor classes.

Hash-based invalidation to detect stale generated code.

3. 🐍 AST Extractors - Python Framework Parity (Phase 3)

New Python Extractors (theauditor/ast_extractors/python/):
Replaced monolithic python_impl.py with 27 specialized modules containing 236 extraction functions (15,090 LOC).

Web Frameworks (2,082 LOC):

Django: CBVs, forms, admin, middleware, signals, managers.

Flask: Blueprints, extensions, hooks, WebSocket, CLI.

FastAPI: Routes, dependencies, auth decorators.

Data & ORM (1,081 LOC):

SQLAlchemy: Models, relationships, cascade detection.

Validation: Pydantic (Field/Root validators), Marshmallow, DRF, WTForms.

Security Patterns (759 LOC):

Auth decorators, password hashing, JWT, SQL/Command injection sinks, dangerous eval/exec, cryptography.

Async & Tasks (638 LOC):

Celery: Tasks, schedules, task calls.

GraphQL: Resolvers, schema definitions.

Testing (400 LOC):

pytest fixtures/markers, unittest, hypothesis, mocks.

Core Language (Python 3.14 Modernization):

Coverage for comprehensions, walrus operators, pattern matching, and protocols.

4. 🛡️ Rules Engine - Standardization & Expansion

Stats: 97 files changed, +13,363/-6,495 lines. Total rules increased from 83 to 200+.

New Categories:

GraphQL Security (9 rules): Injection, N+1, overfetch, depth limits, auth, sensitive fields.

Supply Chain (11 rules): Dependency confusion, version analysis.

GitHub Actions (7 rules): CI/CD pipeline security and injection.

AWS CDK (4 rules): Infrastructure misconfigurations.

Dead Code: Multi-table dead code detection.

Quality Improvements:

ZERO FALLBACK Policy: Eliminated try-except fallback handlers; DB contract guarantees table existence.

Refactoring: 51 rules migrated to find_* convention; modernized type hints.

5. 🧪 Test Suite - Fixture-Driven Architecture

Stats: 317 files changed, +45,838/-6,239 lines.

Removed: 19 legacy test modules and harness infrastructure.

Added: 317 new test fixtures across 23 categories.

Python: Django (App/Advanced), Flask, FastAPI, SQLAlchemy (Complex), Celery, Realworld project.

Node.js: Express, Next.js, React, Angular, Vue, Prisma, BullMQ.

Infra: AWS CDK, Terraform, GitHub Actions.

Integration: All fixtures are spec.yaml compliant.

6. 🔧 Infrastructure, CLI & AI

CLI & Documentation:

AI-First Help: VerboseGroup auto-generates docs.

New Commands: aud planning, aud workflows (GitHub Actions), aud session, aud deadcode.

Docs: Rewritten Architecture.md, HowToUse.md, and new Agent Guides.

Graph Engine & ML:

Graph Optimization: dfg_builder.py (+1098 LOC) with O(1) adjacency list lookups.

ML Risk Models: Added Tier 5 AI Agent Behavior Intelligence (session analysis).

Modernization:

Python 3.14: Removed from __future__ import annotations.

Performance: Connection pooling (87% DB overhead reduction).

Statistics

Metric

Value

Notes

Commits

132



Files Changed

839



Insertions

+165,292

Includes generated accessors/types

Deletions

-66,293

Massive cleanup of legacy engines

Net Change

+98,999



New Extractors

27 modules

236 specialized functions

Schema Tables

250

Across 8 domains

Test Fixtures

317

Covering 23 framework categories

Performance

54.5x

AST extraction speedup

Breaking Changes

Schema Regeneration Required: You must run python -m theauditor.indexer.schemas.codegen after checkout.

Python Version: STRICT requirement for Python 3.14+ (due to new type hinting syntax).

Taint API: The legacy taint analysis API has been deprecated and replaced by ifds_analyzer.

Test Harness: Legacy test_*.py files have been deleted; use the new fixture system.

Migration Instructions

Rebuild Schema:

# Windows/Linux
python -m theauditor.indexer.schemas.codegen


Rebuild Database:

aud full


Verify Analysis:

aud taint-analyze --verbose


Update Custom Rules: Ensure any custom rules use the new generated_accessors rather than raw SQL or legacy storage methods.

Commit History Highlights

This branch contains 132 commits. Highlights from the history include:

perf(taint): optimize FlowResolver with in-memory graph and adaptive throttling

refactor: complete Python 3.14 modernization - remove legacy future annotations

refactor: modernize codebase to Python 3.14 and optimize AST extraction (54.5x faster)

refactor(graph): modernize graph engine and persistence layer

refactor: implement sandboxed execution architecture for zero-pollution installs

feat(security): add boundary analysis for security control distance measurement

refactor(indexer): split monolithic storage.py into domain-specific modules

refactor(ast): split core extractors into domain modules

feat(ml): Add Tier 5 agent behavior intelligence to ML risk models

feat(extraction): add JavaScript framework parity and Python validation support

refactor: migrate taint analysis to schema-driven architecture

feat(security): enhance vulnerability scanner with full CWE taxonomy preservation

feat(python): implement Phase 3 extraction - 25 extractors for Flask, Security, Django, Testing

feat(graphql): complete resolver correlation and security rules implementation

feat(cli): implement AI-first help system with comprehensive documentation

feat: Add comprehensive dead code detection with multi-table analysis

refactor(core): Split monolithic indexer components into modular architecture

feat(taint): Implement two-pass hybrid taint analysis with cross-file support

feat(python): add validation frameworks, Celery ecosystem, and generators extraction

feat(cdk): Add TypeScript/JavaScript support for AWS CDK analysis