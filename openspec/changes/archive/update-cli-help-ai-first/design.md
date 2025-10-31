# Technical Design: AI-First CLI Help System Modernization

**Change ID**: update-cli-help-ai-first
**Status**: Proposed
**Last Updated**: 2025-10-31
**Author**: Opus AI (Lead Coder)

---

## Architecture Overview

### Current Architecture (Problematic)

```
┌─────────────────────────────────────────────────────────────┐
│                       theauditor/cli.py                        │
├─────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ VerboseGroup (lines 24-172)                          │    │
│  ├──────────────────────────────────────────────────────┤    │
│  │ • Hardcoded help text (135 lines of strings)         │    │
│  │ • Manual formatting with formatter.write_text()      │    │
│  │ • NO connection to registered commands               │    │
│  │ • NO validation of completeness                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                             │                                  │
│                             ▼                                  │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ @click.group(cls=VerboseGroup)                       │    │
│  │ def cli(): ...                                       │    │
│  └──────────────────────────────────────────────────────┘    │
│                             │                                  │
│                             ▼                                  │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ Command Registration (lines 287-336)                 │    │
│  ├──────────────────────────────────────────────────────┤    │
│  │ cli.add_command(init)           # Line 287           │    │
│  │ cli.add_command(index)          # Line 288           │    │
│  │ cli.add_command(explain)        # Line 300 ⚠️        │    │
│  │ cli.add_command(detect_frameworks) # Line 304 ⚠️     │    │
│  │ ...                                                   │    │
│  │ cli.add_command(terraform)      # Line 336           │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │  Problem: DRIFT        │
                ├────────────────────────┤
                │ • New commands added   │
                │   via cli.add_command()│
                │                         │
                │ • VerboseGroup NOT     │
                │   updated manually     │
                │                         │
                │ • Commands INVISIBLE   │
                │   in help output       │
                └────────────────────────┘
```

**Key Issues**:
1. **Registration-Documentation Drift**: VerboseGroup (lines 24-172) and command registration (lines 287-336) are **decoupled**
2. **Manual Maintenance**: Adding a command requires TWO separate updates
3. **No Validation**: No check that VerboseGroup includes all registered commands
4. **Result**: `explain` and `detect-frameworks` are registered but invisible

---

### Proposed Architecture (Self-Healing)

```
┌─────────────────────────────────────────────────────────────┐
│                       theauditor/cli.py                        │
├─────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ VerboseGroup.COMMAND_CATEGORIES (metadata)           │    │
│  ├──────────────────────────────────────────────────────┤    │
│  │ {                                                     │    │
│  │   'PROJECT_SETUP': {                                 │    │
│  │     'title': 'PROJECT SETUP',                        │    │
│  │     'description': '...',                            │    │
│  │     'commands': ['init', 'setup-ai', ...],           │    │
│  │     'ai_context': 'Run these FIRST...'               │    │
│  │   },                                                  │    │
│  │   'CORE_ANALYSIS': { ... },                          │    │
│  │   'UTILITIES': {                                      │    │
│  │     'commands': ['explain', 'planning']  ✅          │    │
│  │   }                                                   │    │
│  │ }                                                     │    │
│  └──────────────────────────────────────────────────────┘    │
│                             │                                  │
│                             ▼                                  │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ VerboseGroup.format_help(ctx, formatter)             │    │
│  ├──────────────────────────────────────────────────────┤    │
│  │ 1. super().format_help() → Original docstring        │    │
│  │ 2. Query: registered = self.commands.items()         │    │
│  │ 3. For each category in COMMAND_CATEGORIES:          │    │
│  │    • Extract cmd.help (first line)                   │    │
│  │    • Format with options (first 3 params)            │    │
│  │ 4. Validate: ungrouped = registered - categorized    │    │
│  │    • Warn if ungrouped exists                        │    │
│  └──────────────────────────────────────────────────────┘    │
│              ▲                        │                        │
│              │                        ▼                        │
│  ┌───────────┴──────────┐  ┌────────────────────────┐        │
│  │ cli.commands dict    │  │ Dynamic Help Output    │        │
│  ├──────────────────────┤  ├────────────────────────┤        │
│  │ • init               │  │ PROJECT SETUP:         │        │
│  │ • index              │  │   aud init  # First... │        │
│  │ • explain       ✅   │  │ UTILITIES:              │        │
│  │ • detect-frameworks  │  │   aud explain  # Learn │        │
│  │   ✅                 │  │   aud detect-frameworks│        │
│  │ • ...                │  │     # Display...       │        │
│  └──────────────────────┘  └────────────────────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │  Solution: AUTO-SYNC   │
                ├────────────────────────┤
                │ • New command added    │
                │   via cli.add_command()│
                │                         │
                │ • Appears in help       │
                │   AUTOMATICALLY         │
                │   (if categorized)      │
                │                         │
                │ • Warning shown if      │
                │   not categorized       │
                │   (prevents drift)      │
                └────────────────────────┘
```

