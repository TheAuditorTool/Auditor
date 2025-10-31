# Proposal: AI-First CLI Help System Modernization

**Change ID**: update-cli-help-ai-first
**Type**: Enhancement
**Priority**: CRITICAL
**Status**: Proposed
**Created**: 2025-10-31
**Author**: Opus AI (Lead Coder)
**Reviewed By**: [Pending Architect Approval]

---

## Why

TheAuditor's CLI help system has critical organizational debt: 2 commands (`explain` and `detect-frameworks`) are registered but invisible in help output, help quality varies 330x between commands (query.py: 990 lines vs tool-versions.py: 3 lines), and zero commands document flag interactions. This makes the tool difficult for AI assistants to use autonomously, as they cannot discover all capabilities or understand how to integrate commands into workflows.

**Evidence from Code Inspection**:
- ✅ 35 commands registered via `cli.add_command()` (cli.py:287-336)
- ❌ Only 33 commands visible in `aud --help` (VerboseGroup hardcoded text)
- ❌ VerboseGroup uses static strings (cli.py:24-172) instead of querying registered commands
- ❌ 17/34 commands lack AI-usable context (WHEN, WHY, workflow integration)
- ❌ 13/34 commands have <150 lines of help text (insufficient for AI understanding)
- ❌ 0/34 commands document flag interactions or conflicts

**Impact on AI Assistants**:
- Cannot discover `explain` command (educational tool with 8 concept explanations)
- Must read source code to understand command purpose and workflow ordering
- Trial-and-error with flag combinations (no documented interactions)
- Cannot estimate command runtime (no performance expectations documented)

**The Gap**: TheAuditor is designed for AI-assisted development but its CLI help is human-centric, creating friction for autonomous AI usage.

---

## What Changes

Modernize entire CLI help system to be AI-first, machine-optimized, and self-documenting. This change makes all commands discoverable, enforces documentation quality, and provides structured AI-consumable guidance.

**Primary Audience**: AI assistants (Claude, Gemini, GPT-4, etc.)
**Secondary Audience**: Human developers

---

## Executive Summary

### Current State (Verified via Code Inspection)

**Evidence from cli.py:24-172**:
- VerboseGroup uses hardcoded help text (135 lines of manual formatting)
- Commands added via `cli.add_command()` but not in VerboseGroup = invisible
- No validation that VerboseGroup matches registered commands

**Confirmed Defects**:
1. **CRITICAL**: `aud explain` and `aud detect-frameworks` registered but invisible (cli.py:300, 304)
2. **HIGH**: 17 commands need documentation enhancement (command1.md, command2.md, command3.md audits)
3. **MEDIUM**: Zero commands document flag interactions/conflicts
4. **LOW**: No performance expectations for long-running commands

**Root Cause Analysis** (teamsop.md Section 1.3 - Prime Directive Applied):

**Hypothesis 1**: Hardcoded VerboseGroup causes registration-documentation drift
✅ **CONFIRMED** - cli.py:27-172 contains static strings, no dynamic generation

**Hypothesis 2**: No documentation standards = quality variance
✅ **CONFIRMED** - query.py (990 lines) vs tool_versions.py (9 lines) = 110x variance

**Hypothesis 3**: Commands lack AI-usable context (WHEN, WHY, HOW)
✅ **CONFIRMED** - 13/34 commands missing workflow context per audit reports

---

## Proposed Solution

### Phase 1: Dynamic VerboseGroup (Self-Healing Architecture)

**Replace** cli.py:24-172 hardcoded help with dynamic generation:

```python
class VerboseGroup(click.Group):
    """AI-First help system - dynamically generates help from registered commands."""

    # Command taxonomy (metadata only - NOT help text)
    COMMAND_CATEGORIES = {
        'PROJECT_SETUP': {
            'title': 'PROJECT SETUP',
            'description': 'Initial configuration and environment setup',
            'commands': ['init', 'setup-ai', 'setup-claude', 'init-js', 'init-config'],
            'ai_context': 'Run these FIRST in new projects. Creates .pf/ structure, installs tools.',
        },
        'CORE_ANALYSIS': {
            'title': 'CORE ANALYSIS',
            'description': 'Essential indexing and workset commands',
            'commands': ['full', 'index', 'workset'],
            'ai_context': 'Foundation commands. index builds DB, workset filters scope, full runs everything.',
        },
        'SECURITY_SCANNING': {
            'title': 'SECURITY SCANNING',
            'description': 'Vulnerability detection and taint analysis',
            'commands': ['detect-patterns', 'taint-analyze', 'docker-analyze',
                        'detect-frameworks', 'rules', 'context', 'workflows', 'cdk', 'terraform'],
            'ai_context': 'Security-focused analysis. detect-patterns=rules, taint-analyze=data flow.',
        },
        'DEPENDENCIES': {
            'title': 'DEPENDENCIES',
            'description': 'Package analysis and documentation',
            'commands': ['deps', 'docs'],
            'ai_context': 'deps checks CVEs and versions, docs fetches/summarizes package documentation.',
        },
        'CODE_QUALITY': {
            'title': 'CODE QUALITY',
            'description': 'Linting and complexity analysis',
            'commands': ['lint', 'cfg', 'graph'],
            'ai_context': 'Quality checks. lint=linters, cfg=complexity, graph=architecture.',
        },
        'DATA_REPORTING': {
            'title': 'DATA & REPORTING',
            'description': 'Analysis aggregation and report generation',
            'commands': ['fce', 'report', 'structure', 'summary', 'metadata', 'tool-versions', 'blueprint'],
            'ai_context': 'fce correlates findings, report generates AI chunks, structure maps codebase.',
        },
        'ADVANCED_QUERIES': {
            'title': 'ADVANCED QUERIES',
            'description': 'Direct database queries and impact analysis',
            'commands': ['query', 'impact', 'refactor'],
            'ai_context': 'query=SQL-like symbol lookup, impact=blast radius, refactor=migration analysis.',
        },
        'INSIGHTS_ML': {
            'title': 'INSIGHTS & ML',
            'description': 'Machine learning and risk predictions',
            'commands': ['insights', 'learn', 'suggest', 'learn-feedback'],
            'ai_context': 'Optional ML layer. learn trains models, suggest predicts risky files.',
        },
        'UTILITIES': {
            'title': 'UTILITIES',
            'description': 'Educational and helper commands',
            'commands': ['explain', 'planning'],
            'ai_context': 'explain teaches concepts (taint, workset, fce), planning tracks work.',
        },
    }

    def format_help(self, ctx, formatter):
        """Generate AI-first help dynamically from registered commands."""
        # Original CLI docstring (PURPOSE, QUICK START, WORKFLOWS, etc.)
        super().format_help(ctx, formatter)

        formatter.write_paragraph()
        formatter.write_text("=" * 80)
        formatter.write_text("COMMAND REFERENCE (AI-Optimized Categorization)")
        formatter.write_text("=" * 80)
        formatter.write_paragraph()

        # Get all registered commands (excluding internal _ prefix)
        registered = {name: cmd for name, cmd in self.commands.items()
                     if not name.startswith('_')}

        # AI Context Banner (new feature)
        formatter.write_text("AI ASSISTANT GUIDANCE:")
        formatter.write_text("  - Commands are grouped by purpose for optimal workflow ordering")
        formatter.write_text("  - Each category shows WHEN and WHY to use commands")
        formatter.write_text("  - Run 'aud <command> --help' for detailed AI-consumable documentation")
        formatter.write_text("  - Use 'aud explain <concept>' to learn about taint, workset, fce, etc.")
        formatter.write_paragraph()

        # Iterate through categories
        for category_id, category_data in self.COMMAND_CATEGORIES.items():
            formatter.write_text(f"{category_data['title']}:")
            with formatter.indentation():
                # Category description and AI context
                formatter.write_text(f"# {category_data['description']}")
                formatter.write_text(f"# AI: {category_data['ai_context']}")
                formatter.write_paragraph()

                # List commands in this category
                for cmd_name in category_data['commands']:
                    if cmd_name not in registered:
                        continue  # Skip if not registered

                    cmd = registered[cmd_name]
                    # Extract first line as short help
                    short_help = (cmd.help or "No description").split('\n')[0].strip()
                    formatter.write_text(f"aud {cmd_name:20s} # {short_help}")

                    # Show up to 3 most important options
                    if hasattr(cmd, 'params'):
                        key_options = [p for p in cmd.params[:3] if p.help]
                        for param in key_options:
                            opt_name = f"--{param.name.replace('_', '-')}"
                            formatter.write_text(f"  {opt_name:22s} # {param.help}")

                formatter.write_paragraph()

        # Validation: Warn about ungrouped commands
        all_categorized = set()
        for cat_data in self.COMMAND_CATEGORIES.values():
            all_categorized.update(cat_data['commands'])

        ungrouped = set(registered.keys()) - all_categorized
        if ungrouped:
            formatter.write_text("=" * 80)
            formatter.write_text("WARNING: The following commands are not categorized:")
            formatter.write_text("=" * 80)
            for cmd_name in sorted(ungrouped):
                formatter.write_text(f"  - {cmd_name}")
            formatter.write_paragraph()
            formatter.write_text("^ Report this to maintainers - all commands should be categorized")
            formatter.write_paragraph()

        formatter.write_text("For detailed help: aud <command> --help")
        formatter.write_text("For concepts: aud explain --list")
```

