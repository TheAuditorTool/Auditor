TheAuditor Planning Feature - Architecture & Design Document

Version: 1.2
Date: 2025-10-28
Author: Gemini (incorporating feedback from TheAuditorA)
Target Audience: AI Agents, Future Developers (including potentially impaired future selves), Collaborators

1. Introduction & Goals

1.1. Purpose

The aud planning feature integrates task planning, execution tracking, and ground-truth verification directly into TheAuditor's existing database-centric ecosystem (repo_index.db, graphs.db). It serves as the primary, deterministic state and context source for AI coding agents, explicitly replacing inefficient, unreliable file-based planning workflows. This system is designed for AI agents first, enabling autonomous operation grounded in verifiable codebase reality.

1.2. Core Philosophy: Truth Courier for Planning, Execution & Verification

Consistent with TheAuditor's core philosophy ("tools for AI agents"), aud planning:

Does NOT generate plans: Relies on external inputs (human or AI LLM) for initial task creation via add-task.

Stores plan state as structured data in the Database: Provides a schema (repo_index.db) for plans, tasks, statuses, verification criteria, and results. The database IS the plan, eliminating external file parsing.

Mandates Factual Context Gathering via TheAuditor Tools: Requires the AI agent to use aud query, aud blueprint, aud context (--format json) to gather ground-truth information relevant to tasks instead of reading source files directly. Tool enhancement is prioritized over bypassing.

Provides Deterministic Verification Against Codebase State: Includes a core mechanism (verify-task) that checks task completion by running deterministic queries (query.py, profiles.py logic) against the actual codebase state reflected in repo_index.db after code changes and re-indexing (aud index).

Outputs Structured Data: Communicates exclusively via JSON (--format json), designed for direct consumption and action by AI agents. Human observation occurs via the AI's terminal output of this structured data.

1.3. Benefits

Eliminates Token Waste & Latency: Replaces reading/parsing multiple large text files with targeted, fast database queries for state and context.

Maximizes Reliability: Uses structured database state and deterministic verification checks against indexed code, eliminating brittle LLM parsing/interpretation of markdown files for state management.

Grounds AI Actions: Provides AI agents with accurate, verifiable context and state directly from the database, minimizing hallucination and errors.

Enables True Automation & Resilience: Creates a robust, closed-loop framework for AI agents to manage complex tasks autonomously with verifiable progress tracking derived from the codebase ground truth. Progress is stateless and can be re-verified after interruptions by simply running aud index and aud planning verify-task.

Maintains Determinism & Verifiability: Extends TheAuditor's goal of providing verifiable facts into the planning and execution phases.

2. Problem Addressed: Rejecting Inefficient & Unreliable File-Based AI Planning

Current approaches (e.g., OpenSpec [cite: openspec_readme.md]) relying on conventions involving multiple Markdown files are unsuitable for efficient, reliable AI agent operation:

Extreme Latency & Cost: Force agents into slow, expensive cycles of reading/parsing large text files.

Brittle State Management: LLM interpretation of task status or spec details from Markdown is failure-prone.

State Desynchronization: Markdown reflects intent, not the verifiable state of the codebase. Verification is unreliable.

Inefficient Context: Forces AI agents to process verbose, human-readable text instead of optimized, structured, factual data.

aud planning rejects this paradigm by making the plan, its tasks, and their verification integral parts of TheAuditor's indexed, queryable, and deterministically verifiable database state.

3. Architecture

3.1. Database-Centric State Management (The Core Principle)

All planning state resides within .pf/repo_index.db. No external plan files. The database tables track plan/task definitions, execution status, and verification results based on codebase analysis.

3.2. Mandatory Integration with TheAuditor's Analysis Engine

The AI agent workflow mandates the use of TheAuditor's analysis engine:

