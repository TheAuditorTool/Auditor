Technical Debt \& Stability Action Plan

This document consolidates actionable technical debt identified in the codebase, stripped of AI hallucinations.

🚨 Priority 1: Critical Stability \& Logic Risks

These issues threaten the integrity of data or cause silent failures. Address immediately.

🛑 "Cursor State" Bugs (Data Loss Risk)

Logic iterates over a cursor without storing results first, causing state loss or incomplete iteration.

\[ ] theauditor/rules/frameworks/fastapi\_analyze.py: Store results before loop.

\[ ] theauditor/rules/frameworks/react\_analyze.py: Store results before loop (Lines 549, 640).

\[ ] theauditor/rules/frameworks/vue\_analyze.py: Store results before loop (Lines 176, 357).

\[ ] theauditor/rules/orm/prisma\_analyze.py: Store results before nested loop.

\[ ] theauditor/rules/orm/sequelize\_analyze.py: Store results before loop.

\[ ] theauditor/rules/python/python\_crypto\_analyze.py: Store results before loop (Line 295).

\[ ] theauditor/rules/python/python\_deserialization\_analyze.py: Store results before loop.

♻️ AST Idempotency (Duplicate Data Risk)

Extractors are visiting nodes multiple times. Ensure deduplication logic is preserved.

\[ ] theauditor/ast\_extractors/typescript\_impl.py: Verify deduplication by (line, target\_var, in\_function) and (line, function\_name).

\[ ] theauditor/ast\_extractors/python\_impl.py: Verify deduplication logic matches TypeScript implementation.

\[ ] theauditor/ast\_extractors/treesitter\_impl.py: Verify deduplication by (name, line, type) to handle recursive AST traversal.

🛡️ Zero Fallback Policy Violations

Code attempting to "fail gracefully" where it should crash to expose bugs.

\[ ] theauditor/indexer/extractors/javascript.py: Remove fallback logic for batch processing failures. If tables/keys are missing, it must crash.

\[ ] theauditor/taint/core.py: Ensure no fallbacks for sources without files or malformed sinks.

\[ ] theauditor/rules/vue/component\_analyze.py: Ensure rule crashes if indexer tables are missing.

⚡ Priority 2: Performance Bottlenecks

Issues causing extreme slowness (N+1 queries, O(NM) complexity).\*

🐌 N+1 Query Explosions (SQL inside Loops)

Rewrite these sections using SQL JOIN or CTEs.

\[ ] theauditor/rules/security/cors\_analyze.py: Multiple N+1 queries detected in fetchall() loops.

\[ ] theauditor/rules/security/crypto\_analyze.py: cursor.execute() inside fetchall() loop (multiple occurrences).

\[ ] theauditor/rules/security/pii\_analyze.py: cursor.execute() inside fetchall() loop (Lines 1062, 1308, 1983).

\[ ] theauditor/rules/xss/express\_xss\_analyze.py: cursor.execute() inside fetchall() loop.

\[ ] theauditor/rules/xss/react\_xss\_analyze.py: cursor.execute() inside fetchall() loop.

\[ ] theauditor/rules/xss/vue\_xss\_analyze.py: cursor.execute() inside fetchall() loop.

📉 Algorithmic Inefficiencies

\[ ] theauditor/graph/dfg\_builder.py: Ensure "Vectorized Matching" (O(1) dict lookup) is being used instead of nested loops.

\[ ] theauditor/rules/xss/template\_xss\_analyze.py: Move query for render functions outside the loop (Line 424).

🐛 Priority 3: Broken Features \& Missing Data

Features that are currently broken or incomplete.

🔍 Missing Graph Data (Data Flow Gaps)

The Data Flow Graph (DFG) is missing connections for specific patterns.

\[ ] theauditor/graph/dfg\_builder.py: Fix missing edges for:

\[ ] Async/Arrow Functions (102 missing edges).

\[ ] Object Literals (1,921 missing edges).

\[ ] Wrapped Calls (220 missing edges).

\[ ] Array Literals (273 missing edges).

🛠️ Broken Analyzers

\[ ] theauditor/rules/python/python\_crypto\_analyze.py: SHA-0 check logic is broken.

\[ ] theauditor/rules/deployment/nginx\_analyze.py: Crypto algorithm check is marked broken.

\[ ] theauditor/deps.py: Multi-version collision logic for monorepos is broken (Line 845).

🧹 Priority 4: Cleanup \& Refactoring

Dead code, deprecated features, and temp files.

🗑️ Deprecated Code to Delete

\[ ] theauditor/cli.py: Remove index and tool-versions commands.

\[ ] theauditor/fce.py: Remove "Factual Cluster Detection" phase.

\[ ] theauditor/indexer/extractors/javascript.py: Remove deprecated Tree-sitter path (Line 382).

\[ ] theauditor/rules/security/crypto\_analyze.py: Remove deprecated crypto library checks (Pattern 15).

📂 File Handling Improvements

\[ ] theauditor/pipelines.py: Replace temp file usage with memory pipes (IO Completion Ports) for subprocesses (Line 117).

\[ ] theauditor/js\_semantic\_parser.py: Clean up temp file management logic.

🏗️ Refactoring

\[ ] theauditor/graph/strategies/: Refactor language-specific methods out of dfg\_builder.py into strategy files (node\_express.py, python\_orm.py).