**Key Improvements**:
1. **Single Source of Truth**: `cli.commands` dict is queried dynamically
2. **Self-Healing**: New commands automatically appear in help (if categorized)
3. **Validation Built-In**: Warns if commands exist but aren't categorized
4. **Minimal Maintenance**: Only update `COMMAND_CATEGORIES` dict (5 lines) instead of 135 lines of hardcoded text

---

## Data Structures

### COMMAND_CATEGORIES Dictionary Schema

```python
COMMAND_CATEGORIES = {
    '<category_id>': {  # Unique identifier (UPPER_SNAKE_CASE)
        'title': str,          # Display title (e.g., "PROJECT SETUP")
        'description': str,    # Human-readable explanation
        'commands': List[str], # Command names (must match cli.commands keys)
        'ai_context': str,     # AI-specific guidance (WHEN/WHY to use category)
    },
    # ... 9 total categories
}
```

**Example**:
```python
'PROJECT_SETUP': {
    'title': 'PROJECT SETUP',
    'description': 'Initial configuration and environment setup',
    'commands': ['init', 'setup-ai', 'setup-claude', 'init-js', 'init-config'],
    'ai_context': 'Run these FIRST in new projects. Creates .pf/ structure, installs tools.',
}
```

**Validation Rules**:
1. All command names in `commands` lists MUST exist in `cli.commands`
2. No command should appear in multiple categories (enforced by test)
3. All registered commands (except `_*` internal) MUST appear in exactly one category

---

### Command Help Text Structure (Template)

```yaml
# Required Sections (enforced by CI):
sections:
  - name: "One-Line Summary"
    location: First line of docstring
    length: 50-80 characters
    format: "[WHAT THIS DOES in imperative mood]"

  - name: "Extended Purpose"
    location: Lines 2-5
    length: 2-3 paragraphs
    content: WHO, WHAT, WHEN, WHY

  - name: "AI ASSISTANT CONTEXT"
    location: After purpose, before capabilities
    format: YAML-style key-value
    required_fields:
      - Purpose: str (one sentence)
      - Input: str (files/tables read)
      - Output: str (files/tables written)
      - Prerequisites: List[str] (commands to run first)
      - Integration: str (how fits in workflows)
      - Performance: str (expected runtime)

  - name: "WHAT IT ANALYZES/DETECTS/PRODUCES"
    location: After AI CONTEXT
    format: Bulleted list
    minimum_items: 3

  - name: "SUPPORTED ENVIRONMENTS"
    location: After capabilities
    format: Bulleted list (languages/frameworks)
    optional: True (only for multi-language commands)

  - name: "HOW IT WORKS (ALGORITHM)"
    location: After capabilities
    format: Numbered list (3-5 steps)
    minimum_items: 3

  - name: "EXAMPLES (AI-CONSUMABLE)"
    location: Mid-section
    format: Code blocks with comments
    minimum: 4 examples
    categories:
      - "Use Case 1: Most common usage"
      - "Use Case 2: With workset"
      - "Use Case 3: CI/CD integration"
      - "Use Case 4: Advanced usage"

  - name: "COMMON WORKFLOWS"
    location: After examples
    format: Scenario → command sequence
    minimum: 3 scenarios
    categories:
      - "Before Deployment:"
      - "Pull Request Review:"
      - "Security Audit:"

  - name: "OUTPUT FILES (EXACT PATHS)"
    location: After workflows
    format: "path/to/file.json  # Description"
    minimum: 2 outputs
    include_db_tables: True (if database updated)

  - name: "OUTPUT FORMAT (JSON SCHEMA)"
    location: After output files
    format: JSON example with comments
    required_fields: [file, line, severity, message]

  - name: "PERFORMANCE EXPECTATIONS"
    location: After output format
    format: Table with 3 rows (Small/Medium/Large LOC)
    columns: [Size, Time, RAM]

  - name: "FLAG INTERACTIONS"
    location: After performance
    format: 3 subsections
    subsections:
      - "Mutually Exclusive:"
      - "Recommended Combinations:"
      - "Flag Modifiers:"
    optional: Only if command has 3+ flags

  - name: "PREREQUISITES"
    location: After flag interactions
    format: "Required:" + "Optional:" sublists

  - name: "EXIT CODES"
    location: After prerequisites
    format: "N = Description"
    minimum: 2 codes (0 and 1+)

  - name: "RELATED COMMANDS"
    location: After exit codes
    format: "aud command  # When to use instead"
    minimum: 2 related commands

  - name: "SEE ALSO"
    location: After related
    format: "aud explain concept  # Learn about..."
    optional: True

  - name: "TROUBLESHOOTING"
    location: After related/see also
    format: "Error: message → Solution: action"
    minimum: 2 common errors

  - name: "NOTE"
    location: Final section
    format: Paragraph with caveats/limitations
    optional: True
```

