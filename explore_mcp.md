# MCP Context Servers for Autonomous Integration

## The Problem We're Trying to Solve

**Goal:** "Autonomous integration" - agents use TheAuditor proactively for every relevant task without forgetting.

**Current Approach:** Agent instruction files in `/agents/` with:
- ⚠️ MANDATORY TOOL USAGE ⚠️
- NON-NEGOTIABLE
- Phase → Task → Job structure
- Explicit command sequences

**Reality:** Agents still forget. They skip steps, read files directly, ignore database-first protocol.

**Why Prompts Fail:**
```
User: "Refactor auth.py"

Agent reads: agents/refactor_condensed.md
  ⚠️ MANDATORY: Run aud blueprint BEFORE reading files

Agent thinks: "I understand auth systems, I can just read the file..."

Agent: [reads file directly, skips all tools] ❌
```

LLMs are **bad at procedural compliance**. They:
- Get distracted by user requests
- Skip steps when they "think" they know the answer
- Optimize for appearing helpful over following protocol
- Don't have enforcement mechanisms

**Instructions ≠ Enforcement**

---

## What Are MCP Context Servers?

MCP (Model Context Protocol) has two types of servers:

### 1. Tool Servers (What Most People Think MCP Is)
```typescript
// LLM calls tools explicitly
const result = await theauditor.querySymbol({ symbol: 'AuthGuard' });
```

**Problem:** LLM still has to remember to call the tool.

### 2. Context Servers (The Solution to Autonomous Integration)
```typescript
// Context Server intercepts user message BEFORE LLM sees it
// Runs tools automatically based on triggers
// Injects results into context
// LLM receives message WITH context already loaded
```

**Key Difference:** Context Servers run **BEFORE** the LLM thinks. The LLM receives results automatically.

---

## How Context Servers Solve the Problem

### Current Flow (Prompt-Based)
```
User: "Refactor auth.py"
    ↓
Agent reads agent file instructions
    ↓
Agent decides: "Should I run aud blueprint?"
    ↓
Agent forgets / skips / gets distracted ❌
    ↓
Agent reads file directly (wrong approach)
```

### MCP Context Server Flow (Enforcement-Based)
```
User: "Refactor auth.py"
    ↓
MCP Context Server detects keyword "refactor"
    ↓
AUTOMATICALLY runs (no LLM decision):
  - aud blueprint --structure
  - aud deadcode
  - aud structure --monoliths
    ↓
Results injected into context
    ↓
Agent receives:
    User Message: "Refactor auth.py"

    [AUTOMATIC CONTEXT]
    Blueprint: snake_case 99%, auth/ pattern, monoliths: auth.py (3500 lines)
    Deadcode: auth.py ACTIVE (45 imports), legacy_auth.py DEPRECATED
    [END CONTEXT]
    ↓
Agent: "I see the blueprint shows..."  ✅
      (Can't skip - data is already there)
```

**The Critical Insight:** Triggers fire **BEFORE** agent sees the message. Agent can't forget because the data is pre-loaded.

---

## Implementation for TheAuditor

### Context Server Configuration