AI Agent Context Gathering (Mandatory Tool Usage): Before attempting any task, the AI agent must use aud query, aud blueprint, aud context (--format json) to retrieve necessary code understanding from the database. Direct source file reading is forbidden for planning/context. Missing information requires enhancing TheAuditor's extractors or queries.

Refactor Profile Generation (AI Task): For refactoring, the AI agent must use aud query (e.g., pattern_search, get_callers) to gather facts about legacy/target patterns before generating the refactor_profile.yaml. This profile is then used deterministically by verify-task.

Verification via Core Engine (verify-task): This command directly invokes TheAuditor's deterministic logic (query.py, profiles.py) to check plan_specs against the current repo_index.db state after the AI runs aud index.

3.3. Deterministic Verification (verify-task)

This mechanism provides reliable pass/fail feedback by executing specific, deterministic queries/checks against the database based on optional plan_specs linked to the task. It replaces unreliable LLM self-assessment or markdown parsing.

3.4. AI Agent Focus & Workflow

Designed for AI agent CLI interaction using --format json. The database is the single source of truth for plan state and verification. (See Section 6).

3.5. Stateless Deterministic Verification (Unique Value Proposition)

A key advantage is the ability to deterministically verify the true state of task completion at any time, independent of prior agent state or markdown files.
Workflow:

Agent makes code changes.

Agent (or user) runs aud index (or aud full). This updates repo_index.db to reflect the actual codebase state.

Agent (or user) runs aud planning verify-task --task-id X.

verify-task runs its deterministic checks (e.g., RefactorRuleEngine checks based on plan_specs) against the freshly updated database.
Result: The verification status accurately reflects whether the task's criteria are met in the current code, regardless of interruptions, agent errors, or corrupted external state. This provides unparalleled resilience and reliability compared to file-based or LLM-interpreted state.

4. Database Schema Design (.pf/repo_index.db)

(Schema remains the same as Version 1.1 - plans, plan_tasks, plan_specs tables with appropriate columns, types, constraints, and indices)

Schema Integration:

Add table definitions to theauditor/indexer/schema.py.

Update theauditor/indexer/database.py's initialize_schema() to create tables and indices.

5. CLI Command Design (aud planning ...)

Primary Interface: aud planning <subcommand> [options]
Primary Output Format: JSON (--format json) for AI. Text secondary.

(Subcommand definitions: init, show, add-task, update-task, verify-task, archive remain largely the same as Version 1.1, emphasizing JSON output and deterministic database operations. verify-task description reinforced)

5.5. aud planning verify-task (Reinforced Description)

Purpose: Deterministically verify task completion criteria against the current repo_index.db state. Assumes aud index has been run after relevant code changes.

Arguments: --task-id INTEGER (Req), --format json (Default).

Actions:

Retrieves task and linked plan_specs from DB.

If specs exist: Executes deterministic checks using TheAuditor engine (CodeQueryEngine, RefactorRuleEngine) based on spec_type/target/params against the current database.

If no specs: Passes if plan_tasks.status is 'done'.

Determines verification_status ('passed'/'failed').

Stores structured results in verification_details (JSON).

Updates verification_status in plan_tasks.

Output (JSON): task_id, verification_status, details (structured verification results).

6. AI Agent Workflow (Detailed Steps - Emphasizing Tool Reliance & Verification Loop)

This flow mandates tool usage and highlights the core verification loop.

Goal Assignment: User -> AI Goal.

Plan Initialization: AI -> aud planning init --goal "..." -> Gets plan_id.

(Optional) Initial Task Generation (AI Responsibility):

AI -> aud blueprint --format json / aud query ... --format json -> Gathers initial context from the database.

AI -> (LLM Call) -> Generates potential task list.

AI -> aud planning add-task (repeatedly) -> Stores tasks in DB.

Task Execution Loop:

Get State: AI -> aud planning show --plan-id X --status pending --format json -> Gets next pending task_id (e.g., 5) and description from DB.

Gather Code Context (Mandatory Tool Usage):