---

## Algorithms

### Dynamic Help Generation (format_help)

```python
def format_help(self, ctx, formatter):
    """
    Time Complexity: O(C + N + N*O)
      C = Number of categories (9)
      N = Number of registered commands (35)
      O = Average options per command (~3)
    Total: O(9 + 35 + 35*3) ≈ O(149) operations
    → Negligible performance impact (<1ms)

    Space Complexity: O(N)
      Stores registered commands dict: 35 * sizeof(Command object)
      → ~10KB memory overhead

    Algorithm:
      1. Call super().format_help() to render CLI docstring
      2. Write AI guidance banner (4 lines)
      3. For each category in COMMAND_CATEGORIES:
         a. Write category title + description + ai_context
         b. For each command name in category['commands']:
            i. Look up command in self.commands dict
            ii. Extract first line of cmd.help as short_help
            iii. Format as "aud {name:20s} # {short_help}"
            iv. Extract first 3 options with help text
            v. Format options as "  {opt:22s} # {help}"
      4. Calculate ungrouped commands:
         all_categorized = union(all commands lists)
         ungrouped = set(self.commands.keys()) - all_categorized - {'_*'}
      5. If ungrouped exists, write warning box
      6. Write footer with guidance
    """
```

**Pseudocode**:
```
function format_help(ctx, formatter):
    // Phase 1: Render original docstring
    super().format_help(ctx, formatter)

    // Phase 2: AI Context Banner
    formatter.write("=" * 80)
    formatter.write("COMMAND REFERENCE (AI-Optimized Categorization)")
    formatter.write("=" * 80)
    formatter.write_paragraph()
    formatter.write("AI ASSISTANT GUIDANCE:")
    formatter.write("  - Commands grouped by purpose...")
    formatter.write("  - Each category shows WHEN and WHY...")
    formatter.write("  - Run 'aud <command> --help' for details...")
    formatter.write("  - Use 'aud explain <concept>' to learn...")
    formatter.write_paragraph()

    // Phase 3: Extract registered commands
    registered = {}
    for name, cmd in self.commands.items():
        if not name.startswith('_'):  // Skip internal
            registered[name] = cmd

    // Phase 4: Render categories
    for category_id, category_data in COMMAND_CATEGORIES.items():
        formatter.write(f"{category_data['title']}:")
        with formatter.indentation():
            // Category metadata
            formatter.write(f"# {category_data['description']}")
            formatter.write(f"# AI: {category_data['ai_context']}")
            formatter.write_paragraph()

            // Commands in category
            for cmd_name in category_data['commands']:
                if cmd_name not in registered:
                    continue  // Skip if not registered (e.g., aliases)

                cmd = registered[cmd_name]
                short_help = cmd.help.split('\n')[0].strip() if cmd.help else "No description"
                formatter.write(f"aud {cmd_name:20s} # {short_help}")

                // Show first 3 options
                if hasattr(cmd, 'params'):
                    key_options = [p for p in cmd.params[:3] if p.help]
                    for param in key_options:
                        opt_name = f"--{param.name.replace('_', '-')}"
                        formatter.write(f"  {opt_name:22s} # {param.help}")

            formatter.write_paragraph()

    // Phase 5: Validation warning
    all_categorized = set()
    for cat_data in COMMAND_CATEGORIES.values():
        all_categorized.update(cat_data['commands'])

    ungrouped = set(registered.keys()) - all_categorized

    if ungrouped:
        formatter.write("=" * 80)
        formatter.write("WARNING: The following commands are not categorized:")
        formatter.write("=" * 80)
        for cmd_name in sorted(ungrouped):
            formatter.write(f"  - {cmd_name}")
        formatter.write_paragraph()
        formatter.write("^ Report this to maintainers")
        formatter.write_paragraph()

    // Phase 6: Footer
    formatter.write("For detailed help: aud <command> --help")
    formatter.write("For concepts: aud explain --list")
```