```typescript
// theauditor-mcp-context-server/config.ts

export const contextProviders = [
  {
    name: 'refactor-context',
    description: 'Auto-loads architectural context for refactoring tasks',
    triggers: {
      keywords: ['refactor', 'split', 'extract', 'modularize', 'merge', 'consolidate'],
      filePatterns: ['*.py', '*.js', '*.ts'],
    },
    action: async (userMessage: string, context: Context) => {
      // Extract file mentions from user message
      const files = extractFileMentions(userMessage);

      // Run TheAuditor commands automatically
      const blueprint = await exec('aud blueprint --structure');
      const deadcode = await exec('aud deadcode');
      const structure = await exec('aud structure --monoliths');

      // Check if any mentioned files are monoliths (>2150 lines)
      const monoliths = parseMonoliths(structure);
      const mentionedMonoliths = files.filter(f => monoliths.includes(f));

      // Return structured context to inject
      return {
        type: 'refactor_context',
        display: 'Refactor Context (Auto-loaded)',
        data: {
          blueprint: parseBlueprintOutput(blueprint),
          deadcode: parseDeadcodeOutput(deadcode),
          monoliths: mentionedMonoliths,
          warning: mentionedMonoliths.length > 0
            ? `Files require chunked reading: ${mentionedMonoliths.join(', ')}`
            : null
        }
      };
    }
  },

  {
    name: 'security-context',
    description: 'Auto-loads security analysis for vulnerability discussions',
    triggers: {
      keywords: ['security', 'vulnerability', 'XSS', 'SQL injection', 'CSRF',
                 'taint', 'sanitize', 'validate', 'exploit', 'attack'],
    },
    action: async (userMessage: string) => {
      // Run security analysis tools automatically
      const taint = await exec('aud taint-analyze --severity high');
      const boundaries = await exec('aud boundaries --type input-validation');
      const blueprint = await exec('aud blueprint --structure');

      // Extract framework context (for matching recommendations)
      const frameworks = parseFrameworks(blueprint);

      return {
        type: 'security_context',
        display: 'Security Context (Auto-loaded)',
        data: {
          taint_findings: parseTaintOutput(taint),
          boundary_violations: parseBoundariesOutput(boundaries),
          detected_frameworks: frameworks,
          validation_library: frameworks.validation, // zod, joi, marshmallow, etc.
        }
      };
    }
  },

  {
    name: 'planning-context',
    description: 'Auto-loads codebase structure for planning tasks',
    triggers: {
      keywords: ['plan', 'planning', 'architecture', 'design', 'structure'],
    },
    action: async () => {
      const blueprint = await exec('aud blueprint --structure');
      const query = await exec('aud query --list-symbols');

      return {
        type: 'planning_context',
        display: 'Planning Context (Auto-loaded)',
        data: {
          blueprint: parseBlueprintOutput(blueprint),
          symbol_index: parseQueryOutput(query),
        }
      };
    }
  },

  {
    name: 'symbol-context',
    description: 'Auto-loads symbol details when specific symbols mentioned',
    triggers: {
      // Detects symbol mentions like "AuthGuard", "validateUser", etc.
      symbolMention: true, // Custom trigger type
    },
    action: async (userMessage: string) => {
      const symbols = extractSymbolMentions(userMessage);

      // Query each mentioned symbol
      const symbolData = await Promise.all(
        symbols.map(async (symbol) => {
          const callers = await exec(`aud query --symbol ${symbol} --show-callers`);
          const callees = await exec(`aud query --symbol ${symbol} --show-callees`);

          return {
            symbol,
            callers: parseQueryOutput(callers),
            callees: parseQueryOutput(callees),
          };
        })
      );

      return {
        type: 'symbol_context',
        display: `Symbol Context (Auto-loaded for: ${symbols.join(', ')})`,
        data: symbolData,
      };
    }
  },

  {
    name: 'file-open-context',
    description: 'Auto-loads context when file opened in editor',
    triggers: {
      onFileOpen: true, // Editor integration trigger
    },
    action: async (filePath: string) => {
      // Run analysis on the opened file
      const blueprint = await exec(`aud blueprint --file ${filePath}`);
      const query = await exec(`aud query --file ${filePath} --show-dependents`);

      return {
        type: 'file_context',
        display: `File Context (Auto-loaded for ${filePath})`,
        data: {
          file_analysis: parseBlueprintOutput(blueprint),
          dependents: parseQueryOutput(query),
        }
      };
    }
  },
];
```

### Agent Instructions Become Simpler

**Before (agents/refactor_condensed.md):**
```markdown
## ⚠️ MANDATORY TOOL USAGE - NON-NEGOTIABLE ⚠️

**CRITICAL:** Run TheAuditor commands autonomously. NO file reading until Phase 3 Task 3.4.

### T1.1: Read Command Help
- aud --help, aud query --help, aud deadcode --help

### T1.2: Run Deadcode Analysis
- aud deadcode 2>&1 | grep <target>

### T1.3: Check File Header
- Read first 50 lines...

[15 more tasks with explicit command sequences]
```

**After (with MCP Context Server):**
```markdown
# Refactor Agent

**Context Pre-Loaded Automatically:**
- Blueprint analysis (naming conventions, precedents, frameworks)
- Deadcode analysis (active vs deprecated files)
- Structure analysis (monoliths requiring chunked reading)

**Your Responsibilities:**
1. **Review pre-loaded context** - Blueprint, deadcode, and structure data is already in your context
2. **Follow precedents** - Use naming conventions and patterns from blueprint
3. **Run additional queries if needed** - `aud query --symbol X` for specific details
4. **Chunked reading for monoliths** - Files >2150 lines listed in context
5. **Present facts, let user decide** - Zero recommendation policy

**Workflow:**
- Context is auto-injected when user says "refactor"
- You DON'T need to run blueprint/deadcode/structure (already done)
- Focus on analysis and presenting options
- User makes final decisions
```

**Much simpler.** The hard part (remembering to run tools) is handled by MCP Context Server.

---

## Comparison: TheAuditor vs Anthropic's MCP Article