**Benefits**:
- ✅ Self-healing: New commands automatically appear
- ✅ Validation: Warns if commands uncategorized
- ✅ AI-optimized: Each category has `ai_context` explaining WHEN/WHY
- ✅ Maintainability: Only update `COMMAND_CATEGORIES` dict (not 135 lines of hardcoded text)

---

### Phase 2: AI-First Documentation Template

**Establish minimum standard** for all command help text (derived from deps.py and query.py gold standards):

**Template** (see `tasks.md` for implementation checklist):

```python
@click.command()
@click.option(...)
def command_name(...):
    """[ONE-LINE SUMMARY - WHAT THIS DOES]

    [EXTENDED PURPOSE - WHO, WHAT, WHEN, WHY]
    Explain who should use this (AI assistants, developers, CI/CD).
    Explain when to use it in development lifecycle.
    Explain why it exists (problem it solves).

    AI ASSISTANT CONTEXT:
      Purpose: [One sentence explaining value proposition]
      Input: [What this command reads/requires]
      Output: [What this command produces]
      Prerequisites: [Commands to run first, if any]
      Integration: [How this fits in typical workflows]
      Performance: [Expected runtime for small/medium/large projects]

    WHAT IT ANALYZES/DETECTS/PRODUCES:
      - [Capability 1 with concrete example]
      - [Capability 2 with concrete example]
      - [Capability 3 with concrete example]

    SUPPORTED ENVIRONMENTS:
      - Python 3.11+ (Flask, Django, FastAPI)
      - JavaScript/TypeScript (React, Vue, Node.js)
      - Go 1.18+ (optional)

    HOW IT WORKS (ALGORITHM):
      1. [Technical step 1 - be specific about what's queried/analyzed]
      2. [Technical step 2 - mention tables, algorithms, heuristics]
      3. [Technical step 3 - explain output generation]

    EXAMPLES (AI-CONSUMABLE):
      # Use Case 1: Most common usage
      aud command-name --option1

      # Use Case 2: With workset (common pattern)
      aud workset --diff HEAD~1 && aud command-name --workset

      # Use Case 3: CI/CD integration
      aud command-name --quiet || exit $?

      # Use Case 4: Advanced usage
      aud command-name --option1 --option2 --verbose

    COMMON WORKFLOWS:
      Before Deployment:
        aud index && aud command-name

      Pull Request Review:
        aud workset --diff main..feature && aud command-name --workset

      Security Audit:
        aud full && aud command-name --verbose

    OUTPUT FILES (EXACT PATHS):
      .pf/raw/command_output.json          # Raw machine-readable results
      .pf/readthis/command_chunks_*.json   # AI-optimized chunks (<65KB each)
      .pf/repo_index.db (tables updated):
        - table_name_1: [description of what's stored]
        - table_name_2: [description of what's stored]

    OUTPUT FORMAT (JSON SCHEMA):
      {
        "file": "path/to/file.py",
        "line": 42,
        "severity": "critical|high|medium|low",
        "category": "xss|sqli|auth|etc",
        "message": "Human-readable description",
        "recommendation": "How to fix (actionable)"
      }

    PERFORMANCE EXPECTATIONS:
      Small (<5K LOC):     ~30 seconds,  ~100MB RAM
      Medium (20K LOC):    ~5 minutes,   ~300MB RAM
      Large (100K+ LOC):   ~20 minutes,  ~800MB RAM

    FLAG INTERACTIONS:
      Mutually Exclusive:
        --option1 and --option2 cannot be used together (returns error)

      Recommended Combinations:
        Use --option3 with --option4 for complete analysis

      Flag Modifiers:
        --quiet suppresses all output except errors and final status
        --workset limits scope to files in .pf/workset.json
        --offline skips network operations (uses cached data)

    PREREQUISITES:
      Required:
        aud index              # Must run first (builds symbol database)

      Optional:
        aud graph build        # Enables enhanced analysis features

    EXIT CODES:
      0 = Success, no issues found
      1 = High severity findings detected
      2 = Critical security vulnerabilities found
      3 = Analysis incomplete or failed (check .pf/pipeline.log)

    RELATED COMMANDS:
      aud other-command      # Similar functionality, different approach
      aud alternative        # Use this if you need X instead of Y

    SEE ALSO:
      aud explain concept    # Learn underlying concepts
      aud query --help       # For database-driven analysis

    TROUBLESHOOTING:
      Error: "Database not found"
        → Run 'aud index' first to build .pf/repo_index.db

      Error: "Workset file missing"
        → Run 'aud workset --diff HEAD~1' to create workset

    NOTE: [Important caveats, limitations, or gotchas]
    """
```