---

### Help Text Validation Algorithm (CI Test)

```python
def validate_help_text(command_name: str, command_object: click.Command) -> List[str]:
    """
    Validate command help text meets AI-first standards.

    Time Complexity: O(L + S)
      L = Lines in help text (~200 max)
      S = Sections to validate (~15)
    Total: O(215) per command → O(215 * 35) = O(7525) for all commands
    → ~10ms total validation time

    Returns:
        List of validation errors (empty = pass)
    """
    errors = []
    help_text = command_object.help or ""
    lines = help_text.split('\n')
    line_count = len(lines)

    # 1. Check minimum line count (tier-based)
    tier = classify_command_tier(command_name)
    min_lines = {'complex': 200, 'medium': 150, 'simple': 80, 'utility': 50}[tier]
    if line_count < min_lines:
        errors.append(f"Help text too short: {line_count} < {min_lines} (tier: {tier})")

    # 2. Check required sections exist
    required_sections = [
        "AI ASSISTANT CONTEXT:",
        "EXAMPLES",
        "OUTPUT",
        "PREREQUISITES",
    ]
    for section in required_sections:
        if section not in help_text:
            errors.append(f"Missing required section: {section}")

    # 3. Check AI ASSISTANT CONTEXT has all fields
    if "AI ASSISTANT CONTEXT:" in help_text:
        required_fields = ['Purpose:', 'Input:', 'Output:', 'Prerequisites:', 'Integration:', 'Performance:']
        context_section = extract_section(help_text, "AI ASSISTANT CONTEXT:", next_section="WHAT")
        for field in required_fields:
            if field not in context_section:
                errors.append(f"Missing AI CONTEXT field: {field}")

    # 4. Check minimum 4 examples
    example_count = help_text.count(f'aud {command_name}')
    if example_count < 4:
        errors.append(f"Insufficient examples: {example_count} < 4")

    # 5. Check COMMON WORKFLOWS has 3 scenarios
    if "COMMON WORKFLOWS:" in help_text:
        workflow_section = extract_section(help_text, "COMMON WORKFLOWS:", "OUTPUT")
        scenario_count = workflow_section.count(":")
        if scenario_count < 3:
            errors.append(f"Insufficient workflow scenarios: {scenario_count} < 3")

    # 6. Check EXIT CODES (if command can fail)
    if command_can_fail(command_name):
        if "EXIT CODES:" not in help_text:
            errors.append("Missing EXIT CODES section")

    # 7. Check FLAG INTERACTIONS (if 3+ flags)
    param_count = len([p for p in command_object.params if p.help])
    if param_count >= 3:
        if "FLAG INTERACTIONS:" not in help_text:
            errors.append("Missing FLAG INTERACTIONS (command has 3+ flags)")

    return errors
```

---

## Design Decisions & Rationale

### Decision 1: Dynamic Generation vs. Hardcoded Text

