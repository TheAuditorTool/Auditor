# Proposal: Optimize CLI Help Content for AI Consumption

## Why

TheAuditor's `--help` content is written for humans but **AI assistants are the primary users**. Claude Code, Gemini, and other AI tools parse these help texts to understand how to use commands. Current help text has:

1. **Outdated references** - 91 occurrences of "aud index" across 19 files (deprecated command)
2. **Missing AI context** - 7 command files lack AI ASSISTANT CONTEXT sections
3. **Terse/minimal docstrings** - Many commands have placeholder-quality help
4. **Unverified examples** - Examples may not actually work
5. **No workflow guidance** - Help says WHAT, not HOW or WHEN to use

This ticket focuses EXCLUSIVELY on `--help` content across all 38 command files. We verify every claim against actual tool behavior, optimize for AI parsing, and write detailed actionable help.

**This is written BY AI FOR AI.** The Architect built this tool for us. Time to take ownership.

## What Changes

### Content Modernization (All 38 Command Files)
- Replace all 91 "aud index" references with "aud full" (see Appendix A)
- Verify every example actually works
- Verify every command/option described actually exists
- Fix descriptions that don't match reality

### AI ASSISTANT CONTEXT (Add to 7 Missing Files)
Files verified missing AI ASSISTANT CONTEXT (excludes __init__.py, config.py, manual_lib*.py):
1. `cfg.py` - CFG group + 2 subcommands (analyze, viz)
2. `deps.py` - Dependency analysis command
3. `planning.py` - Planning group + 14 subcommands
4. `query.py` - Database query command
5. `tools.py` - Tools group + 3 subcommands (list, check, report)
6. `_archive.py` - Internal archive command
7. `index.py` - Deprecated command (needs deprecation-focused context)

### Content Quality (All Commands)
- Rewrite terse docstrings to be detailed and actionable
- Add "WHEN to use this" guidance
- Add workflow context (what comes before/after)
- Cross-reference with aud manual topics
- Make examples copy-paste ready

## Scope

**In Scope:**
- 38 command files in `theauditor/commands/`
- ~80 total commands (standalone + subcommands)
- Docstrings, examples, AI ASSISTANT CONTEXT sections
- Cross-referencing with actual tool behavior

**Out of Scope:**
- Manual entries (separate ticket: optimize-manual-content-v2)
- Rich formatting code (already complete)
- New features or functionality

## Execution Model

**6 Parallel AI Teams** - Each team handles one track independently:

| Track | Focus | Files | Commands |
|-------|-------|-------|----------|
| 1 | Core Pipeline | 5 files | full, taint, detect-patterns, index, manual |
| 2 | Graph/Flow | 4 files | graph (5 sub), graphql (3 sub), cfg (2 sub), fce |
| 3 | Security/IaC | 5 files | boundaries, docker, workflows, terraform (3 sub), cdk |
| 4 | Code Analysis | 6 files | query, explain, impact, deadcode, refactor, context |
| 5 | Infrastructure | 7 files | deps, tools (3 sub), setup, workset, rules, lint, docs |
| 6 | Planning/ML | 6 files | planning (14 sub), session (5 sub), ml (3), metadata (3), blueprint, detect-frameworks |

Each track is independent. No blocking dependencies between tracks.

## Verification Protocol

For EVERY command touched, the AI team MUST:

1. **Run the command** - `aud <command> --help` to see current state
2. **Verify existence** - Does this command actually exist? Do the options work?
3. **Cross-reference** - Read the actual implementation to verify descriptions
4. **Test examples** - Run every example in the help text
5. **Check prerequisites** - Are the stated prerequisites correct?

## Success Criteria

- [ ] Zero "aud index" references in any help text (except index.py deprecation notice)
- [ ] All 38 command files have AI ASSISTANT CONTEXT (excluding __init__.py, config.py, manual_lib*.py)
- [ ] All examples are verified working
- [ ] All descriptions match actual tool behavior
- [ ] All cross-references to manual topics are valid

## Files Affected

**Primary (38 command files):**
- `theauditor/commands/*.py` - All command docstrings

**Reference (read-only for verification):**
- `theauditor/cli.py:141-350` - RichCommand class (parses docstring sections)
- `.auditor_venv/.theauditor_tools/agents/*.md` - Workflow guidance
- `theauditor/pipeline/*.py` - Verify pipeline descriptions
- `.pf/repo_index.db` - Verify database references

## Reference Implementation

