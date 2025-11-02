# Proposal: ml-user-chats

## Status
**DRAFT** - Awaiting validation and approval

## Change ID
`ml-user-chats`

## Summary
Add Tier 5 (Agent Behavior Intelligence) to TheAuditor's ML system by analyzing Claude Code session logs to create a deterministic feedback loop. This change extracts execution traces (tool calls, diffs), scores them using TheAuditor's complete SAST pipeline, and correlates workflow compliance with task outcomes to generate high-quality labeled training data.

## Why

Session logs from AI coding assistants contain complete execution traces (tool calls, diffs, timestamps) that are currently unused. This data enables deterministic correlation between **development process quality** (workflow compliance) and **code quality** (SAST findings), creating a feedback loop for AI agents to learn successful patterns and avoid failed approaches.

Without this feedback loop:
- AI agents repeat the same mistakes (blind edits, skipped workflows, incomplete refactors)
- ML models lack process quality signals (only know "what code is risky" not "why it was written that way")
- No statistical evidence showing which workflow violations cause failures
- No mechanism for self-correction (agent can't learn from historical patterns)

With Tier 5 (Agent Behavior Intelligence):
- **Statistical workflow enforcement**: "Skipping blueprint on api.py = 95% failure rate" (data-driven, not opinions)
- **Self-correcting agents**: Agent queries historical patterns before executing, avoids approaches with <60% success rate
- **ML model improvement**: 5-10% accuracy boost by adding process quality signals
- **Labeled training data**: High-quality dataset showing successful vs failed execution patterns

This is not "vibe coding" or "analyzing user intent" - it's deterministic correlation of execution traces with SAST findings and task outcomes.

## Problem Statement

### Current State
TheAuditor's ML Intelligence System has 4 tiers of data sources:
- **Tier 1**: Pipeline logs (phase timing, success/failure)
- **Tier 2**: Journal events (file touches, audit trail)
- **Tier 3**: Raw artifacts (CFG complexity, security patterns)
- **Tier 4**: Git temporal (commits, authors, churn)

These tiers provide excellent code-centric data but lack execution context about **how changes were made** and **whether the development process followed best practices**.

### The Gap
AI coding assistants (Claude Code, GitHub Copilot, etc.) generate session logs containing:
- Every tool call (Read, Edit, Write, Bash) with timestamps
- Complete diffs (`old_string` → `new_string`) for every code change
- Task context from user messages
- Execution sequences showing agent behavior patterns

**This data is currently unused** despite containing deterministic evidence of:
- Blind edits (editing files without reading them first)
- Workflow violations (skipping `aud blueprint`, `aud query` before implementation)
- Incomplete refactors (modifying one file while missing related files)
- Agent confusion patterns (excessive re-reads, repeated searches)

### Why This Matters
Current ML models lack **process quality signals**. They can predict "this file is risky" based on code metrics and git history, but they cannot learn that "changes made without running blueprint first have 78% failure rate."

Session logs enable **statistical workflow enforcement**:
- Correlate execution patterns with outcomes (task completed, corrections needed, rollback)
- Learn which workflow violations cause failures
- Generate labeled training data showing successful vs failed approaches

## Proposed Solution

### Three-Layer Architecture

**Layer 1: Execution Capture**
- Parse Claude Code session logs (`C:\Users\santa\.claude\projects\<project>\*.jsonl`)
- Extract tool calls, diffs, timestamps, task context
- Build execution timeline showing agent behavior sequence

**Layer 2: Deterministic Scoring**
- Run each diff through TheAuditor's complete SAST pipeline:
  - Taint analysis (SQL injection, XSS, etc.)
  - Pattern detection (f-strings in SQL, hardcoded secrets)
  - FCE correlation (incomplete refactors, missed related files)
  - RCA historical risk (file's historical failure rate)
- Aggregate scores into risk metric (0.0-1.0)

**Layer 3: Workflow Correlation**
- Check if agent followed `planning.md` workflows:
  - Did agent run `aud blueprint` first? (MANDATORY)
  - Did agent use `aud query` before editing? (MANDATORY)
  - Did agent check related files via `aud context`? (RECOMMENDED)
- Correlate compliance with outcomes:
  - Task completed without corrections
  - User corrections needed in next session
  - Changes rolled back
- Learn: `IF workflow_compliant AND risk_score < 0.3 THEN success_rate = 89%`

### Data Flow
```
Session Execution
  ↓
Extract diffs + tool calls (Layer 1)
  ↓
Score each diff via SAST (Layer 2)
  ↓
Check workflow compliance (Layer 3)
  ↓
Calculate user engagement rate (INVERSE METRIC)
  → user_messages / tool_calls
  → Low engagement = agent self-sufficient (good)
  → High engagement = agent needs guidance (bad)
  ↓
Store in session_executions table
  ↓
Correlate compliance + risk + outcomes + engagement
  ↓
Generate ML training features
  ↓
Learn successful execution patterns
```

### Key Components

1. **DiffScorer** (`theauditor/session/diff_scorer.py`)
   - Extracts diffs from Edit/Write tool calls
   - Runs diffs through taint, patterns, FCE, RCA
   - Returns aggregate risk score (0.0-1.0)

2. **WorkflowChecker** (`theauditor/session/workflow_checker.py`)
   - Validates execution sequence against `planning.md` workflows
   - Returns compliance score and violation list
   - Checks: blueprint_first, query_before_edit, no_blind_reads

3. **session_executions table** (new schema)
   - Stores: session_id, task_description, workflow_compliant, risk_score, outcome, user_engagement_rate
   - User engagement rate = user_messages / tool_calls (INVERSE METRIC: lower = better)
   - Enables correlation queries: compliance vs success rate vs user engagement
   - Feeds ML models with labeled execution data

4. **ML Feature Integration** (`theauditor/insights/ml/features.py`)
   - Extends existing feature extraction to include Tier 5 data
   - Adds session-level features to training matrix
   - Maintains feature dimension consistency (97 features)

## Impact Analysis

### Benefits

**For ML Models**:
- High-quality labeled data showing successful vs failed approaches
- Process quality signals (not just code metrics)
- Enables learning: "Skip blueprint → 73% correction rate"

**For AI Agents** (Self-Correction):
- Agent can check historical patterns before executing
- Example: "78% of api.py edits fail when skipping blueprint → force myself to run blueprint first"
- Reduces bug introduction via learned best practices

**For Workflow Optimization**:
- Identify which workflow steps are critical (89% vs 34% success)
- Distinguish mandatory vs optional steps based on correlation data
- Update `planning.md` workflows with statistical evidence

**For Users**:
- Fewer corrections needed (agent learns from past mistakes)
- Faster development (agent uses proven approaches)
- Better code quality (changes scored before execution)

### Risks

**Low Implementation Risk**:
- Session parsing already implemented (`theauditor/session/parser.py`, `analyzer.py`)
- Diff scoring reuses existing SAST pipeline (no new analysis logic)
- Workflow checking is simple sequence validation

**Data Privacy**:
- All analysis is local-only (no external data sharing)
- Session logs contain user code (users should treat accordingly)
- Add `.claude/` to `.gitignore` if needed

**Storage Overhead**:
- Session logs: ~2-5MB per day of active development
- session_executions table: ~1KB per session (~100KB per month)
- Minimal impact compared to repo_index.db (91MB)

### Breaking Changes
**None**. This is a pure addition:
- Existing ML features continue to work
- Session analysis is optional (requires `--session-dir` flag)
- No changes to core analysis pipeline

## Success Criteria

1. **Execution Capture Works**
   - Parse 100+ sessions without errors
   - Extract all tool calls and diffs correctly
   - Handle timezone-aware timestamps

2. **Diff Scoring Works**
   - Run diffs through SAST pipeline
   - Generate risk scores (0.0-1.0)
   - Correlate scores with actual bug introduction

3. **Workflow Correlation Works**
   - Identify compliant vs non-compliant sessions
   - Show: compliant = 89% success, non-compliant = 34% success
   - Statistical significance (p < 0.05)

4. **ML Integration Works**
   - Tier 5 features added to training matrix
   - Models improve prediction accuracy by 5-10%
   - Feature importance shows Tier 5 contributes

5. **Self-Correction Works** (Future)
   - Agent queries historical patterns before executing
   - Agent skips approaches with <60% success rate
   - Measurable reduction in user corrections
   - Measurable reduction in user engagement rate (agent more self-sufficient)

## Implementation Scope

### Phase 1: Core Infrastructure (Current PR)
- [x] Session parser (DONE - `theauditor/session/parser.py`)
- [x] Session analyzer with pattern detection (DONE - `theauditor/session/analyzer.py`)
- [x] ML feature extraction (DONE - `theauditor/insights/ml/features.py`)
- [ ] DiffScorer component
- [ ] WorkflowChecker component
- [ ] session_executions table schema
- [ ] Persistence layer (fix dual-write violation)

### Phase 2: ML Integration
- [ ] Correlation analysis queries
- [ ] Statistical workflow enforcement
- [ ] Model training with Tier 5 features
- [ ] Validation: accuracy improvement measurement

### Phase 3: Self-Correction (Future)
- [ ] Agent query interface for historical patterns
- [ ] Proactive workflow enforcement
- [ ] Diff pre-scoring (before execution)

## Alternatives Considered

### Alternative 1: Analyze User Intent (REJECTED)
- **Idea**: Parse user messages to infer what they wanted
- **Problem**: User messages are contradictory, vague, and useless for deterministic analysis
- **Verdict**: TheAuditor is deterministic - focus on agent execution, not user intent

### Alternative 2: Simple ML Features Without Scoring (REJECTED)
- **Idea**: Just count blind edits, duplicate reads, etc. as simple features
- **Problem**: No correlation with actual code quality (all 4 features were zero for many files)
- **Verdict**: Need Layer 2 (SAST scoring) to connect execution patterns to code risk

### Alternative 3: Owen's Helix Approach (COMPLEMENTARY, NOT COMPETING)
- **Helix Focus**: User corrections, frustration detection, agent behavior correction
- **TheAuditor Focus**: Code quality verification, workflow compliance, diff scoring
- **Verdict**: Different goals - both valuable, not competing

## Related Changes
- None (first implementation of Tier 5)

## Validation Requirements
- [ ] `openspec validate ml-user-chats --strict` passes
- [ ] All spec scenarios have test coverage
- [ ] Integration tests cover end-to-end flow
- [ ] Documentation updated (Architecture.md, SESSION_ANALYSIS.md)

## Open Questions
1. Should session_executions table be in repo_index.db or separate session_analysis.db?
2. What threshold for "workflow compliance" score? (0.8? 1.0 only?)
3. Should diff scoring be synchronous or async? (batch processing vs real-time)
4. How to handle sessions without planning.md workflows? (mark as non-compliant or skip?)

## References
- `SESSION_ANALYSIS.md` - Current implementation documentation
- `planning.md` - Workflow definitions for compliance checking
- `Architecture.md` - ML system architecture (4-tier → 5-tier)
- `theauditor/insights/ml/features.py` - Existing ML feature extraction
- `openspec/specs/ml-intelligence/spec.md` - ML system requirements (to be updated)