**Options Considered**:
1. **Keep hardcoded VerboseGroup** + manually update for each new command
2. **Dynamic generation from COMMAND_CATEGORIES** + validation
3. **Fully automatic** (no categories, just list all commands alphabetically)

**Chosen**: Option 2 (Dynamic generation with explicit categorization)

**Rationale**:
- ✅ **Maintainability**: Updating categories is 5 lines vs 135 lines of hardcoded text
- ✅ **Self-Healing**: New commands automatically appear (if categorized)
- ✅ **Validation**: Warns if commands uncategorized (prevents drift)
- ✅ **AI-Optimized**: Categories have `ai_context` explaining WHEN/WHY
- ❌ Option 1 fails: Already caused 2 invisible commands
- ❌ Option 3 fails: No semantic grouping → confusing for AI

**Tradeoffs**:
- Requires ONE update (add to category) instead of ZERO updates (fully automatic)
- But: Validation warns immediately if forgotten (vs silent invisibility)

---

### Decision 2: AI ASSISTANT CONTEXT Section Format

**Options Considered**:
1. **Freeform prose** (like current help text)
2. **YAML-style key-value** (structured fields)
3. **JSON object** (machine-readable)

**Chosen**: Option 2 (YAML-style key-value in help text)

**Rationale**:
- ✅ **Human-Readable**: Looks clean in terminal
- ✅ **Machine-Parsable**: AI can extract specific fields
- ✅ **Structured**: Enforces completeness (6 required fields)
- ✅ **Consistent**: All commands follow same format
- ❌ Option 1 fails: AI can't reliably extract specific info
- ❌ Option 3 fails: Not readable in terminal help

**Example**:
```
AI ASSISTANT CONTEXT:
  Purpose: Indexes all source files into SQLite database
  Input: Source files (*.py, *.js, *.ts, *.go)
  Output: .pf/repo_index.db (108 tables), .pf/manifest.json
  Prerequisites: None (this is the first command)
  Integration: Foundation for all other analysis commands
  Performance: Small ~30s, Medium ~5min, Large ~20min
```

---

### Decision 3: Minimum Line Count Enforcement

**Options Considered**:
1. **No minimum** (let authors decide)
2. **Single minimum** (e.g., 50 lines for all)
3. **Tiered minimums** (complex=200, medium=150, simple=80, utility=50)

**Chosen**: Option 3 (Tiered minimums based on command complexity)

**Rationale**:
- ✅ **Proportional**: Complex commands need more explanation
- ✅ **Realistic**: Simple commands don't need 200 lines
- ✅ **Measurable**: CI can enforce automatically
- ✅ **Prevents Regression**: Can't merge with insufficient docs
- ❌ Option 1 fails: Already have 9-line commands (tool-versions)
- ❌ Option 2 fails: Too harsh for simple utils, too lenient for complex

**Command Tiers**:
- **Complex** (200+ lines): fce, taint-analyze, graph, insights, query
- **Medium** (150+ lines): detect-patterns, deps, lint, full, index
- **Simple** (80+ lines): init, workset, tool-versions, init-config, init-js
- **Utility** (50+ lines): explain, planning

---

### Decision 4: Flag Interactions Documentation

**Options Considered**:
1. **No documentation** (users figure it out)
2. **Document in command logic** (code comments)
3. **Document in help text** (FLAG INTERACTIONS section)

**Chosen**: Option 3 (FLAG INTERACTIONS section in help text)

**Rationale**:
- ✅ **User-Facing**: AI/humans don't read code comments
- ✅ **Discoverable**: Shows up in --help output
- ✅ **Prevents Errors**: AI won't try invalid combinations
- ✅ **Actionable**: Shows recommended combinations
- ❌ Option 1 fails: Trial-and-error wastes time
- ❌ Option 2 fails: Help text readers can't see code

**Structure**:
```
FLAG INTERACTIONS:
  Mutually Exclusive:
    --option1 and --option2 cannot be used together (returns error)

  Recommended Combinations:
    Use --option3 with --option4 for complete analysis

  Flag Modifiers:
    --quiet suppresses all output except errors
    --workset limits scope to .pf/workset.json files
```

---

### Decision 5: Examples Format (AI-Consumable)

