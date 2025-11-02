# Planning System - Phase 3: Integration Testing & Real-World Validation
**Document Version:** 3.0
**Protocol:** TeamSOP v4.20
**Date Started:** 2025-11-03
**Status:** **PHASE 1 & 2 COMPLETE ✅ | PHASE 3 IN PROGRESS**

---

## Executive Summary

**What's Done:**
- ✅ Phase 1: All 4 prerequisites complete (naming, precedents, refactor history, frameworks)
- ✅ Phase 2: Agent infrastructure complete (4 agents, installation, triggers, workflows)

**What's NOT Done:**
- ❌ End-to-end workflow testing (never actually used the agents)
- ❌ Real-world validation (does it prevent hallucination in practice?)
- ❌ Agent refinement based on actual usage
- ❌ Integration verification (blueprint → query → synthesis actually works?)

**The Gap:**
Previous planning.md documented building the infrastructure but didn't account for the real work: actually USING the system and iterating based on what sucks.

---

## Phase 3: Integration Testing & Real-World Validation

**Status:** IN PROGRESS
**Objective:** Prove the agent system works end-to-end, iterate on what's broken, validate zero hallucination in practice

### Task 3.1: End-to-End Workflow Testing

**Goal:** Test complete planning workflow from trigger to synthesis

**Test Cases:**

1. **Refactor Planning Workflow**
   ```
   User: "refactor storage.py into domain-specific files"

   Expected Flow:
   1. Agent triggers automatically (keyword: "refactor")
   2. Agent reads @/.theauditor_tools/agents/refactor.md
   3. Agent runs: aud blueprint --structure
   4. Agent sees: schemas/ precedent (domain split pattern)
   5. Agent runs: aud query --file storage.py --show-functions
   6. Agent sees: _store_python_*, _store_react_* (domain clusters)
   7. Agent synthesizes: Split following schemas/ precedent
   8. Agent outputs: Plan anchored in query results (no hallucination)

   Success Criteria:
   - [ ] Agent triggers automatically
   - [ ] Blueprint runs FIRST (before any file reading)
   - [ ] Query commands execute with database queries
   - [ ] Plan cites specific query results (line numbers, counts)
   - [ ] Zero hallucination (no invented patterns)
   - [ ] No file reading (all data from aud commands)
   ```

2. **Security Planning Workflow**
   ```
   User: "check for XSS vulnerabilities in user input handling"

   Expected Flow:
   1. Agent triggers (keyword: "XSS")
   2. Agent reads @/.theauditor_tools/agents/security.md
   3. Agent runs: aud blueprint --structure (framework detection)
   4. Agent runs: aud context query --security-rules
   5. Agent runs: aud query --pattern "req.body" --show-usage
   6. Agent synthesizes: Security analysis anchored in query results

   Success Criteria:
   - [ ] Security agent triggers (not general planning)
   - [ ] Framework-aware queries (uses detected frameworks)
   - [ ] Taint analysis integration (if applicable)
   - [ ] Findings cite specific files/lines from database
   ```

3. **Greenfield Planning Workflow**
   ```
   User: "plan implementation for new payment processing feature"

   Expected Flow:
   1. Agent triggers (keyword: "plan")
   2. Agent reads @/.theauditor_tools/agents/planning.md
   3. Agent runs: aud blueprint --structure (finds analogous patterns)
   4. Agent runs: aud query --pattern "payment" --show-callers
   5. Agent runs: aud query --api "/payment" (if API routes exist)
   6. Agent synthesizes: Implementation plan following existing patterns

   Success Criteria:
   - [ ] Agent finds analogous implementations (if any exist)
   - [ ] Agent uses detected frameworks for tech stack
   - [ ] Agent follows naming conventions from blueprint
   - [ ] Plan includes specific files/functions to emulate
   ```

**Deliverables:**
- [ ] Test session logs (markdown format)
- [ ] Success/failure documentation
- [ ] List of gaps/failures in agent prompts
- [ ] Performance metrics (time to plan, query count)