### Anthropic's Problem (from article)
- Tool definitions overload context (1000s of tools = 150k tokens)
- Intermediate results flow through context (10,000 row spreadsheet)

**Their Solution:** Code execution to filter data before it reaches LLM

### TheAuditor's Problem (different)
- ✅ Tool definitions already minimal (30 commands ≈ 3k tokens)
- ✅ Results already filtered (database queries return focused data)
- ❌ **Agents forget to use tools proactively**

**Your Solution Needed:** Context Servers to enforce tool usage automatically

### Why Your Use Case Is Different

**Anthropic's focus:** Efficiency (reduce tokens)
**Your focus:** Compliance (ensure tools are used)

**Both use MCP, different aspects:**
- Anthropic: Code execution + Tool Servers
- You: Context Servers (auto-injection)

---

## Benefits of MCP Context Server for TheAuditor

### 1. Architectural Enforcement (vs Prompt Compliance)

**Prompt-based (fails):**
```
"⚠️ MANDATORY: Run aud blueprint first"
→ LLM decides whether to follow
→ LLM forgets / skips
```

**Context Server (succeeds):**
```
User says "refactor" → Trigger fires → Commands run → Results injected
→ LLM receives results automatically
→ Can't forget (data is already there)
```

### 2. Consistent Tool Usage Across All Agents

**Before:** Each agent file duplicates tool invocation logic
```
refactor_condensed.md:    "Run aud blueprint"
security_condensed.md:    "Run aud blueprint"
planning_condensed.md:    "Run aud blueprint"
```

**After:** Centralized trigger definitions
```typescript
// Single source of truth
triggers: {
  keywords: ['refactor', 'security', 'planning'],
  action: async () => await exec('aud blueprint')
}
```

### 3. Framework-Aware Recommendations (Automatic)

**Current problem:** Agent recommends `joi` when codebase uses `zod`

**With Context Server:**
```typescript
// Auto-extracts framework from blueprint
const frameworks = parseFrameworks(blueprint);
// Injects: { validation_library: 'zod' }

// Agent sees in context:
"Detected validation library: zod 3.22.0"

// Agent recommendation:
"Use zod.string().email() for validation" ✅
(matches detected framework automatically)
```

### 4. Multi-Tenant Boundary Analysis (Automatic)

**Trigger:** User mentions "tenant", "multi-tenant", "RLS"

**Context Server automatically runs:**
```bash
aud boundaries --type multi-tenant
aud taint-analyze --severity critical
```

**Agent receives:**
```
[CONTEXT]
Multi-Tenant Analysis:
- 8 queries missing tenant_id filter (CRITICAL)
- 3 user-controlled tenant_id sources (LAWSUIT RISK)
- 12 tenant checks after database access (distance > 0)
[END CONTEXT]
```

Agent can't analyze multi-tenant code without this context.

### 5. Proactive Deadcode Detection

**Trigger:** User mentions file name

**Context Server checks:**
```bash
aud deadcode | grep <filename>
```

**If deprecated:**
```
[CONTEXT]
WARNING: legacy_auth.py is DEPRECATED
- Confidence: HIGH
- Imports: 0
- Replacement: auth/service.py
- Header: "Phase 2.1 - kept for rollback only"

DO NOT refactor deprecated files. Suggest deletion instead.
[END CONTEXT]
```

Agent stops refactor work on deprecated files automatically.

---

## Implementation Effort

### Phase 1: Basic Context Server (1-2 days)
1. Create MCP Context Server project (TypeScript)
2. Define trigger for "refactor" keyword
3. Auto-run: `aud blueprint`, `aud deadcode`, `aud structure`
4. Inject results into context
5. Test with Claude Desktop / Continue

### Phase 2: Security Context (1 day)
1. Add trigger for security keywords
2. Auto-run: `aud taint-analyze`, `aud boundaries`
3. Extract framework from blueprint
4. Test framework-matching in recommendations

### Phase 3: Symbol & File Triggers (1-2 days)
1. Symbol mention detection (regex/NLP)
2. Auto-run: `aud query --symbol X --show-callers`
3. File open integration (editor plugin)
4. Auto-run: `aud blueprint --file X`

### Phase 4: Advanced Features (2-3 days)
1. Planning context (blueprint + symbol index)
2. Multi-tenant context (RLS + boundary analysis)
3. Monolith detection with chunking warnings
4. Custom trigger rules (user-configurable)