**Options Considered**:
1. **Plain commands** (just `aud full`)
2. **Commands with output** (show what you get)
3. **Commands with use case comments** (`# Use Case 1: ...`)

**Chosen**: Option 3 (Commands with use case context comments)

**Rationale**:
- ✅ **Context-Rich**: AI understands WHEN to use each example
- ✅ **Copy-Pasteable**: AI can copy command directly
- ✅ **Categorized**: Common, workset, CI/CD, advanced
- ✅ **Self-Explanatory**: No need to guess intent
- ❌ Option 1 fails: No context for when to use
- ❌ Option 2 fails: Too verbose, clutters help text

**Format**:
```python
EXAMPLES (AI-CONSUMABLE):
  # Use Case 1: Most common usage
  aud command-name --option1

  # Use Case 2: With workset (after code changes)
  aud workset --diff HEAD~1 && aud command-name --workset

  # Use Case 3: CI/CD integration (fail on errors)
  aud command-name --quiet || exit $?

  # Use Case 4: Advanced usage (all options)
  aud command-name --option1 --option2 --verbose
```

---

## Performance Considerations

### Help Generation Performance

**Current (Hardcoded)**:
- Time: <1ms (just string concatenation)
- Memory: ~5KB (static strings)

**Proposed (Dynamic)**:
- Time: <2ms (query 35 commands × extract help × format)
- Memory: ~15KB (command dict + formatted strings)