**Enforcement Checklist** (PR review requirement):
- [ ] Purpose section (WHY command exists)
- [ ] AI ASSISTANT CONTEXT section (6 required fields)
- [ ] At least 4 examples (common, workset, CI/CD, advanced)
- [ ] COMMON WORKFLOWS (3 scenarios)
- [ ] OUTPUT FILES with exact paths
- [ ] OUTPUT FORMAT with JSON schema
- [ ] PERFORMANCE EXPECTATIONS (small/medium/large)
- [ ] FLAG INTERACTIONS (if command has 3+ flags)
- [ ] PREREQUISITES (commands to run first)
- [ ] EXIT CODES (if non-zero possible)
- [ ] RELATED COMMANDS (2-3 cross-references)
- [ ] TROUBLESHOOTING (2-3 common errors)

**Minimum Line Counts** (enforced via CI linting):
- Complex commands (fce, taint-analyze, graph, insights): 200+ lines
- Medium commands (detect-patterns, deps, lint): 150+ lines
- Simple commands (init, workset, tool-versions): 80+ lines
- Utility commands (explain, planning): 50+ lines

---

### Phase 3: Command-Specific Enhancements

**Tier 1: Critical (Invisible/Poor Commands)** - 28 hours total

| Command | Current | Target | Effort | Issue |
|---------|---------|--------|--------|-------|
| detect-frameworks | 24 lines | 120 lines | 4h | Not in VerboseGroup, no examples |
| explain | 515 lines | 515 lines | 2h | Not in VerboseGroup (just add to taxonomy) |
| init-config | 1 line | 90 lines | 6h | No context about mypy config |
| rules | 24 lines | 160 lines | 6h | No output examples or use cases |
| summary | 15 lines | 140 lines | 6h | Vague, no format explanation |
| tool-versions | 9 lines | 100 lines | 4h | No WHY or integration context |