`theauditor/commands/full.py:68-192` is the gold standard for CLI help content. All AI teams should study this file before modifying others. It demonstrates:
- AI ASSISTANT CONTEXT section (lines 116-122)
- DESCRIPTION with detailed breakdown (lines 97-115)
- EXAMPLES with inline comments (lines 124-129)
- COMMON WORKFLOWS with named scenarios (lines 131-143)
- OUTPUT FILES with paths (lines 144-150)
- EXIT CODES (lines 157-161)
- TROUBLESHOOTING section (lines 173-187)

---

## Appendix A: Complete "aud index" Reference List (91 occurrences)

### blueprint.py (2 refs)
| Line | Context |
|------|---------|
| 60 | `Prerequisites: aud index (populates database)` |
| 117 | `aud index           # Minimum (basic structure only)` |

### boundaries.py (1 ref)
| Line | Context |
|------|---------|
| 69 | `Prerequisites: aud index (populates call graph for distance calculation)` |

### cdk.py (3 refs)
| Line | Context |
|------|---------|
| 31 | `Prerequisites: aud index (extracts CDK constructs)` |
| 55 | `aud index` |
| 116 | `Run 'aud index' first to populate cdk_constructs table` |

### deadcode.py (8 refs)
| Line | Context |
|------|---------|
| 43 | `Prerequisites: aud index (populates import graph in database)` |
| 78 | `aud index && aud deadcode` |
| 94 | `aud index && aud deadcode --format json --save cleanup_targets.json` |
| 149 | `aud index              # Populates symbols and refs tables` |
| 160 | `aud index              # Populates import graph in database` |
| 170 | `Run 'aud index' first to create .pf/repo_index.db` |
| 183 | `Re-run 'aud index' to refresh database` |

### detect_frameworks.py (14 refs)
| Line | Context |
|------|---------|
| 3 | `This command reads from the frameworks table populated by 'aud index'.` |
| 23 | `Reads framework metadata from the database (populated during 'aud index')` |
| 31 | `Prerequisites: aud index (must run first to populate database)` |
| 51 | `Queries frameworks table (populated by 'aud index' extractors)` |
| 58 | `aud index && aud detect-frameworks` |
| 67 | `aud index && aud detect-frameworks && aud blueprint --format json` |
| 71 | `aud index && aud detect-frameworks && aud blueprint` |
| 112 | `aud index              # Must run first to populate frameworks table` |
| 119 | `Database not found (run 'aud index' first)` |
| 123 | `aud index              # Populates frameworks table (run first)` |
| 133 | `Run 'aud index' first to create .pf/repo_index.db` |
| 136 | `Check 'aud index' output for errors` |
| 141 | `Re-run 'aud index' to refresh database` |
| 145 | `To refresh framework detection, run 'aud index' again.` |

### docker_analyze.py (9 refs)
| Line | Context |
|------|---------|
| 38 | `Input: .pf/repo_index.db (Dockerfile contents indexed by 'aud index')` |
| 40 | `Prerequisites: aud index (populates database with Dockerfile contents)` |
| 76 | `Reads Dockerfile content from database (indexed by 'aud index')` |
| 85 | `aud index && aud docker-analyze` |
| 101 | `aud index && aud docker-analyze --severity high --check-vulns` |
| 157 | `aud index              # Populates database with Dockerfile contents` |
| 169 | `aud index              # Extracts Dockerfile contents to database` |
| 180 | `Run 'aud index' first to populate .pf/repo_index.db` |
| 183 | `Check 'aud index' output for parsing errors` |

### graph.py (4 refs)
| Line | Context |
|------|---------|
| 26 | `Prerequisites: aud index (populates refs and calls tables)` |
| 48 | `aud index` |
| 67 | `aud index     # Populates refs/calls tables` |
| 356 | `Prerequisites: aud index, aud graph build` |

### graphql.py (3 refs)
| Line | Context |
|------|---------|
| 26 | `Prerequisites: aud index (extracts SDL schemas + resolver patterns)` |
| 49 | `aud index                    # Extract SDL + resolvers` |
| 65 | `aud index        # Extracts GraphQL schemas and resolvers` |

### impact.py (4 refs)
| Line | Context |
|------|---------|
| 114 | `Prerequisites: aud index (populates symbol table and refs)` |
| 139 | `Note: Requires 'aud index' to be run first.` |
| 210 | `Run 'aud index' to rebuild the index` |
| 282 | `Ensure the file has been indexed with 'aud index'.` |

