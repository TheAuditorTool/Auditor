# Design: AI-Optimized CLI Help Annotations

## Context

TheAuditor CLI uses Click framework with a CUSTOM `VerboseGroup` class that already has AI-oriented metadata.

**ACTUAL Current Architecture** (verified by reading `theauditor/cli.py`):

```
theauditor/cli.py:26-122
├── VerboseGroup(click.Group)           # Custom group class
│   ├── COMMAND_CATEGORIES (line 34-90) # Dict with category metadata
│   │   └── Each category has:
│   │       ├── 'title': str
│   │       ├── 'description': str
│   │       ├── 'commands': list[str]
│   │       └── 'ai_context': str       # EXISTING AI hint (not displayed)
│   │
│   ├── format_commands() (line 29-31)  # Suppresses default listing
│   └── format_help() (line 92-122)     # Custom categorized display
│
└── @click.group(cls=VerboseGroup)      # CLI uses custom class
```

**Key Discovery**: The `ai_context` field ALREADY exists but is NOT displayed to users. The infrastructure is there - we just need to:
1. Add `command_meta` sub-dict with `use_when`/`gives` per command
2. Modify `format_help()` to display these annotations

### Stakeholders

- **AI Agents** (Claude, GPT-4, Gemini) - Primary consumers, need discriminative routing
- **Human Developers** - Secondary consumers, need quick reference
- **CI/CD Scripts** - May parse help output (risk mitigation needed)
- **Documentation Generators** - May extract from docstrings

### Constraints

1. **Windows CP1252** - CLAUDE.md ABSOLUTE RULE: No emojis, ASCII-only
2. **Click Framework** - Must work within Click's help generation system
3. **Zero External Dependencies** - No new packages for help formatting
4. **Backward Compatibility** - Existing command behavior unchanged
5. **Token Efficiency** - AI context windows are precious (8K-128K tokens)

## Goals / Non-Goals

### Goals

1. Enable AI agents to select correct command >90% of the time via discriminative annotations
2. Prevent common AI mistakes via explicit Anti-Patterns sections
3. Enable few-shot learning via standardized "Copy These Patterns" examples
4. Reduce `aud query --help` from 400+ to <150 lines without losing essential info
5. Maintain ASCII-only output for Windows compatibility

### Non-Goals

1. Restructuring CLI command hierarchy (separate proposal)
2. Adding new commands (separate proposal)
3. Changing command behavior (only help output)
4. Internationalization (English-only)
5. Interactive help system (out of scope)

## Decisions

### Decision 1: Extend Existing COMMAND_CATEGORIES (NOT Create New Dict)

**What**: Add `command_meta` nested dict to existing `VerboseGroup.COMMAND_CATEGORIES` at `cli.py:34-90`.

**Why**:
- Infrastructure ALREADY exists - `COMMAND_CATEGORIES` with `ai_context` field proves AI-awareness intent
- Adding to existing structure is safer than creating parallel system
- Single source of truth maintained (no sync issues)
- `format_help()` already iterates this dict - minimal code change needed

**ACTUAL Implementation** (extends existing structure at `cli.py:71-77`):
```python
# BEFORE (current code at line 71-77):
'ADVANCED_QUERIES': {
    'title': 'ADVANCED QUERIES',
    'description': 'Direct database queries and impact analysis',
    'commands': ['explain', 'query', 'impact', 'refactor'],
    'ai_context': 'explain=comprehensive context, query=SQL-like...',
},

# AFTER (add command_meta sub-dict):
'ADVANCED_QUERIES': {
    'title': 'ADVANCED QUERIES',
    'description': 'Direct database queries and impact analysis',
    'commands': ['explain', 'query', 'impact', 'refactor'],
    'ai_context': 'explain=comprehensive context, query=SQL-like...',
    'command_meta': {  # NEW - per-command routing hints for AI
        'explain': {
            'use_when': 'Need to understand code before editing',
            'gives': 'Definitions, dependencies, hooks, call flows',
        },
        'query': {
            'use_when': 'Need specific facts (Who calls X?)',
            'gives': 'Exact file:line locations and relationships',
        },
        'impact': {
            'use_when': 'Assessing blast radius of changes',
            'gives': 'Upstream/downstream dependency counts',
        },
        'refactor': {
            'use_when': 'Detecting incomplete migrations',
            'gives': 'Broken imports, orphan code locations',
        },
    },
},
```