AI -> MUST call aud query/blueprint/context --format json -> Gets necessary code understanding from DB. NO DIRECT FILE READING.

(If Refactoring Task): AI -> aud query ... -> Gathers facts -> Generates refactor_profile.yaml.

Perform Code Action: AI -> Modifies code files.

Update Code Index (CRITICAL): AI -> aud index --workset -> Updates repo_index.db.

Verify Task Deterministically: AI -> aud planning verify-task --task-id 5 --format json -> Runs DB checks against updated index.

AI receives JSON: {"task_id": 5, "verification_status": "passed", ...}.

Update Task Status: AI -> aud planning update-task --task-id 5 --status done.

AI repeats. If verification fails, AI parses details, gathers more context via aud tools, retries action.

Plan Completion: AI -> aud planning archive --plan-id X.

7. Data Structures (JSON Focus)

All communication relies on structured JSON from aud planning commands, reflecting the database state.

8. Information Requirements (Revised for AI Focus)

8.1. AI Agent Needs (Sourced exclusively from Database via Commands):

Plan Goal, Task List, Task State, Verification Feedback: JSON output of aud planning show.

Code Context: Structured JSON output from aud query, aud blueprint, aud context. Reliance on these tools is absolute.

Verification Result: Structured JSON output of aud planning verify-task.

State Updates via add-task/update-task commands.

8.2. Human Observer Needs (via AI displaying command output):

Observes the factual, structured JSON output provided by the AI from aud planning commands, reflecting the deterministic state managed by TheAuditor.

9. Implementation Considerations

Schema & DB Logic: Implement tables/indices (schema.py, database.py).

CLI Commands (planning.py): Implement robust JSON-first commands connected to DB logic.

Verification Logic (verify-task): Core component mapping plan_specs to deterministic CodeQueryEngine/RefactorRuleEngine calls against repo_index.db. Must handle all spec_type cases and structure output correctly.

Error Handling: Ensure commands and verification logic handle DB errors, invalid IDs gracefully.

AI Agent Prompts: External prompts must explicitly instruct the AI agent to use aud commands for all state and context information and follow the Act -> Index -> Verify loop.

10. Future Enhancements

(Same as Version 1.1: Dependency graphs, UI, more spec types, git integration)

11. Conclusion

Integrating planning state directly into TheAuditor's database elevates it to an AI agent enablement platform. This database-centric, deterministic approach provides unparalleled speed, reliability, and ground-truth verification essential for effective AI automation. It fully realizes TheAuditor's "truth courier" mission as a tool designed for AI agents.








------

# TheAuditor Planning Feature - Amendment 1: Handling Greenfield Development

**Version:** 1.0 (Amends Design Doc v1.2)
**Date:** 2025-10-28
**Author:** Gemini (based on requirements from TheAuditorA)

## A.1. Problem Statement: Planning for Non-Existent Code

The core `aud planning` design (v1.2) excels at managing tasks related to *existing* code by leveraging TheAuditor's deterministic database (`repo_index.db`). However, it doesn't explicitly address how to initiate, track, and eventually verify tasks for features or code structures that **do not yet exist**. Simply asking an LLM to generate a plan (like OpenSpec workflows) contradicts TheAuditor's "truth courier" and deterministic principles.

## A.2. Guiding Principles (Reiteration)

* **Database is the Source of Truth:** All plan and task state *must* reside in the database, not external files.
* **Deterministic Verification:** Task completion *must* eventually be verifiable against the indexed codebase state.
* **AI Agent Focus:** The system provides structured data and tools *for* an AI agent to use.
* **No Internal LLM Generation:** `aud planning` commands themselves do not generate creative content (specs, task descriptions, code). They manage state and execute deterministic queries.

## A.3. Proposed Solution: Structure, State, and Analogous Context

Instead of generating content for new features, `aud planning` will:

1.  **Provide the Database Structure:** Act as the structured container for the plan and tasks related to the new feature, even if the initial task descriptions are high-level or originate from an external source (human or LLM prompt).
2.  **Manage State:** Reliably track the status (`pending`, `in_progress`, `done`, `failed`) of these tasks within the database.
3.  **Facilitate Context Gathering via Analogues:** Require the AI agent to use existing `aud query` and `aud blueprint` commands to find **analogous patterns or similar features** within the *current* codebase. This provides *factual*, deterministic context to inform the AI's implementation of the *new* feature.
4.  **Enable Post-Implementation Verification:** Allow `aud planning verify-task` to function *after* the initial code for the new feature has been written by the AI agent and indexed via `aud index`.

## A.4. Workflow for Greenfield Features

1.  **Goal Assignment:** User gives the AI agent a goal for a *new* feature (e.g., "Implement a `/widgets` API endpoint with CRUD operations").
2.  **Plan Initialization:**
    * AI calls `aud planning init --goal "..."` -> Creates the plan record in the `plans` table.
3.  **Initial Task Definition (External Input -> DB Storage):**
    * The AI agent (potentially using an LLM based on the goal) or a human defines the high-level tasks required (e.g., "Define Widget model", "Create Widget controller", "Add GET /widgets route", "Implement POST /widgets handler").
    * AI calls `aud planning add-task` for each task -> Tasks are stored in `plan_tasks` with `status='pending'`, `verification_status='unverified'`.
4.  **Task Execution Loop (Leveraging Analogues):**
    * **Get State:** AI -> `aud planning show` -> Gets next pending task (e.g., "Add GET /widgets route").
    * **Gather Context via Analogues (Mandatory Tool Usage):**
        * AI -> **MUST** call `aud query`/`blueprint` to find *similar existing patterns*.
        * Example: `aud blueprint --security --format json` (to see how other routes handle auth), `aud query --api "/users" --format json` (to see structure of similar GET endpoints), `aud query --symbol create --type function --format json` (to find existing creation handlers).
        * **Crucially, the AI uses factual data about *existing* code to inform the design of the *new* code.**
    * **Perform Code Action:** AI -> Generates and writes the *new* code files (e.g., `widgets.controller.ts`, adds route to `server.ts`).
    * **Update Code Index (CRITICAL):** AI -> `aud index --workset` (or specific files) -> **Adds the *new* code structure to `repo_index.db`**.
    * **Verify Task (Now Possible):** AI -> `aud planning verify-task --task-id X`.
        * `verify-task` can now run checks against the *newly indexed code*.
        * Example `plan_spec`: `spec_type: symbol_exists`, `spec_target: WidgetsController.getAll`, `spec_params: {"file": "widgets.controller.ts"}`.
        * Example `plan_spec`: `spec_type: refactor_rule_expect` checking a rule that ensures API routes have validation middleware.
    * AI receives verification result (`passed`/`failed`).
    * **Update Task Status:** AI -> `aud planning update-task --task-id X --status done`.
    * AI repeats.
5.  **Plan Completion:** AI -> `aud planning archive`.

## A.5. Role of `aud planning verify-task` for New Code

* For tasks involving creation of new structures, `verify-task` relies on `plan_specs` that define **existence criteria** or adherence to **project conventions** (which could be encoded as refactor rules).
* **Initial State:** Tasks for creating new code start as `unverified`.
* **Verification:** `verify-task` runs *after* the AI writes the code and runs `aud index`. It then queries the *updated* database to check if the specified symbols, files, or patterns now exist and meet the criteria defined in the `plan_specs`.
    * `symbol_exists`: Checks `symbols` table.
    * `refactor_rule_expect`: Uses `RefactorRuleEngine` against the new code.
    * `finding_resolved`: Can check if initial "placeholder" findings (if any were created) are now gone.

## A.6. Refinements to Design Document v1.2

