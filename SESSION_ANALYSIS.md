# Agent Behavior Intelligence - Tier 5 ML Features

## What is This?

TheAuditor's ML risk prediction system now includes **Tier 5: Agent Behavior** - analyzing Claude Code conversation logs to extract features about AI agent behavior patterns. This data feeds into the ML models alongside code metrics, git history, and security findings.

**This is not a standalone CLI feature.** It's integrated into the ML training pipeline as an optional data source.

## How to Enable

```bash
# Train ML models with agent behavior features
aud learn --session-dir ~/.claude/projects/YourProject --print-stats

# Agent behavior features are automatically included in feature matrix
# Models learn patterns like: files with blind edits = higher risk
```

## Data Source

All Claude Code conversation logs are automatically stored in:
```
C:\Users\santa\.claude\projects\C--Users-santa-Desktop-TheAuditor\*.jsonl
```

Each `.jsonl` file contains:
- User messages (prompts, questions, requests)
- Agent messages (text responses, tool calls)
- Tool call parameters (files read/edited, bash commands, etc.)
- Timestamps, token usage, model info

## Features Extracted for ML Models

### 4 Agent Behavior Features Added to Feature Matrix

1. **agent_blind_edit_count** (normalized /5.0)
   - Files edited without prior read
   - Correlated with higher bug introduction rate
   - Used by Risk Scorer to flag risky agent-modified files

2. **agent_duplicate_impl_rate** (0.0-1.0 scale)
   - Rate of duplicate symbol creation (increments by 0.1 per duplicate)
   - Files where agent recreates existing functionality
   - Used by Root Cause Classifier to identify misunderstood architecture

3. **agent_missed_search_count** (normalized /10.0)
   - Relevant files not examined before implementation
   - Indicates agent didn't discover existing context
   - Used by Next Edit Predictor to flag incomplete changes

4. **agent_read_efficiency** (normalized /5.0)
   - Reads per successful edit (lower = better)
   - Excessive re-reads indicate agent confusion
   - Used by Risk Scorer to detect uncertain modifications

### Integration with ML Pipeline

These features join 50+ existing features:
- **Tier 1**: Pipeline logs (phase timing, success/failure)
- **Tier 2**: Journal events (file touches, audit trail)
- **Tier 3**: Raw artifacts (security patterns, CFG complexity)
- **Tier 4**: Git history (commits, authors, recency)
- **Tier 5**: Agent behavior (blind edits, duplicates, missed context)

## Example Findings (This Project)

From analyzing 20 recent sessions:

```
Sessions analyzed: 20
Total findings: 635

--- Aggregate Stats ---
Total tool calls: 602
Total reads: 248
Total edits: 39
Avg tool calls/session: 30.1
Edit-to-read ratio: 0.16

--- Findings by Category ---
  missed_existing_code: 610
  blind_edit: 11
  duplicate_implementation: 11
  duplicate_read: 3
```

**Key insight**: 11 blind edits across 20 sessions (agent editing files without reading them first).

## Real-World Use Case: Self-Improvement

This very implementation caught me (Claude) making blind edits:

```
[WARNING] Edit without prior Read
File C:\Users\santa\Desktop\TheAuditor\theauditor\commands\session.py was edited without being read first
Evidence: {
  "file": "C:\\Users\\santa\\Desktop\\TheAuditor\\theauditor\\commands\\session.py",
  "tool_call_uuid": "toolu_01NoEDFXzPuYRchUZjH4KnmH"
}
```

I made **10 edits** to `session.py` without reading it first - risky behavior that could introduce bugs.

## Architecture

### Parser Layer (`theauditor/session/parser.py`)
- Loads JSONL conversation logs
- Parses into structured `Session` objects
- Extracts user messages, assistant messages, tool calls

### Analyzer Layer (`theauditor/session/analyzer.py`)
- Computes session statistics
- Runs pattern detectors (blind edits, duplicates, etc.)
- Cross-references with `repo_index.db` for codebase reality

### CLI Layer (`theauditor/commands/session.py`)
- `aud session list` - List all sessions
- `aud session analyze` - Aggregate analysis across multiple sessions
- `aud session inspect` - Deep dive into single session

## Cross-Referencing with Codebase

When `repo_index.db` exists, analyzer can:

1. **Detect duplicate implementations**:
   ```python
   # Agent creates new symbol
   write_call.content contains "def calculate_total"

   # Check if it exists
   cursor.execute("SELECT path FROM symbols WHERE name = 'calculate_total'")
   # Found in api/utils.py - DUPLICATE!
   ```

2. **Find missed existing code**:
   ```python
   # User mentions "authentication"
   user_message.content contains "auth"

   # Check relevant files
   cursor.execute("SELECT path FROM symbols WHERE name LIKE '%auth%'")
   # Found auth/session.py, auth/jwt.py - agent never read them
   ```

## Future Enhancements

### Planned (Vision from User)

1. **Corrections Tracking**
   - How many times user corrects agent mistakes
   - Common types of corrections

2. **Frustration Detection**
   - User repeats same request 3+ times
   - Agent fails to understand intent

3. **Success Patterns**
   - Which agent approaches work best
   - Optimal tool call sequences

4. **Preferences Learning**
   - User prefers imports at top
   - User wants type hints
   - User likes verbose comments

5. **Auto-CLAUDE.md Generation**
   - Extract patterns from successful sessions
   - Generate project-specific agent guidelines
   - Update based on frustration/correction patterns

### Technical Debt to Address

- **Keyword extraction** is naive (simple regex)
  - Should use NLP for entity extraction
- **Duplicate detection** only checks symbol names
  - Should compare function signatures, logic similarity
- **No temporal patterns** yet
  - Which sessions happen after errors?
  - Learning curves over time

## Integration Points

### With TheAuditor Core
- Session analysis complements code analysis
- Agent behavior + codebase reality = complete picture
- Findings can inform taint analysis scope

### With Planning System
- Track which planning steps agent skips
- Verify planned vs actual implementation
- Auto-generate task lists from successful patterns

### With ML/Insights
- Training data for agent optimization
- Feedback loop for continuous improvement
- Pattern recognition for common failures

## Data Privacy

- All analysis is **local-only**
- No data sent to external services
- Session logs contain your code - treat accordingly
- Add `.claude/` to `.gitignore` if needed

## Performance

Parsing 194 sessions (~44,000 lines of JSONL) takes ~5 seconds.

Database cross-referencing adds ~2-3 seconds for duplicate detection.

Analyze at will - it's fast enough for interactive use.

## Example Workflow

```bash
# After a frustrating session where agent missed existing code
aud session analyze --limit 1

# Findings show: "User mentioned X but relevant files not read"
# Add to CLAUDE.md:
# "Always search for existing implementations of X before creating new ones"

# Next session: Agent searches first, finds existing code
# Success rate improves over time
```

## Implementation Notes

**Why separate from core analysis?**
- Different data source (JSONL vs repo files)
- Different analysis goals (behavior vs security)
- Optional feature (core analysis works standalone)

**Why not just use logs?**
- Logs show what happened, not why
- Cross-referencing with DB shows missed opportunities
- Pattern detection finds systemic issues

**Why JSONL instead of database?**
- Claude Code stores sessions in JSONL
- No conversion needed - parse directly
- Maintains compatibility with Claude's format

## See Also

- `theauditor/session/parser.py` - JSONL parsing logic
- `theauditor/session/analyzer.py` - Pattern detection algorithms
- `theauditor/commands/session.py` - CLI interface