**Categories to Update** (all at `cli.py:34-90`):
- `PROJECT_SETUP` (line 35-40): setup-ai
- `CORE_ANALYSIS` (line 41-45): full, workset
- `SECURITY_SCANNING` (line 46-53): detect-patterns, taint-analyze, boundaries
- `DEPENDENCIES` (line 54-58): deps, docs
- `CODE_QUALITY` (line 59-64): lint, cfg, graph
- `DATA_REPORTING` (line 65-70): fce, report, structure
- `ADVANCED_QUERIES` (line 71-77): explain, query, impact, refactor
- `INSIGHTS_ML` (line 78-83): insights, learn, suggest
- `UTILITIES` (line 84-89): manual, planning

**Alternatives Considered**:

| Alternative | Rejected Because |
|-------------|------------------|
| Create separate COMMAND_METADATA dict | Creates sync problem with existing COMMAND_CATEGORIES |
| External YAML file | Adds I/O, complicates packaging, out-of-sync risk |
| Click decorators | Click doesn't support custom metadata natively |

### Decision 2: Modify Existing format_help() Method (NOT Create Custom Formatter)

**What**: Modify the existing `VerboseGroup.format_help()` method at `cli.py:92-122` to display annotations.

**Why**:
- `VerboseGroup` ALREADY has custom `format_help()` that iterates `COMMAND_CATEGORIES`
- We're already bypassing Click's default formatter - no need for another subclass
- Minimal change to existing code (~10 lines added)
- No new class needed

**ACTUAL Implementation** (modify existing method at `cli.py:102-119`):
```python
# BEFORE (current code at line 102-119):
for category_id, category_data in self.COMMAND_CATEGORIES.items():
    formatter.write_text(f"  {category_data['title']}:")
    for cmd_name in category_data['commands']:
        if cmd_name not in registered:
            continue
        cmd = registered[cmd_name]
        # ... truncation logic ...
        formatter.write_text(f"    {cmd_name:20s} {short_help}")
    formatter.write_paragraph()

# AFTER (add annotation display - insert after line 119):
for category_id, category_data in self.COMMAND_CATEGORIES.items():
    formatter.write_text(f"  {category_data['title']}:")
    for cmd_name in category_data['commands']:
        if cmd_name not in registered:
            continue
        cmd = registered[cmd_name]
        # ... truncation logic (unchanged) ...
        formatter.write_text(f"    {cmd_name:20s} {short_help}")

        # NEW: Add AI routing annotations if available
        cmd_meta = category_data.get('command_meta', {}).get(cmd_name, {})
        if 'use_when' in cmd_meta:
            formatter.write_text(f"                          > USE WHEN: {cmd_meta['use_when']}")
        elif 'run_when' in cmd_meta:
            formatter.write_text(f"                          > RUN: {cmd_meta['run_when']}")
        if 'gives' in cmd_meta:
            formatter.write_text(f"                          > GIVES: {cmd_meta['gives']}")

    formatter.write_paragraph()
```

**WHY 26-SPACE INDENT**: Aligns annotations under command description column (20-char cmd name + 4-space initial indent + 2 padding).

### Decision 3: Docstring Convention for Anti-Patterns

**What**: Add `ANTI-PATTERNS (Do NOT Do This)` section to command docstrings with specific format.

**Why**:
- Click extracts full docstring for `--help` output
- Docstrings are the canonical place for detailed help
- No code changes needed beyond docstring edits

**Format Convention**:
```python
@click.command()
def query():
    """Query code relationships from indexed database.

    [... existing help content ...]

    ANTI-PATTERNS (Do NOT Do This)
    ------------------------------
      X  aud query "how does auth work?"
         -> Use 'aud explain' for conceptual questions

      X  aud query --symbol "foo"
         -> Always add --show-callers or --show-callees

    EXAMPLES (Copy These Patterns)
    ------------------------------
      # Find where a function is used
      aud query --symbol authenticate --show-callers

      # JSON output for AI parsing
      aud query --symbol validate --format json

    OUTPUT FORMAT
    -------------
    Text mode:
      Symbol: authenticate (function)
      File: src/auth.py:42
      Callers:
        - src/api/login.py:15 -> login_handler()

    JSON mode (--format json):
      {"symbol": "authenticate", "type": "function", ...}
    """
```

**Formatting Rules**:
1. Section headers: ALL CAPS with dashes underline
2. Anti-patterns: `X` prefix, `->` for redirect suggestion
3. Examples: `#` comment describes use case, then command
4. Output format: Actual example output (truncated for brevity)

### Decision 4: `aud query --help` Content Relocation

**What**: Move verbose content from `aud query --help` to `aud manual` concepts.

**Content Migration**:

| Current Section in query --help | Move To | Reason |
|--------------------------------|---------|--------|
| DATABASE SCHEMA REFERENCE | `aud manual database` | Reference material, not routing |
| TROUBLESHOOTING | `aud manual troubleshooting` | Not needed for command selection |
| ARCHITECTURE explanation | `aud manual architecture` | Educational, not operational |
| PERFORMANCE CHARACTERISTICS | `aud manual performance` | Nice-to-know, not need-to-know |
| MANUAL DATABASE QUERIES | `aud manual database` | Advanced usage |
| Redundant SQL examples | `aud manual database` | Duplicate information |

**Retained in query --help**:
1. One-line description
2. ARGUMENTS section (all flags with descriptions)
3. FLAGS section (all options)
4. ANTI-PATTERNS section (NEW)
5. EXAMPLES (Copy These Patterns) (5-6 examples)
6. OUTPUT FORMAT section

**New Manual Concepts** (added to `theauditor/commands/manual.py`):
```python
EXPLANATIONS = {
    # ... existing ...
    'database': {
        'title': 'Database Schema Reference',
        'summary': 'Tables, indexes, and query patterns for advanced usage',
        'explanation': '[Content migrated from query --help]',
    },
    'troubleshooting': {
        'title': 'Troubleshooting Guide',
        'summary': 'Common errors and solutions',
        'explanation': '[Content migrated from query --help]',
    },
    'architecture': {
        'title': 'CLI Architecture',
        'summary': 'How query engine, databases, and commands interact',
        'explanation': '[Content migrated from query --help]',
    },
}
```

### Decision 5: ASCII-Only Enforcement

**What**: Automated check that all docstrings are ASCII-only.

**Why**: Windows CP1252 encoding crashes on Unicode characters (CLAUDE.md ABSOLUTE RULE).

**Implementation**: Pre-commit hook or test case.

```python
# tests/test_cli_ascii.py
import ast
import glob

def test_cli_docstrings_ascii_only():
    """Ensure all CLI docstrings are ASCII-only for Windows compatibility."""
    cli_files = glob.glob('theauditor/commands/*.py') + ['theauditor/cli.py']

    for filepath in cli_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                docstring = ast.get_docstring(node)
                if docstring:
                    try:
                        docstring.encode('ascii')
                    except UnicodeEncodeError as e:
                        raise AssertionError(
                            f"Non-ASCII character in {filepath}:{node.lineno}: {e}"
                        )
```

## Risks / Trade-offs

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Custom formatter breaks on Click upgrade | HIGH | LOW | Pin Click version, test on upgrade |
| CI scripts break on new help format | MEDIUM | MEDIUM | Search `.github/` for help parsing patterns |
| Docstring changes cause test failures | LOW | LOW | No existing docstring tests |
| Manual content gets stale | MEDIUM | MEDIUM | Add "Last Updated" timestamp |
| AI still hallucinates despite Anti-Patterns | MEDIUM | MEDIUM | Test with multiple AI models |

## Migration Plan

### Phase 1: Infrastructure (Tasks 1.1-1.4)
1. Add `COMMAND_METADATA` dict
2. Create `AIOptimizedHelpFormatter` class
3. Wire formatter to CLI group
4. Add ASCII test case

### Phase 2: Root Help (Tasks 2.1-2.2)
1. Populate `COMMAND_METADATA` for all 42 commands
2. Test root help output format

### Phase 3: Subcommand Updates (Tasks 3.1-3.6)
1. Update `explain.py` docstring
2. Update `query.py` docstring (major trim + additions)
3. Update `structure.py` docstring
4. Update `taint.py` docstring
5. Update `graph.py` docstring
6. Update `manual.py` with new concepts

### Phase 4: Validation (Tasks 4.1-4.3)
1. Verify line counts
2. Test with AI agents
3. Update help_ai.md with results

### Rollback Plan

1. Revert `cli.py` changes (removes formatter)
2. Revert individual docstring changes
3. Rollback is fully reversible via `git revert`

## Open Questions

1. **Q**: Should `COMMAND_METADATA` be in separate file (e.g., `cli_metadata.py`)?
   **A**: Keep in `cli.py` for simplicity. Revisit if file grows >1000 lines.

2. **Q**: Should Anti-Patterns be extracted to structured data like `COMMAND_METADATA`?
   **A**: No - Click only consumes docstrings. Keep in docstrings for simplicity.

3. **Q**: Which AI models to test with?
   **A**: Claude (primary), GPT-4, Gemini 1.5 Pro. Measure correct command selection rate.

4. **Q**: Should we add `--ai` flag for AI-optimized output format?
   **A**: Out of scope for this proposal. Consider for future work.