---

### Task 3.2: Agent Refinement Based on Real Usage

**Goal:** Fix broken patterns, improve agent prompts, add missing command examples

**Refinement Process:**
1. Run test cases from Task 3.1
2. Document every failure (hallucination, wrong sequence, missing command)
3. Identify root cause (unclear prompt, missing example, wrong trigger)
4. Update agent files (planning.md, refactor.md, security.md, dataflow.md)
5. Re-test to confirm fix

**Known Gaps to Address:**
- [ ] Agents may not know all aud command flags (need command reference)
- [ ] Agents may skip blueprint if user prompt is too specific
- [ ] Agents may guess patterns instead of querying when database is empty
- [ ] Agents may not know how to handle "no precedents found" case
- [ ] Trigger keywords may be too narrow (missing common phrases)

**Iteration Checklist:**
- [ ] Update agent trigger keywords based on real usage
- [ ] Add concrete command examples for common scenarios
- [ ] Document edge cases (empty database, no precedents, new project)
- [ ] Add fallback instructions (what to do when query returns nothing)
- [ ] Strengthen "MANDATORY SEQUENCE" language if skipped

---

### Task 3.3: Integration Verification

**Goal:** Verify each component works together (blueprint + query + agents + triggers)

**Component Integration Tests:**

1. **Blueprint → Agent Integration**
   - [ ] Run `aud blueprint --structure` manually
   - [ ] Verify naming conventions show correctly
   - [ ] Verify architectural precedents display
   - [ ] Verify framework detection accurate
   - [ ] Verify refactor history appears
   - [ ] Agent can parse blueprint output correctly

2. **Query → Agent Integration**
   - [ ] Agent can execute `aud query --file X --show-functions`
   - [ ] Agent can parse query JSON output
   - [ ] Agent can execute `aud query --symbol X --show-callers`
   - [ ] Agent anchors decisions in query results (cites line numbers)

3. **Trigger → Agent Integration**
   - [ ] Test trigger insertion: `aud planning setup-agents --target AGENTS.md`
   - [ ] Verify trigger block appears in AGENTS.md
   - [ ] Verify no duplicate triggers on re-run
   - [ ] Test keyword matching (refactor, plan, security, XSS, etc.)
   - [ ] Verify correct agent loads for each keyword

4. **Installation → Agent Integration**
   - [ ] Fresh install: `aud setup-ai --target .`
   - [ ] Verify agents copied to `.auditor_venv/.theauditor_tools/agents/`
   - [ ] Verify 4 agent files present (planning, refactor, security, dataflow)
   - [ ] Verify file permissions correct
   - [ ] Test on clean project (no .auditor_venv exists)

**Deliverables:**
- [ ] Integration test report (pass/fail for each component)
- [ ] Bug list (integration failures)
- [ ] Performance baseline (time for full workflow)

---

### Task 3.4: Documentation & User Guide

**Goal:** Document how to use the agent system for end users

**Documentation Needed:**

1. **User Guide: Getting Started with Planning Agents**
   - [ ] How to install (`aud setup-ai`)
   - [ ] How to trigger agents (keyword list)
   - [ ] What to expect (blueprint → query → synthesis flow)
   - [ ] Example sessions (refactor, security, greenfield)

2. **Agent Workflow Reference**
   - [ ] Planning agent: When to use, what it does, command examples
   - [ ] Refactor agent: When to use, what it does, command examples
   - [ ] Security agent: When to use, what it does, command examples
   - [ ] Dataflow agent: When to use, what it does, command examples

3. **Troubleshooting Guide**
   - [ ] Agent didn't trigger (check AGENTS.md trigger block)
   - [ ] Agent hallucinated (check if blueprint ran first)
   - [ ] Agent skipped query (check agent prompt clarity)
   - [ ] No precedents found (expected for new projects)