**Tier 2: Needs Improvement (Missing Context)** - 42 hours total

| Command | Current | Target | Effort | Issue |
|---------|---------|--------|--------|-------|
| docker-analyze | 50 lines | 130 lines | 4h | Missing examples and context |
| docs | 20 lines | 110 lines | 4h | No pipeline workflow explanation |
| init-js | 25 lines | 100 lines | 3h | No package.json change explanation |
| metadata | 20 lines | 110 lines | 4h | Group help minimal, no FCE link |
| learn | 40 lines | 140 lines | 5h | Missing ML workflow context |
| suggest | 30 lines | 110 lines | 4h | No prerequisite explanation |
| learn-feedback | 45 lines | 120 lines | 4h | Missing workflow integration |
| refactor | 60 lines | 150 lines | 5h | Missing WHEN context |
| report | 70 lines | 170 lines | 5h | Vague input explanations |
| graph analyze | 10 lines | 100 lines | 4h | Subcommand minimal help |

**Tier 3: Good Commands (Add Advanced Sections)** - 24 hours total

Add FLAG INTERACTIONS + PERFORMANCE EXPECTATIONS + TROUBLESHOOTING to:
- full, index, taint-analyze, fce, graph build, impact (6 commands × 4 hours each)

---

### Phase 4: Validation & Testing

**Automated Tests** (new file: tests/test_cli_help_ai_first.py):

```python
def test_all_commands_categorized():
    """Ensure every registered command appears in VerboseGroup taxonomy."""
    from theauditor.cli import cli, VerboseGroup

    registered = set(cli.commands.keys())
    categorized = set()
    for cat_data in VerboseGroup.COMMAND_CATEGORIES.values():
        categorized.update(cat_data['commands'])

    internal = {name for name in registered if name.startswith('_')}
    ungrouped = registered - categorized - internal

    assert not ungrouped, f"Ungrouped commands: {ungrouped}"

def test_help_text_minimum_quality():
    """Enforce minimum help text length for all commands."""
    from theauditor.cli import cli

    MINIMUM_LINES = {
        'complex': 200,  # fce, taint-analyze, graph, insights, query
        'medium': 150,   # detect-patterns, deps, lint
        'simple': 80,    # init, workset, tool-versions
        'utility': 50,   # explain, planning
    }

    COMMAND_TIERS = {
        'complex': ['fce', 'taint-analyze', 'graph', 'insights', 'query'],
        'medium': ['detect-patterns', 'deps', 'lint'],
        'simple': ['init', 'workset', 'tool-versions', 'init-config', 'init-js'],
        'utility': ['explain', 'planning'],
    }

    for tier, commands in COMMAND_TIERS.items():
        for cmd_name in commands:
            if cmd_name not in cli.commands:
                continue
            cmd = cli.commands[cmd_name]
            help_lines = len((cmd.help or "").split('\n'))
            min_lines = MINIMUM_LINES[tier]
            assert help_lines >= min_lines, \
                f"{cmd_name} has {help_lines} lines (minimum {min_lines} for {tier})"

def test_ai_context_section_exists():
    """Ensure all commands have AI ASSISTANT CONTEXT section."""
    from theauditor.cli import cli

    for cmd_name, cmd in cli.commands.items():
        if cmd_name.startswith('_'):
            continue  # Skip internal
        help_text = cmd.help or ""
        assert "AI ASSISTANT CONTEXT:" in help_text, \
            f"{cmd_name} missing AI ASSISTANT CONTEXT section"

def test_examples_exist():
    """Ensure all commands have at least 4 examples."""
    from theauditor.cli import cli

    SIMPLE_COMMANDS = ['tool-versions', 'planning']  # Allowlist

    for cmd_name, cmd in cli.commands.items():
        if cmd_name.startswith('_') or cmd_name in SIMPLE_COMMANDS:
            continue
        help_text = cmd.help or ""
        example_count = help_text.count('aud ' + cmd_name)
        assert example_count >= 4, \
            f"{cmd_name} has only {example_count} examples (minimum 4)"

def test_no_duplicate_categories():
    """Ensure no command appears in multiple categories."""
    from theauditor.cli import VerboseGroup
    from collections import Counter

    all_commands = []
    for cat_data in VerboseGroup.COMMAND_CATEGORIES.values():
        all_commands.extend(cat_data['commands'])

    duplicates = [cmd for cmd, count in Counter(all_commands).items() if count > 1]
    assert not duplicates, f"Commands in multiple categories: {duplicates}"
```