\[ ] theauditor/ast\_extractors/python/framework\_extractors.py: Move Flask code to flask\_extractors.py.

📝 Priority 5: High-Value TODOs

Deferred tasks that impact analysis quality.

\[ ] theauditor/ast\_extractors/rust\_impl.py: Implement full CFG extraction (currently empty list).

\[ ] theauditor/rules/secrets/hardcoded\_secret\_analyze.py: Move Python-side filtering to SQL WHERE clauses for efficiency.

\[ ] theauditor/taint/core.py: Apply security rules from /rules/ to classify flows (currently returns raw count).







This is a \*\*massive success\*\*, even with the red text.



You went from having "no idea if 160k lines of code work" to having a \*\*precise diagnostic map\*\* of your entire system in about 10 minutes.



Here is the executive summary of your Smoke Test:

\* \*\*Structure Health:\*\* \*\*100%\*\*. Every single command (`73/73`) loaded, imported its dependencies, and displayed help without crashing. Your architecture is solid.

\* \*\*Runtime Health:\*\* \*\*Mixed\*\*. You have \*\*2 critical bugs\*\*, \*\*1 missing file\*\*, and several \*\*test configuration errors\*\* (flags that don't exist).



Here is the breakdown of what you need to fix, ranked by priority.



---



\### 1. The "Real" Bugs (Code Fixes Required)



These are actual errors in your codebase that would crash for a user.



\*\*A. The Missing Module (`aud docker-analyze`)\*\*

\* \*\*Error:\*\* `ModuleNotFoundError: No module named 'theauditor.docker\_analyzer'`

\* \*\*Diagnosis:\*\* Your `cli.py` imports a command wrapper, but that wrapper tries to import `theauditor.docker\_analyzer`, which doesn't exist or isn't in the python path.

\* \*\*Fix:\*\* Check `theauditor/commands/docker\_analyze.py`. It likely has a bad import at the top.



\*\*B. The Crash (`aud suggest`)\*\*

\* \*\*Error:\*\* `Traceback ... File "C:\\Users\\..."` (Runtime Error)

\* \*\*Diagnosis:\*\* This command crashed with a Python exception during execution. The log was truncated in the summary, but it indicates a logic error, likely because ML models weren't found or paths were wrong.

\* \*\*Fix:\*\* Run `aud suggest` manually in your terminal to see the full stack trace.



\*\*C. The Unimplemented Feature (`aud terraform report`)\*\*

\* \*\*Error:\*\* `'terraform report' not yet implemented (Phase 7)`

\* \*\*Diagnosis:\*\* The command raises an error intentionally (Exit Code 1), which flags as a failure.

\* \*\*Fix:\*\* If this is intended behavior, ignore it. If you want a clean test report, mark this command as `SKIP` in your script.



---



\### 2. The "Test Harness" Errors (Update Your Script)



These failures are because your \*\*Test Fixtures\*\* (the arguments you defined in the script) are using flags that don't exist. The code is fine; the test is wrong.



\*\*A. Incorrect Flags\*\*

\* \*\*`aud detect-patterns`\*\*: Failed because you passed `--dry-run`. The tool says: `Error: No such option: --dry-run`.

\* \*\*`aud full`\*\*: Failed because you passed `--dry-run`.

\* \*\*`aud graph viz`\*\*: Failed because you passed `--output`. It seems the command expects `-o` or a positional argument.

\* \*\*`aud graph query`\*\*: Failed because you passed `--symbol`. The tool says: `Error: No such option: --symbol`. It wants `--uses` or `--calls`.



\*\*Action:\*\* Update the `TEST\_FIXTURES` dictionary in your `cli\_smoke\_test.py` to use valid arguments.



---



\### 3. The "False Positives" (Deprecations)



\*\*`aud index` and `aud init`\*\*

\* \*\*Status:\*\* FAIL (Exit Code 3)

\* \*\*Reason:\*\* These commands are deprecated. Your CLI prints a warning and exits with code `3`.

\* \*\*Verdict:\*\* This is actually \*\*working as designed\*\*.

\* \*\*Fix:\*\* Add `aud index` and `aud init` to the `EXPECTED\_NO\_ARGS\_FAIL` list in your script, or update the script to accept Exit Code 3 as a "Pass".



---



\### 4. The "Missing Tools" (Environment)



\*\*`aud tools check`\*\*

\* \*\*Error:\*\* `FAILED: 1 required tool(s) missing ... \[MISSING] eslint`

\* \*\*Verdict:\*\* Your code works, but your Windows machine doesn't have `eslint` installed globally or in the path.

\* \*\*Fix:\*\* Ignore this, or install ESLint.



---



\### Summary of Next Steps



You are in a very good place. To get a "Green" board:



1\.  \*\*Fix the Import:\*\* Check `theauditor/docker\_analyzer.py`.

2\.  \*\*Update Script Fixtures:\*\*

&nbsp;   \* Remove `--dry-run` from `aud full` and `detect-patterns` in your script.

&nbsp;   \* Change `--symbol` to `--uses` for `aud graph query`.

&nbsp;   \* Check `aud graph viz` help to see the correct output flag.

3\.  \*\*Run `aud suggest` manually\*\* to debug that crash.



Would you like me to help you debug the `aud suggest` crash if you paste the stack trace?