**Total: ~1 week of focused development**

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  User Message                                           │
│  "Refactor auth.py to split into modules"              │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  MCP Context Server (Intercepts Message)                │
│                                                          │
│  Trigger Detection:                                      │
│    ✓ Keyword: "refactor"                                │
│    ✓ File mention: "auth.py"                            │
│                                                          │
│  Actions Fired:                                          │
│    → exec('aud blueprint --structure')                  │
│    → exec('aud deadcode | grep auth.py')                │
│    → exec('aud structure --monoliths')                  │
│                                                          │
│  Context Built:                                          │
│    {                                                     │
│      blueprint: { naming: 'snake_case 99%', ... },      │
│      deadcode: { status: 'ACTIVE', imports: 45 },       │
│      monoliths: ['auth.py'],                            │
│      warning: 'auth.py requires chunked reading'        │
│    }                                                     │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Enhanced Message to Agent                               │
│                                                          │
│  User: "Refactor auth.py to split into modules"         │
│                                                          │
│  [AUTOMATIC CONTEXT - REFACTOR]                         │
│  Blueprint Analysis:                                     │
│    - Naming: snake_case (99%)                           │
│    - Precedents: auth/ directory pattern (15 files)     │
│    - Frameworks: Flask, SQLAlchemy, zod                 │
│                                                          │
│  Deadcode Analysis:                                      │
│    - auth.py: ACTIVE (45 imports)                       │
│    - Status: Safe to refactor                           │
│                                                          │
│  Structure Warning:                                      │
│    - auth.py: 3500 lines (MONOLITH)                     │
│    - Requires chunked reading (1500-line chunks)        │
│  [END CONTEXT]                                           │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Agent Processing                                        │
│                                                          │
│  Agent sees:                                             │
│    ✓ User request                                       │
│    ✓ Pre-loaded blueprint data                          │
│    ✓ Pre-loaded deadcode status                         │
│    ✓ Monolith warning                                   │
│                                                          │
│  Agent CAN'T skip context (already injected)            │
│  Agent follows precedents from blueprint                │
│  Agent uses chunked reading for monolith                │
└─────────────────────────────────────────────────────────┘
```

---

## Alternatives Considered

### 1. Stricter Agent Prompts
**Tried:** agents/refactor_condensed.md with ⚠️ MANDATORY ⚠️

**Result:** Agents still forget

**Why it fails:** Instructions ≠ Enforcement

### 2. Task Tool with Sub-Agents
**Tried:** Launch specialized agents for each task

**Result:** Sub-agents also forget to use tools

**Why it fails:** Sub-agents have same prompt-following limitations

### 3. Hardcoded Workflows (No LLM)
**Example:** Shell script that runs commands in sequence

**Why not ideal:**
- Loses LLM flexibility
- Can't adapt to context
- User has to manually trigger

### 4. MCP Tool Server (Not Context Server)
**What it does:** Exposes TheAuditor commands as MCP tools

**Why insufficient:**
- LLM still decides when to call tools
- Doesn't solve "forgetting" problem
- Same as current CLI approach

### 5. MCP Context Server (BEST OPTION)
**What it does:** Automatically runs commands on triggers, injects results

**Why it works:**
- ✅ Architectural enforcement (not prompt-based)
- ✅ Triggers fire before LLM thinks
- ✅ LLM can't skip (data pre-loaded)
- ✅ Still allows LLM flexibility for additional queries

---

## Decision Framework

### When NOT to Build MCP Context Server

**If:**
- You're okay with agents forgetting sometimes
- Manual reminders are acceptable
- Prompts work "well enough"
- You don't have 1 week to implement

**Then:** Stick with current agent files + manual oversight

### When TO Build MCP Context Server

**If:**
- Autonomous integration is critical
- Agents must use tools proactively every time
- You want enforcement, not just instructions
- You have 1 week to invest

**Then:** Build MCP Context Server

---

## What This Enables

### Scenario 1: Refactor Flow (Fully Autonomous)
```
User: "Refactor auth.py - it's getting too large"

[MCP Context Server fires]
→ Loads blueprint (precedents: auth/ pattern)
→ Loads deadcode (status: ACTIVE)
→ Loads structure (monolith: 3500 lines)

Agent receives all context automatically

Agent: "I see auth.py is a monolith with 3500 lines. The blueprint shows
       an existing auth/ directory pattern with 15 files using snake_case.

       Precedent analysis:
       - auth/service.py (450 lines) - core auth logic
       - auth/middleware.py (280 lines) - request handling
       - auth/validators.py (190 lines) - input validation

       Your auth.py could follow this pattern. Should I proceed with
       planning the split?"

User: "Yes, plan it"

Agent: [runs aud query to find dependencies]
       [generates split plan following precedents]
```

**No steps skipped. No forgetting. Blueprint precedents followed automatically.**

### Scenario 2: Security Analysis (Framework-Aware)
```
User: "Check for XSS vulnerabilities in the user profile page"

