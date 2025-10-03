You're right. We intentionally deferred a deep dive into the individual rules. That was a strategic decision to focus on the fire, not the furniture.

Our entire effort so far has been **Phase 1: Triage & Stabilization**. It was impossible to sanely investigate rule logic when:
1.  The `RulesOrchestrator` was running every rule on every file, creating an overwhelming amount of noise.
2.  The indexer's data pipeline was broken, feeding the rules incomplete or incorrect data.

Fixing a rule's logic is pointless if it's running on the wrong file or reading corrupted data. Now that the engine is fixed and the fuel lines are clean, we can finally fine-tune the engine's components—the rules themselves.

Welcome to **Phase 2: Rule Logic & Contract Audit**.

---
## The SOP: Auditing the Ruleset

We will now apply the same methodical, evidence-based approach to your entire ruleset. We already did this for the `/auth` and `/build` categories, which confirmed the validity of this process. For every new rule file you provide, we will perform the following three checks.

### ✅ **Check 1: Verify Rule Metadata**
This ensures the `RulesOrchestrator` runs the rule in the correct context.

* **Action**: Inspect the `METADATA` block at the top of the rule file.
* **Question**: "Does this rule correctly target the right files and architectural layers?"
    * Are `target_extensions` correct? (e.g., a Python rule should not target `.js`).
    * Are `exclude_patterns` filtering out irrelevant code like tests or frontend directories?
    * Is `requires_jsx_pass` set correctly for rules needing preserved JSX syntax?

### ✅ **Check 2: Verify Database Contracts**
This is the most critical step. It ensures the rule's queries are valid against the current, correct database schema.

* **Action**: For **every single SQL query** in the rule, cross-reference it with the `CREATE TABLE` statements in `database.py` and the `TableSchema` definitions in `schema.py`.
* **Questions**:
    * "Does the queried table exist?"
    * "Do all the columns in the `SELECT`, `WHERE`, and `ORDER BY` clauses exist?"
    * "Is the `WHERE` clause looking for **real data** (like `jwt.sign`) or **obsolete magic strings** (like `JWT_SIGN_HARDCODED`)?"

### ✅ **Check 3: Verify Finding Generation**
This ensures the rule produces findings in the standardized format, preventing runtime errors.

* **Action**: Inspect all `StandardFinding(...)` calls.
* **Question**: "Are the standardized parameter names from `base.py` being used correctly?"
    * Is it `file_path=` (not `file=`)?
    * Is it `rule_name=` (not `rule=`)?
    * Is it `severity=Severity.HIGH` (not `severity='HIGH'`)?

---
## What's Next

We have successfully audited the `/auth` and `/build` rule categories. Let's continue this methodical process.

To begin, please provide the rule files from the next category you'd like to audit. Based on common SAST tool structures, I would suggest `/rules/security`, `/rules/sql`, or another high-impact category. We will apply this 3-step SOP to them together.