### index.py (18 refs - DEPRECATION FILE)
| Line | Context |
|------|---------|
| 31 | `DEPRECATION NOTICE: 'aud index' is DEPRECATED` |
| 34 | `The 'aud index' command no longer provides sufficient data fidelity` |
| 46 | `Running 'aud index' will execute the COMPLETE audit pipeline` |
| 60 | `aud index                    # Phase 1 only` |
| 74 | `OLD: aud index && aud taint-analyze && aud deadcode` |
| 78 | `OLD: aud index --print-stats` |
| 82 | `OLD: aud index --exclude-self` |
| 86 | `The following flags from the old 'aud index' are NOT supported` |
| 94 | `OLD 'aud index': ~10-30 seconds (Phase 1 only)` |
| 103 | `This deprecation warning will be removed in v2.0 when 'aud index' is fully` |
| 120 | `The 'aud index' command is DEPRECATED and now runs 'aud full' instead.` |
| 122 | `WHY: 'aud index' alone no longer provides sufficient data fidelity` |
| 133 | `Replace 'aud index && aud taint-analyze' with just 'aud full'` |
| 137 | `This warning will be removed in v2.0 when 'aud index' is fully retired.` |

### manual_lib02.py (6 refs)
| Line | Context |
|------|---------|
| 928 | `Works seamlessly with aud index / aud full workflow` |
| 961 | `aud index && aud planning verify-task 1 1` |
| 967 | `aud index && aud planning verify-task 1 1 --auto-update` |
| 997 | `aud index && aud planning verify-task 1 1 --verbose` |
| 1258 | `'aud index' parses CDK code (AST extraction)` |
| 1323 | `SDL Extraction (during 'aud index')` |

### planning.py (5 refs)
| Line | Context |
|------|---------|
| 61 | `Works seamlessly with aud index / aud full workflow` |
| 71 | `aud index && aud planning verify-task 1 1 --verbose` |
| 80 | `aud index && aud planning verify-task 1 1` |
| 86 | `aud index && aud planning verify-task 1 1 --auto-update` |
| 122 | `Run 'aud index' to build repo_index.db before verify-task` |

### refactor.py (4 refs)
| Line | Context |
|------|---------|
| 90 | `Prerequisites: aud index (for code symbol database)` |
| 151 | `aud index && aud refactor --migration-limit 1` |
| 196 | `aud index              # Populates code reference database` |
| 208 | `aud index              # Populates code reference database` |

### taint.py (1 ref)
| Line | Context |
|------|---------|
| 335 | `Fix: Run 'aud index' to rebuild database with correct schema.` |

### terraform.py (4 refs)
| Line | Context |
|------|---------|
| 28 | `Input: *.tf files (indexed by 'aud index')` |
| 30 | `Prerequisites: aud index (extracts Terraform resources)` |
| 52 | `aud index` |
| 97 | `Must run 'aud index' first to extract Terraform resources` |
| 236 | `Run 'aud index' first to extract Terraform resources` |

### workflows.py (4 refs)
| Line | Context |
|------|---------|
| 32 | `Input: .github/workflows/*.yml files (indexed by 'aud index')` |
| 34 | `Prerequisites: aud index (extracts workflow files)` |
| 50 | `aud index` |
| 107 | `Must run 'aud index' first to extract workflows` |

### workset.py (5 refs)
| Line | Context |
|------|---------|
| 38 | `Prerequisites: aud index (for dependency expansion), git repository (for --diff)` |
| 104 | `aud index && aud workset --diff origin/main..HEAD && aud full --workset` |
| 159 | `aud index              # Populates refs table for dependency expansion` |
| 171 | `aud index              # Must run first to populate import graph` |
| 198 | `Verify 'aud index' ran successfully (check .pf/repo_index.db)` |

---

## Appendix B: Files Missing AI ASSISTANT CONTEXT

Verified via: `for f in theauditor/commands/*.py; do grep -q "AI ASSISTANT CONTEXT" "$f" || echo "$f"; done`

| File | Type | Needs AI CONTEXT |
|------|------|------------------|
| `__init__.py` | Package init | NO (not a command) |
| `_archive.py` | Internal command | YES |
| `cfg.py` | Group + 2 subs | YES |
| `config.py` | Not a command | NO |
| `deps.py` | Standalone | YES |
| `index.py` | Deprecated | YES (deprecation-focused) |
| `manual_lib01.py` | Library helper | NO (not a command) |
| `manual_lib02.py` | Library helper | NO (not a command) |
| `planning.py` | Group + 14 subs | YES |
| `query.py` | Standalone | YES |
| `tools.py` | Group + 3 subs | YES |

**Total requiring AI ASSISTANT CONTEXT: 7 files**