**Analysis**:
- Overhead: +1ms, +10KB → **Negligible** (user won't notice)
- Benefit: Self-healing help + validation → **High Value**
- Tradeoff: **Acceptable** (performance impact minimal, maintainability gain huge)

### Help Text Validation Performance

**CI Test Suite**:
- Commands to validate: 35
- Validation time per command: ~0.3ms (15 section checks)
- Total validation time: 35 × 0.3ms = **10.5ms**

**Analysis**:
- CI overhead: +10ms per run → **Negligible**
- Benefit: Catches doc regressions immediately → **High Value**
- Tradeoff: **Acceptable** (CI runs take seconds anyway)

---

## Security Considerations

### No Security Impact

**Analysis**:
- **Help text only** (no code execution changes)
- **No user input** (all text is static or from trusted source code)
- **No network calls** (local help generation)
- **No file writes** (read-only operation)
- **No privilege escalation** (runs with same perms as `aud` command)

**Conclusion**: This change has **zero security impact** beyond making security commands more discoverable.

---

## Backwards Compatibility

### No Breaking Changes

**Analysis**:
- **Command syntax unchanged** (all flags, options, arguments identical)
- **Command behavior unchanged** (only help text enhanced)
- **Exit codes unchanged** (all commands return same codes)
- **Output formats unchanged** (JSON schemas, file paths identical)
- **API unchanged** (Click command decorators identical)

**Migration**:
- **Scripts**: No changes needed (only `--help` output different)
- **CI**: No changes needed (command behavior identical)
- **Documentation**: Update screenshots/examples to show new help

**Conclusion**: **100% backwards compatible** - existing users/scripts unaffected.

---

## Testing Strategy

### Unit Tests (tests/test_cli_help_ai_first.py)

1. **test_all_commands_categorized()**
   - Purpose: Ensure no commands invisible
   - Logic: Compare `cli.commands` vs `COMMAND_CATEGORIES`
   - Coverage: VerboseGroup taxonomy

2. **test_help_text_minimum_quality()**
   - Purpose: Enforce minimum line counts
   - Logic: Check `len(cmd.help.split('\n'))` per tier
   - Coverage: All 35 commands

3. **test_ai_context_section_exists()**
   - Purpose: Ensure structured AI guidance
   - Logic: Search for "AI ASSISTANT CONTEXT:" in help
   - Coverage: All 35 commands

4. **test_examples_exist()**
   - Purpose: Ensure 4+ examples per command
   - Logic: Count occurrences of `aud {cmd_name}`
   - Coverage: All 35 commands (except simple utils)

5. **test_no_duplicate_categories()**
   - Purpose: Ensure clean taxonomy
   - Logic: Check no command in multiple categories
   - Coverage: COMMAND_CATEGORIES dict

6. **test_flag_interactions_documented()**
   - Purpose: Ensure complex commands have FLAG INTERACTIONS
   - Logic: Search for section if command has 3+ flags
   - Coverage: 18 commands with 3+ flags

### Integration Tests (Manual QA)

1. **Visual Inspection**:
   - Run `aud --help` → Verify all categories show
   - Run `aud --help | grep "aud explain"` → Verify explain visible
   - Run `aud --help | grep "WARNING"` → Verify no ungrouped

2. **Command-Specific**:
   - Run `aud full --help` → Verify FLAG INTERACTIONS section
   - Run `aud query --help | grep "AI ASSISTANT CONTEXT"` → Verify exists
   - Run `aud tool-versions --help | wc -l` → Verify ~100 lines

3. **Regression Tests**:
   - Compare old vs new help output → Verify no lost information
   - Run existing CI scripts → Verify no broken commands
   - Test with AI assistant → Verify improved usability

---

## Rollout Plan

### Phase 1: Core Infrastructure (Week 1)
- Implement dynamic VerboseGroup
- Define COMMAND_CATEGORIES taxonomy
- Add validation tests
- Deploy: Internal testing only

### Phase 2: Documentation Template (Week 1)
- Create CLI_DOCUMENTATION_STANDARD.md
- Add PR checklist
- Implement CI enforcement
- Deploy: Enable CI checks

### Phase 3: Command Enhancements (Week 2-3)
- Enhance Tier 1 commands (6 critical)
- Enhance Tier 2 commands (10 needs improvement)
- Enhance Tier 3 commands (6 good → add advanced sections)
- Deploy: Incremental (merge as ready)

### Phase 4: Validation & Release (Week 4)
- Run full test suite
- Manual QA checklist
- AI assistant testing
- Deploy: Release to main

---

## Monitoring & Success Metrics

### Quantitative Metrics

| Metric | Before | Target | After | Status |
|--------|--------|--------|-------|--------|
| Commands visible in --help | 33/35 (94%) | 35/35 (100%) | TBD | Pending |
| Min lines per command | 3 | 50 | TBD | Pending |
| Commands with AI CONTEXT | 0/35 (0%) | 35/35 (100%) | TBD | Pending |
| Commands with 4+ examples | ~21/35 (60%) | 35/35 (100%) | TBD | Pending |
| Commands with FLAG INTERACTIONS | 0/18 (0%) | 18/18 (100%) | TBD | Pending |

### Qualitative Metrics

1. **AI Usability**: Can new Claude session understand tool from --help alone?
   - Baseline: No (needs source code + examples)
   - Target: Yes (help text sufficient)

2. **Developer Experience**: Can contributors write commands following template?
   - Baseline: Inconsistent quality
   - Target: Template ensures consistency

3. **User Feedback**: Do users report clearer understanding?
   - Baseline: N/A (no tracking)
   - Target: Positive feedback in issues/PRs

---

## Future Enhancements (Out of Scope)

### Phase 5 Possibilities (Backlog)

1. **Interactive Help Explorer**:
   - Command: `aud explore` or `aud help --interactive`
   - Features: Search, filter, fuzzy matching
   - UI: TUI with rich/textual library

2. **Help Text Localization**:
   - Multi-language support (Spanish, French, Chinese)
   - AI-friendly for non-English models

3. **Help Text Analytics**:
   - Track which commands users run `--help` on most
   - Identify confusing commands needing improvement

4. **Auto-Generated Documentation Site**:
   - Extract help text → Markdown → Static site
   - Deploy to GitHub Pages / ReadTheDocs

5. **Help Text Linting in Pre-Commit**:
   - Validate before commit (not just in CI)
   - Faster feedback loop for contributors

---

## Conclusion

This design provides a **self-healing, AI-first CLI help system** that:
- ✅ Eliminates registration-documentation drift
- ✅ Ensures 100% command discoverability
- ✅ Enforces minimum documentation quality
- ✅ Provides structured AI-consumable guidance
- ✅ Maintains backwards compatibility
- ✅ Adds negligible performance overhead

**Next Steps**: Proceed to implementation (tasks.md Phase 0-4) after Architect approval.
