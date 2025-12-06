# TheAuditor Pre-Flight Check Report

**Date:** 2025-12-06 17:32:22
**Total Duration:** 155.9s
**Index Duration:** 0.0s

**Total Tests:** 91
**Passed:** 89
**Failed:** 2

## FAILURES DETECTED

### Failure 1: Impact analysis by symbol

- **Command:** `aud impact --symbol main`
- **Phase:** invoke
- **Exit Code:** 1
- **Duration:** 1.50s

**Error:**
```
Error: Ambiguous symbol - multiple matches found
```

**Stderr:**
```
Found 41 symbols matching 'main':
  1. main (function) at scripts/ast_modernizer_v4.py:679
  2. main (function) at scripts/ast_walk_to_filecontext.py:660
  3. main (function) at scripts/cleanup_rule_metadata.py:124
  4. main (function) at scripts/cli_smoke_test.py:1079
  5. main (function) at scripts/fix_ast_v3.py:332
  6. main (function) at scripts/fix_broken_extractors.py:85
  7. main (function) at scripts/fix_forward_refs.py:57
  8. main (function) at scripts/fix_future_annotations.py:63
  9. main (function) at scripts/fix_recursive_tree_walks.py:287
  10. main (function) at scripts/fix_stderr_migration.py:263
  ... and 31 more

Use --file and --line to specify exact location, or refine pattern.
Error: Ambiguous symbol - multiple matches found

```

---

### Failure 2: Taint analysis

- **Command:** `aud taint`
- **Phase:** invoke
- **Exit Code:** 10
- **Duration:** 1.38s

**Error:**
```
[32m17:32:22[0m | [31mERROR   [0m | [36mtheauditor.taint.core:trace_taint:535[0m - [31m[SCHEMA FIX] Please re-run the command[0m
```

**Stderr:**
```
[32m17:32:21[0m | [37mINFO    [0m | [36mtheauditor.utils.memory:get_recommended_memory_limit:121[0m - [37mSystem RAM: 31965MB, Using: 19179MB (60% of total)[0m
[32m17:32:22[0m | [31mERROR   [0m | [36mtheauditor.taint.core:trace_taint:526[0m - [31m[SCHEMA STALE] Schema files have changed but generated code is out of date![0m
[32m17:32:22[0m | [31mERROR   [0m | [36mtheauditor.taint.core:trace_taint:529[0m - [31m[SCHEMA STALE] Regenerating code automatically...[0m
[32m17:32:22[0m | [37mINFO    [0m | [36mtheauditor.indexer.schemas.codegen:write_generated_code:352[0m - [37mGenerated code written to C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas[0m
[32m17:32:22[0m | [31mERROR   [0m | [36mtheauditor.taint.core:trace_taint:534[0m - [31m[SCHEMA FIX] Generated code updated successfully[0m
[32m17:32:22[0m | [31mERROR   [0m | [36mtheauditor.taint.core:trace_taint:535[0m - [31m[SCHEMA FIX] Please re-run the command[0m

```

---


## Test Summary by Phase

| Phase | Total | Passed | Failed |
|-------|-------|--------|--------|
| setup | 3 | 3 | 0 |
| invoke | 35 | 33 | 2 |
| help | 53 | 53 | 0 |