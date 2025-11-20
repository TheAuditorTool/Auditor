## Multi-hop Investigation Report

**Date:** 2025-10-19  
**Analyst:** Codex (GPT-5)  
**Scope:** Stage 3 multi-hop / cross-file taint propagation for Plant project (`verifiy/repo_index.db`)

### 1. Pipeline Symptoms
- Latest `aud full` run finished Stage 3 in **1.7 s** with **29 taint paths** – identical to the same-file count – confirming no cross-file propagation (`verifiy/pipeline.log:140-168`).
- Controller → service flow at `backend/src/controllers/account.controller.ts:34` → `backend/src/services/account.service.ts:93` should be reported but is absent in `.pf/raw/taint_analysis.json`.

### 2. Evidence Collected
1. **Database rows exist for the cross-file call**  
   ```python
   ('AccountController.create', 'accountService.createAccount', 'data', 'req.body', 'backend/src/services/account.service.ts')
   ('AccountController.create', 'accountService.createAccount', '_createdBy', "'system'", 'backend/src/services/account.service.ts')
   ```  
   (`function_call_args`, file: `backend/src/controllers/account.controller.ts`, line: 34 – confirmed via inline sqlite query).

2. **Service definitions stored with PascalCase name**  
   `symbols` table row: `('AccountService.createAccount', 'backend/src/services/account.service.ts', 50)`  
   `function_call_args` rows inside the service also use `AccountService.createAccount` as `caller_function`.

3. **Stage 2 query misses the rows**  
   Code at `theauditor/taint/interprocedural.py:126-144` issues  
   ```python
   cursor.execute(query, (current_file,
                          current_func,
                          f"%.{current_func}",
                          current_var,
                          f"%{current_var}%"))
   ```  
   When the worklist `current_func` equals `accountService.createAccount`, both equality and LIKE predicates fail to match the PascalCase `caller_function`, so the worklist never traverses into the service.

4. **Stage 3 suffers from the same mismatch**  
   The CFG worklist query at `theauditor/taint/interprocedural.py:302-307` repeats the same parameter tuple, so the grouped call processing receives an empty result. As a consequence, no entries are added to the Stage 3 worklist, and the service CFG is never analyzed.

5. **Function definition lookup also fails**  
   `PathAnalyzer` setup uses  
   ```python
   cursor.execute(func_def_query, (current_file, current_func))
   ```  
   (`theauditor/taint/interprocedural.py:251-254`). Because `symbols` stores the canonical class method name, the lookup returns `None`, causing the intra-file sink guard to skip the ORM block entirely.

6. **Sink fallback cannot compensate**  
   Even if the traversal reached the service, the recorded `argument_expr` for the ORM call is `'{'` (due to object literal serialization), so the fallback `LIKE` check at `theauditor/taint/interprocedural.py:285-288` would not match `req.body`.

### 3. Root Cause
1. The worklist state carries the invocation name (`accountService.createAccount`) extracted from the controller callsite.
2. All canonical entries in `symbols` and `function_call_args` inside the service use the class-qualified name `AccountService.createAccount`.
3. Every downstream lookup reuses `current_func` without normalization, so no Stage 2 or Stage 3 queries find the service records.
4. Because no rows are returned, no cross-file propagation occurs and sink checks never execute for the service body.

### 4. Impact
- Stage 3 multi-hop yields zero cross-file paths despite database completeness.
- Controller/service flows (the project’s “moonshot”) are totally silent, blocking security coverage beyond same-file heuristics.
- Any other call where caller and callee use different casing or qualification suffers the same blind spot.

### 5. Remediation Plan
1. **Normalize function identifiers before every query.**  
   Resolve the canonical function name (and file) once per worklist step using:
   - `symbols` lookup by signature (`AccountService.createAccount`)
   - fallback to `function_call_args.callee_file_path` for file resolution.
2. **Store both canonical and invocation aliases in worklist state.**  
   Maintain tuple `(display_name, canonical_name, file)` so lookups can use canonical values while reports keep the original surface form.
3. **Update Stage 2 and Stage 3 query parameters.**  
   - Equality clause should target canonical name.
   - LIKE clause should be constructed from canonical name when searching `%.{name}`.
4. **Ensure `PathAnalyzer` receives canonical names.**  
   Pass the resolved symbol name into the CFG analyzer so the symbols query at `interprocedural.py:251-254` succeeds.
5. **Tighten argument matching for sink fallbacks.**  
   Where possible, rely on `function_call_args` parameter mapping instead of substring heuristics (planned after name fix validation).

### 6. Next Steps
- Implement normalization helpers shared by Stage 2/Stage 3 worklists.
- Re-run `aud full` on Plant to confirm cross-file vulnerabilities are now emitted.
- Extend regression coverage to catch future name drift (unit tests around mixed-case class methods).

_End of report._