**Deliverable:**
- [ ] `docs/agents/USER_GUIDE.md` (new file)
- [ ] Update README.md with agent system overview
- [ ] Add examples to `docs/agents/examples/` directory

---

### Task 3.5: Validation Metrics

**Goal:** Measure if the system achieves zero hallucination goal

**Metrics to Track:**

1. **Hallucination Rate**
   - Definition: Agent invents pattern not present in database query results
   - Measurement: Manual review of 10 planning sessions
   - Target: 0% hallucination rate
   - [ ] Run 10 test sessions
   - [ ] Mark hallucinations (invented names, wrong counts, fake patterns)
   - [ ] Calculate: (hallucinations / total decisions) * 100

2. **Query Coverage**
   - Definition: Percentage of decisions backed by database query
   - Measurement: Count decisions vs query citations
   - Target: 100% query coverage
   - [ ] Run 5 test sessions
   - [ ] Count total decisions made
   - [ ] Count decisions with query citation (file:line, count, pattern)
   - [ ] Calculate: (cited decisions / total decisions) * 100

3. **Workflow Compliance**
   - Definition: Agent follows blueprint → query → synthesis sequence
   - Measurement: Check if blueprint runs before synthesis
   - Target: 100% compliance
   - [ ] Run 10 test sessions
   - [ ] Mark sessions where blueprint skipped or run after synthesis
   - [ ] Calculate: (compliant sessions / total sessions) * 100

4. **Performance**
   - Definition: Time from user request to plan delivery
   - Measurement: Timestamp analysis
   - Target: <2 minutes for typical workflow
   - [ ] Run 5 test sessions
   - [ ] Record: time to trigger, time for blueprint, time for queries, time for synthesis
   - [ ] Calculate average and p95

**Deliverable:**
- [ ] Metrics report (markdown table with results)
- [ ] Pass/fail assessment (did we hit targets?)
- [ ] Improvement recommendations (if targets missed)

---

## Success Criteria for Phase 3

### Must-Have (P0)
- [ ] End-to-end refactor workflow tested (Task 3.1.1)
- [ ] Agent triggers automatically on keywords
- [ ] Blueprint runs FIRST in every workflow
- [ ] Zero hallucination in test sessions (Task 3.5.1)
- [ ] 100% query coverage (Task 3.5.2)
- [ ] Integration tests pass (Task 3.3)

### Should-Have (P1)
- [ ] All 3 workflows tested (refactor, security, greenfield)
- [ ] Agent prompts refined based on failures (Task 3.2)
- [ ] User guide written (Task 3.4)
- [ ] Metrics report complete (Task 3.5)

### Nice-to-Have (P2)
- [ ] Performance optimization (<1 minute workflows)
- [ ] Advanced examples (complex refactors, multi-step plans)
- [ ] Agent composition (one agent calling another)

---

## Current Status

**Phase 1:** ✅ COMPLETE (4 prerequisites: naming, precedents, refactor history, frameworks)

**Phase 2:** ✅ COMPLETE (4 agents created, installation working, triggers functional)

**Phase 3:** 🔄 IN PROGRESS (infrastructure exists, real testing hasn't started)

**Next Action:** Start Task 3.1 - End-to-End Workflow Testing with refactor scenario

---

## Handoff Notes

**For Next Session:**

The infrastructure is DONE. Database has the data, blueprint exposes it, agents are written, triggers work.

**What's NOT done:**
- Haven't actually USED the agents in a real planning session
- Haven't verified they prevent hallucination in practice
- Haven't iterated on prompts based on failures
- Haven't measured if it works

**Next Steps:**
1. Pick a real refactor task (e.g., "split storage.py")
2. Trigger the agent (use refactor keyword)
3. Observe: Does blueprint run first? Do queries execute? Is plan anchored in results?
4. Document failures (hallucinations, wrong sequence, missing commands)
5. Fix agent prompts
6. Repeat until zero hallucination achieved

**This is the REAL work.** Everything before was just building the foundation.