[MCP Context Server fires]
→ Loads taint analysis
→ Loads boundary analysis
→ Loads blueprint (framework: zod detected)

Agent receives context with detected validation library: zod

Agent: "Taint analysis found 3 potential XSS vectors:

       1. user.bio flows to innerHTML (HIGH)
          - No sanitization detected
          - Distance to validation: 2 (validation too late)

       2. user.website flows to <a href> (MEDIUM)
          - URL not validated
          - Distance to validation: None (missing)

       Recommendations (using detected framework):
       - Add zod.string().url() for website validation
       - Add DOMPurify.sanitize() for bio before rendering

       (Note: Using zod because blueprint detected zod 3.22.0 in codebase)"
```

**Framework automatically detected. Recommendations match codebase. No guessing.**

### Scenario 3: Multi-Tenant Analysis (Proactive Safety)
```
User: "Add a feature to let users view order history"

[MCP Context Server detects this is a data access feature]
→ Loads multi-tenant boundary analysis
→ Loads existing RLS patterns

Agent receives tenant boundary context automatically

Agent: "Before implementing, I checked multi-tenant boundaries.

       Existing patterns:
       - All order queries include: WHERE tenant_id = req.user.tenantId
       - Validation occurs at distance 0 (in route handler)

       WARNING: Boundary analysis found 8 existing queries missing
       tenant_id filters. This is a high-risk pattern.

       For your new feature, ensure:
       1. tenant_id from req.user.tenantId (authenticated source)
       2. WHERE tenant_id = ? in query (distance 0)
       3. Never accept tenant_id from req.query (user-controlled)

       Should I proceed with implementation following secure patterns?"
```

**Multi-tenant safety checks happen proactively, not as afterthought.**

---

## Recommendation

**Build the MCP Context Server.**

### Why
1. It's the **only** solution that enforces autonomous tool usage
2. Your agent prompts already prove instructions don't work
3. Investment: 1 week → Permanent solution to "forgetting" problem
4. Enables true autonomous integration (your stated goal)

### When
- After boundary analysis is stable (done)
- When you have 1 week focused time
- Before scaling to more complex workflows

### How
- Start with refactor context (highest value)
- Add security context next (framework matching critical)
- Add symbol/file contexts last (nice-to-have)

### Success Criteria
- Agent never skips blueprint/deadcode when user says "refactor"
- Security recommendations always match detected framework
- Multi-tenant boundary analysis runs automatically for data access tasks
- Monolith warnings appear before agent tries to read 3500-line files

---

## Resources

### MCP Documentation
- MCP Spec: https://modelcontextprotocol.io/
- Context Servers: https://modelcontextprotocol.io/docs/concepts/servers#context-servers
- TypeScript SDK: https://github.com/modelcontextprotocol/typescript-sdk

### Related Articles
- Anthropic MCP Code Execution: https://www.anthropic.com/news/code-execution-with-mcp
- Cloudflare Code Mode: https://blog.cloudflare.com/mcp-code-mode

### TheAuditor Integration Points
- Current CLI commands: `aud --help`
- Agent instruction files: `./agents/`
- Database schema: `.pf/repo_index.db`
- Existing queries: `aud query`, `aud blueprint`, `aud boundaries`

---

## Next Steps

If you decide to build this:

1. **Prototype (Day 1-2)**
   - Simple MCP Context Server
   - Single trigger: "refactor" keyword
   - Auto-run: `aud blueprint`
   - Test in Claude Desktop

2. **Validate (Day 3)**
   - Test with real refactor scenarios
   - Verify context injection works
   - Confirm agent uses injected data

3. **Expand (Day 4-5)**
   - Add security context
   - Add framework detection
   - Add monolith warnings

4. **Polish (Day 6-7)**
   - Error handling
   - Configuration file for triggers
   - Documentation
   - Integration testing

5. **Deploy**
   - Update agent instruction files (simplified)
   - Announce MCP Context Server availability
   - Gather feedback on autonomous integration quality

---

## Conclusion

**The problem:** Agents forget to use TheAuditor tools despite strict prompts.

**The cause:** LLMs are bad at procedural compliance. Instructions ≠ Enforcement.

**The solution:** MCP Context Servers enforce tool usage architecturally by:
- Running commands automatically on triggers (before LLM thinks)
- Injecting results into context (LLM can't skip)
- Removing need for LLM to "remember" to use tools

**Your choice:**
- Keep fighting with prompts (you'll lose) ❌
- Build MCP Context Server (1 week, permanent solution) ✅

For "autonomous integration," MCP Context Servers are the answer.