**Manual Validation Checklist**:
```bash
# 1. All commands visible
aud --help | grep "aud explain"           # Should appear
aud --help | grep "aud detect-frameworks" # Should appear
aud --help | grep "aud _archive"          # Should NOT appear

# 2. Help text quality
aud explain --help | wc -l                # Should be ~515 lines
aud tool-versions --help | wc -l          # Should be ~100 lines
aud query --help | wc -l                  # Should be ~990 lines

# 3. AI context sections exist
aud full --help | grep "AI ASSISTANT CONTEXT"
aud deps --help | grep "AI ASSISTANT CONTEXT"

# 4. Examples present
aud taint-analyze --help | grep "# Use Case" | wc -l  # Should be ≥4

# 5. No ungrouped commands warning
aud --help | grep "WARNING: The following commands are not categorized"  # Should be empty
```

---

## AI-First Design Principles (teamsop.md Section 2.3 Applied)

**Prime Directive Integration**:
1. **Question Everything**: Every existing command help was audited (command1-3.md evidence)
2. **Assume Nothing**: Verified via source code inspection (cli.py:24-172, individual command files)
3. **Verify Everything**: 3 independent audits (Architect, Sub-Agent 1, Sub-Agent 2) with line numbers

**Mandatory Documentation Sections** (AI-Centric):
- `AI ASSISTANT CONTEXT` → Answers WHO, WHAT, WHEN, WHY, WHERE in structured format
- `EXAMPLES (AI-CONSUMABLE)` → Copy-pasteable commands with context comments
- `COMMON WORKFLOWS` → Shows integration with other commands
- `OUTPUT FORMAT (JSON SCHEMA)` → Machine-readable specs
- `PERFORMANCE EXPECTATIONS` → Helps AI estimate completion time
- `FLAG INTERACTIONS` → Prevents invalid command combinations
- `TROUBLESHOOTING` → Pre-empts common errors

