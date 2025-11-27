Technical Debt & Stability Action Plan

This document consolidates actionable technical debt identified in the codebase, stripped of AI hallucinations.

🚨 Priority 1: Critical Stability & Logic Risks

These issues threaten the integrity of data or cause silent failures. Address immediately.

🛑 "Cursor State" Bugs (Data Loss Risk)

Logic iterates over a cursor without storing results first, causing state loss or incomplete iteration.

[ ] theauditor/rules/frameworks/fastapi_analyze.py: Store results before loop.

[ ] theauditor/rules/frameworks/react_analyze.py: Store results before loop (Lines 549, 640).

[ ] theauditor/rules/frameworks/vue_analyze.py: Store results before loop (Lines 176, 357).

[ ] theauditor/rules/orm/prisma_analyze.py: Store results before nested loop.

[ ] theauditor/rules/orm/sequelize_analyze.py: Store results before loop.

[ ] theauditor/rules/python/python_crypto_analyze.py: Store results before loop (Line 295).

[ ] theauditor/rules/python/python_deserialization_analyze.py: Store results before loop.

♻️ AST Idempotency (Duplicate Data Risk)

Extractors are visiting nodes multiple times. Ensure deduplication logic is preserved.

[ ] theauditor/ast_extractors/typescript_impl.py: Verify deduplication by (line, target_var, in_function) and (line, function_name).

[ ] theauditor/ast_extractors/python_impl.py: Verify deduplication logic matches TypeScript implementation.

[ ] theauditor/ast_extractors/treesitter_impl.py: Verify deduplication by (name, line, type) to handle recursive AST traversal.

🛡️ Zero Fallback Policy Violations

Code attempting to "fail gracefully" where it should crash to expose bugs.

[ ] theauditor/indexer/extractors/javascript.py: Remove fallback logic for batch processing failures. If tables/keys are missing, it must crash.

[ ] theauditor/taint/core.py: Ensure no fallbacks for sources without files or malformed sinks.

[ ] theauditor/rules/vue/component_analyze.py: Ensure rule crashes if indexer tables are missing.

⚡ Priority 2: Performance Bottlenecks

Issues causing extreme slowness (N+1 queries, O(NM) complexity).*

🐌 N+1 Query Explosions (SQL inside Loops)

Rewrite these sections using SQL JOIN or CTEs.

[ ] theauditor/rules/security/cors_analyze.py: Multiple N+1 queries detected in fetchall() loops.

[ ] theauditor/rules/security/crypto_analyze.py: cursor.execute() inside fetchall() loop (multiple occurrences).

[ ] theauditor/rules/security/pii_analyze.py: cursor.execute() inside fetchall() loop (Lines 1062, 1308, 1983).

[ ] theauditor/rules/xss/express_xss_analyze.py: cursor.execute() inside fetchall() loop.

[ ] theauditor/rules/xss/react_xss_analyze.py: cursor.execute() inside fetchall() loop.

[ ] theauditor/rules/xss/vue_xss_analyze.py: cursor.execute() inside fetchall() loop.

📉 Algorithmic Inefficiencies

[ ] theauditor/graph/dfg_builder.py: Ensure "Vectorized Matching" (O(1) dict lookup) is being used instead of nested loops.

[ ] theauditor/rules/xss/template_xss_analyze.py: Move query for render functions outside the loop (Line 424).

🐛 Priority 3: Broken Features & Missing Data

Features that are currently broken or incomplete.

🔍 Missing Graph Data (Data Flow Gaps)

The Data Flow Graph (DFG) is missing connections for specific patterns.

[ ] theauditor/graph/dfg_builder.py: Fix missing edges for:

[ ] Async/Arrow Functions (102 missing edges).

[ ] Object Literals (1,921 missing edges).

[ ] Wrapped Calls (220 missing edges).

[ ] Array Literals (273 missing edges).

🛠️ Broken Analyzers

[ ] theauditor/rules/python/python_crypto_analyze.py: SHA-0 check logic is broken.

[ ] theauditor/rules/deployment/nginx_analyze.py: Crypto algorithm check is marked broken.

[ ] theauditor/deps.py: Multi-version collision logic for monorepos is broken (Line 845).

🧹 Priority 4: Cleanup & Refactoring

Dead code, deprecated features, and temp files.

🗑️ Deprecated Code to Delete

[ ] theauditor/cli.py: Remove index and tool-versions commands.

[ ] theauditor/fce.py: Remove "Factual Cluster Detection" phase.

[ ] theauditor/indexer/extractors/javascript.py: Remove deprecated Tree-sitter path (Line 382).

[ ] theauditor/rules/security/crypto_analyze.py: Remove deprecated crypto library checks (Pattern 15).

📂 File Handling Improvements

[ ] theauditor/pipelines.py: Replace temp file usage with memory pipes (IO Completion Ports) for subprocesses (Line 117).

[ ] theauditor/js_semantic_parser.py: Clean up temp file management logic.

🏗️ Refactoring

[ ] theauditor/graph/strategies/: Refactor language-specific methods out of dfg_builder.py into strategy files (node_express.py, python_orm.py).

[ ] theauditor/ast_extractors/python/framework_extractors.py: Move Flask code to flask_extractors.py.

📝 Priority 5: High-Value TODOs

Deferred tasks that impact analysis quality.

[ ] theauditor/ast_extractors/rust_impl.py: Implement full CFG extraction (currently empty list).

[ ] theauditor/rules/secrets/hardcoded_secret_analyze.py: Move Python-side filtering to SQL WHERE clauses for efficiency.

[ ] theauditor/taint/core.py: Apply security rules from /rules/ to classify flows (currently returns raw count).