* **Section 3.2 (Integration):** Clarify that for new features, context gathering involves querying *analogous existing* patterns.
* **Section 5.1 (`init`):** Reinforce that it only creates the plan structure; task definition is separate.
* **Section 5.5 (`verify-task`):** Add detail on how verification works for *new* code via existence checks (`symbol_exists`) and convention checks (`refactor_rule_expect`) run *after* indexing.
* **Section 6 (Workflow):** Update steps to explicitly include querying for analogous patterns when implementing new code.

## A.7. Limitations & Tradeoffs

* **No Initial Content Generation:** `aud planning` itself does not create the initial task list or spec content for a brand-new feature. This must come from the user or an external LLM call managed by the AI agent. `aud planning` provides the *structure* and *verification*.
* **Relies on Analogues:** The quality of context for new features depends on the existence of comparable patterns in the existing codebase. For truly novel features in a new domain, the AI might need more external guidance.
* **Verification Requires Implementation:** `verify-task` only becomes fully effective *after* the code exists and is indexed. Initial task completion might rely on the AI marking status as 'done' before full verification is possible.

## A.8. Conclusion

This amendment clarifies how `aud planning` handles greenfield development by focusing on its strengths: providing a **structured database container** for externally defined tasks, **mandating the use of deterministic queries on existing code for context**, and enabling **post-implementation verification against the actual codebase state**. This approach avoids LLM generation within the core tool, maintains determinism, and effectively integrates new feature planning into TheAuditor's database-centric workflow.
```eof

This amendment addresses the greenfield scenario by outlining a workflow where the AI agent uses your existing tools (`query`/`blueprint`) to gather *factual context* from analogous parts of the codebase, informing its generation of the *new* code, which is then tracked and verified using the database-centric planning system. It keeps `aud planning` deterministic while providing the necessary structure and verification loop. Does this align with your thinking?




----

Amendment 2

Okay, here is an amendment document for `aud_planning.md` incorporating the task-based code checkpointing feature using `git diff` and the separate `planning.db`.

---

# TheAuditor Planning Feature - Amendment 2: Task-Based Code Checkpointing

**Version:** 1.0 (Amends Design Doc v1.2 & Amendment 1)
**Date:** 2025-10-29
**Author:** Gemini (incorporating feedback from TheAuditorA)

## A.2.1. Problem Statement: Lack of Granular, Task-Oriented Code History

While `aud planning` provides task tracking, it lacks a mechanism to capture the code state *associated with* specific tasks or edits made during a task's execution. Standard Git commits provide history, but often group multiple small changes or don't align directly with individual tasks in `aud planning`, making it difficult to revert just the changes related to a single failed or exploratory task without affecting unrelated edits. This is particularly relevant when AI agents make multiple incremental changes for a single task.

## A.2.2. Guiding Principles (Reiteration)

* **Database is the Source of Truth:** Planning state and associated history reside in a persistent database.
* **Leverage Existing Tools:** Utilize robust external tools like Git where appropriate, rather than reinventing core functionality.
* **Task-Oriented Context:** History should be directly linked to tasks defined in `aud planning`.
* **Complement Git:** This feature acts as a task-aware "local undo" or session history, complementing, **not replacing**, Git for permanent version control.

## A.2.3. Proposed Solution: Git-Diff-Based Checkpointing in `planning.db`

Introduce an optional checkpointing system integrated with `aud planning` that uses `git diff` to capture code changes related to specific tasks and stores them in a **separate, dedicated database (`planning.db`)**.

1.  **Separate Database (`planning.db`):**
    * **Rationale:** To prevent planning state and checkpoint history from being overwritten by `aud index` (which rebuilds `repo_index.db`) or archived by `aud full` (which moves `repo_index.db`).
    * **Implementation:** All tables related to `aud planning` (`plans`, `plan_tasks`, `plan_specs`, and the new checkpoint tables) will reside in `.pf/planning.db`. `aud planning` commands will operate exclusively on this database.

2.  **Checkpointing Workflow:**
    * **(Optional Trigger) Task Start:** When a task status is set to `in_progress` (via `aud planning update-task`), optionally snapshot the current state of relevant files (verbatim text) into a new `code_snapshots` table in `planning.db`, linked to the `task_id`. This serves as the baseline.
    * **(Optional Trigger) Post-Edit/Task Update:** After an agent makes an edit *or* when a task status is updated (e.g., to `done` or `failed`), the system can:
        * Run `git diff HEAD -- <filename>` (or `git diff --no-index <previous_snapshot> <current_file>`) for the modified file(s).
        * Store the raw textual output of `git diff` in a new `code_diffs` table in `planning.db`, linked to the `task_id` and a sequence number/timestamp.

3.  **Rewind Functionality:**
    * A new command, `aud planning rewind --task-id X [--to {base|edit_N|before_edit_N}]`, will allow reverting code changes associated with a task.
    * **Mechanism:**
        * Retrieve the baseline snapshot and relevant diffs from `planning.db`.
        * Option A (Restore Forward): Restore the baseline snapshot to the working directory, then sequentially apply the stored diffs up to the desired point using `git apply` or `patch`.
        * Option B (Reverse Apply): Attempt to apply diffs in reverse using `git apply --reverse` or `patch -R`. (More prone to conflicts).
        * The command should likely prompt the user or require a flag like `--force` to modify the working directory.
        * Recommend running `aud index` after rewinding to sync `repo_index.db`.

## A.2.4. New Database Schema (`planning.db`)

(Adds to existing `plans`, `plan_tasks`, `plan_specs` which are moved here from `repo_index.db`)

* **`code_snapshots` Table:**
    * `snapshot_id` (INTEGER, PK)
    * `task_id` (INTEGER, FK -> plan_tasks.task_id)
    * `file_path` (TEXT)
    * `content` (TEXT): Full file content at the time of snapshot.
    * `created_at` (TIMESTAMP)
    * `snapshot_type` (TEXT): e.g., 'task_start_base'.

* **`code_diffs` Table:**
    * `diff_id` (INTEGER, PK)
    * `task_id` (INTEGER, FK -> plan_tasks.task_id)
    * `sequence` (INTEGER): Order of diffs within a task.
    * `file_path` (TEXT): File the diff applies to.
    * `diff_content` (TEXT): Raw output from `git diff`.
    * `created_at` (TIMESTAMP)

## A.2.5. Refinements to Design Document v1.2

* **Section 3.1 (Database-Centric State):** Update to specify state resides in `.pf/planning.db`, separate from `repo_index.db`.
* **Section 4 (Database Schema):** Move existing tables to `planning.db` definition and add `code_snapshots` and `code_diffs` tables.
* **Section 5 (CLI Commands):** Add definition for `aud planning rewind`. Update `update-task` to potentially trigger snapshot/diff creation (perhaps via a `--checkpoint` flag).
* **Section 9 (Implementation Considerations):** Add points about managing the separate `planning.db` connection, handling potential `git diff`/`git apply` errors, and storage implications. Emphasize interaction with user's Git state (working directory, staging area).

## A.2.6. Benefits and Challenges

* **Benefits:** Provides task-specific, granular code history; allows rollback of individual task attempts without complex Git maneuvers; leverages robust `git diff` functionality.
* **Challenges:** Determining *what* to diff against (`HEAD` vs. previous snapshot); managing storage space for baselines and diffs; handling potential conflicts when applying diffs (`git apply`); ensuring clear interaction with the user's Git working directory and staging area.

## A.2.7. Conclusion

Adding optional, Git-diff-based checkpointing stored in a separate `planning.db` enhances `aud planning` by providing a task-oriented code history and rewind capability. This leverages existing Git functionality for diffing and patching while integrating tightly with the planning system's task structure, offering finer-grained control than standard Git commits alone. The separation into `planning.db` ensures persistence across code indexing operations.