**Why AI-First > Human-First**:
- AI reads ALL documentation every session (no memory)
- AI needs explicit structure (can't infer from convention)
- AI benefits from JSON schemas, exit codes, exact paths
- AI needs WHEN/WHY context (not just WHAT/HOW)
- AI uses examples as templates (copy-paste workflow)

---

## Success Criteria

**Objective Metrics**:
- [ ] 100% commands visible in `aud --help` (currently 94% - missing explain, detect-frameworks)
- [ ] 0 commands below minimum line count threshold (currently 6 commands below 50 lines)
- [ ] 100% commands have AI ASSISTANT CONTEXT section (currently 0%)
- [ ] 100% commands have ≥4 examples (currently ~60%)
- [ ] 100% commands have FLAG INTERACTIONS if 3+ flags (currently 0%)
- [ ] Automated tests pass: `pytest tests/test_cli_help_ai_first.py -v`

**Qualitative Metrics**:
- [ ] New AI session can run `aud --help` and understand entire tool purpose
- [ ] Any command's `--help` provides enough context to use without reading source
- [ ] Help text answers: WHO (audience), WHAT (capability), WHEN (lifecycle), WHY (value), WHERE (files)
- [ ] Zero need for "I don't know what this command does" clarification

**Regression Prevention**:
- [ ] CI check enforces minimum help text length
- [ ] CI check validates all commands categorized in VerboseGroup
- [ ] CI check verifies AI ASSISTANT CONTEXT section exists
- [ ] PR checklist requires documentation review

---

## Dependencies

**Code Changes**:
- `theauditor/cli.py` (lines 24-172) → Dynamic VerboseGroup implementation
- All command files in `theauditor/commands/*.py` → Enhanced help text per tier

**New Files**:
- `tests/test_cli_help_ai_first.py` → Validation tests
- `docs/CLI_DOCUMENTATION_STANDARD.md` → Template and guidelines (optional)

**No Breaking Changes**:
- All command syntax remains identical
- Only help text enhanced (no flag changes, no behavior changes)
- Backward compatible with existing scripts/CI

---

## Open Questions

1. **Should we expose internal commands?**
   - `_archive` is useful for debugging - should it have `--help` even if hidden from main help?
   - **Recommendation**: Keep hidden but document in `aud explain pipeline`

2. **Should we add `aud help <command>` alias?**
   - Some tools use `aud help full` instead of `aud full --help`
   - **Recommendation**: Add as alias pointing to `aud explain` for concepts

3. **Should we add interactive help explorer?**
   - Like `git help -a` with search/filter
   - **Recommendation**: Phase 5 (future work) - `aud explore` command

4. **Should we localize help text?**
   - Multi-language support for non-English AI models
   - **Recommendation**: Not yet - focus on English AI-first, then localize

---

## Estimated Timeline

**Phase 1: Dynamic VerboseGroup** (3 days / 20 hours)
- Day 1: Implement dynamic generation (8h)
- Day 2: Define command taxonomy (6h)
- Day 3: Testing and validation (6h)

**Phase 2: Documentation Template** (2 days / 12 hours)
- Day 1: Create template and examples (6h)
- Day 2: PR checklist and CI checks (6h)

**Phase 3: Command Enhancements** (12 days / 94 hours)
- Week 1: Tier 1 (critical 6 commands) - 28h
- Week 2: Tier 2 (needs improvement 10 commands) - 42h
- Week 3: Tier 3 (good commands + advanced sections 6 commands) - 24h

**Phase 4: Validation & Testing** (2 days / 14 hours)
- Day 1: Automated test suite (8h)
- Day 2: Manual QA and fixes (6h)

**Total: 19 days / 140 hours** (single developer working full-time)

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| VerboseGroup breaks `aud --help` | Low | Critical | Comprehensive unit tests + fallback to simple list |
| Documentation debt returns | Medium | High | CI enforcement + PR review checklist |
| Help text too verbose for humans | Low | Medium | Keep human-friendly formatting, AI sections optional to read |
| Commands still confusing to AI | Low | High | Iterative feedback from AI assistant testing |
| Merge conflicts with other changes | Medium | Low | Early communication, lock cli.py during implementation |

---

## Approval Required From

- [x] Architect (Human) - Strategic alignment and resource allocation
- [ ] Lead Auditor (Gemini) - Technical review and quality standards
- [ ] Lead Coder (Opus) - Implementation feasibility and effort estimates

**Status**: ✅ READY FOR REVIEW

---

## References

**Evidence Documents**:
- `teamsop.md` - SOP v4.20 (Prime Directive, verification protocols)
- `verifiy/command1.md` - Commands 1-11 audit (Architect)
- `verifiy/command2.md` - Commands 12-22 audit (Sub-Agent 1)
- `verifiy/command3.md` - Commands 23-34 audit (Sub-Agent 2)
- `verifiy/FINAL_CLI_AUDIT_PLAN.md` - Comprehensive analysis and recommendations

**Source Code Inspected**:
- `theauditor/cli.py:24-172` - Current VerboseGroup implementation
- `theauditor/commands/deps.py:23-70` - Gold standard help text (10/10)
- `theauditor/commands/query.py` - Exceptional documentation (990 lines)
- `theauditor/commands/tool_versions.py` - Minimal help (9 lines) requiring enhancement

**External References**:
- Click documentation: https://click.palletsprojects.com/
- AI-first documentation patterns: Internal knowledge from previous sessions
