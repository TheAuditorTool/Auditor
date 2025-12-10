"""Manual library 03 - YAML-configurable commands.

Commands that require user-written YAML configuration files.
Full schema documentation embedded for runtime access.
"""

EXPLANATIONS_03: dict[str, dict[str, str]] = {
    "refactor": {
        "title": "Refactoring Impact Analysis",
        "summary": "Detect incomplete refactorings from database schema migrations",
        "explanation": """
WHAT IT IS:
The refactor command detects code-schema mismatches from incomplete database
migrations. When you DROP a table but code still references it, that's a
runtime break waiting to happen. This command finds those mismatches by
parsing migrations and cross-referencing against the indexed codebase.

YAML CONFIGURATION REQUIRED:
To use --file mode, you MUST write a refactor profile YAML that defines:
- Legacy identifiers/patterns to find (old schema references)
- Expected new identifiers (new schema references)
- Scope rules (which files to check)

Without a YAML profile, aud refactor only scans migrations for DROP/ALTER.
With a profile, it tracks your specific refactoring progress.

WHEN TO USE IT:
- Before deploying migrations: Verify no code references dropped schema
- After writing migrations: Find code that needs updating
- During PR review: Check for incomplete refactorings
- Schema cleanup: Find code referencing deprecated tables/columns
- CI/CD gates: Block deployments with schema-code mismatches

HOW TO USE IT:
PREREQUISITES:
    aud full                              # Build database first

STEPS:
    1. Run refactor analysis:
       aud refactor                       # Analyze last 5 migrations

    2. Review findings by severity:
       - CRITICAL: Code references deleted table (will break)
       - HIGH: Code references deleted column (will break)
       - MEDIUM: Code may reference renamed element (verify)

    3. For each finding, update the code:
       aud explain <file>                 # Get context

    4. Re-run to verify:
       aud refactor                       # Should show 0 findings

EXAMPLE - Pre-Deployment Check:
    aud full && aud refactor
    # Shows: api/users.py:42 references dropped column 'email'
    # Action: Update query before deploying migration

YAML PROFILE SCHEMA:
To track custom refactoring beyond migrations, create a YAML profile:

    refactor_name: "frontend_variants_v2"
    description: "Ensure POS + dashboard flows use product_variant_id"
    version: "2025-10-26"

    metadata:
      owner: "plantflow_frontend"
      jira_epic: "PF-276"
      docs: "https://wiki.company.com/variants"

    rules:
      - id: "order-pos-cart"
        description: "Cart/order/receipt flows must store product_variant_id"
        severity: "critical"
        category: "pos-flow"
        match:
          identifiers:
            - "cartItem.product_id"
            - "orderItem.product_id"
          expressions:
            - "product.unit_price"
        expect:
          identifiers:
            - "product_variant_id"
            - "posSelection.variant"
          expressions:
            - "variant.retail_price"
        scope:
          include:
            - "frontend/src/pages/pos/**"
            - "frontend/src/pages/dashboard/CreateOrder.tsx"
          exclude:
            - "tests/"
        guidance: >
          Optional human note for future readers.

YAML FIELD REFERENCE:
    refactor_name    REQUIRED  Unique slug for the profile
    description      REQUIRED  Short summary
    version          optional  Date/semver to track revisions
    metadata         optional  Owner, tickets, docs, rollout stage
    rules[]          REQUIRED  Each rule defines match and optional expect patterns
    rules[].id       REQUIRED  Unique rule identifier
    rules[].severity optional  critical/high/medium/low (sorting priority)
    rules[].category optional  Tag for grouping
    rules[].match    REQUIRED  Legacy identifiers/expressions/API routes to find
    rules[].expect   optional  New identifiers/expressions to confirm coverage
    rules[].scope    optional  include/exclude path patterns
    rules[].guidance optional  Informational comment

PATTERN SYNTAX:
Literal patterns (default) - word-boundary matching:
    match:
      identifiers:
        - "product_id"       # Matches "product_id" not "old_product_id"
        - "cartItem.id"      # Matches exact "cartItem.id"

Regex patterns - wrap in forward slashes:
    match:
      identifiers:
        - "/.*\\.product\\.id/"    # Matches x.product.id
        - "/\\.product_id$/"       # Matches any .product_id suffix

EXAMPLE RULES:
Transfers rule:
    - id: "transfers-variant-ids"
      description: "Transfers + QR flows must use product_variant_id"
      severity: "high"
      match:
        identifiers:
          - "transferItem.product_id"
          - "product_variant.product.name"
        expressions:
          - "qrPayload.product_id"
      expect:
        identifiers:
          - "transferItem.product_variant_id"
        expressions:
          - "qrPayload.product_variant_id"
      scope:
        include:
          - "frontend/src/pages/dashboard/Transfers.tsx"
          - "frontend/src/components/QRScanner.tsx"

Regex pattern rule:
    - id: "order-pos-cart"
      severity: "critical"
      match:
        identifiers:
          - "/.*\\.product\\.id/"      # Catches item.product.id, cart.product.id
          - "/\\.product_id/"          # Catches any .product_id property
      expect:
        identifiers:
          - "product_variant_id"
      scope:
        include:
          - "frontend/src/pages/pos/**"

RUNNING WITH PROFILE:
    aud refactor --file profile.yaml --migration-limit 0

OUTPUT SECTIONS:
- Profile summary: totals, rule coverage, missing expectations
- Rule breakdown: per-rule counts, top files
- File priority queue: severity-sorted list of files with violations
- Schema mismatch summary: default migration analysis

COMBINING WITH OTHER TOOLS:
- Before refactor: Run aud full to index code references
- With context: Define migration rules to track progress
- With deadcode: After migration, find orphaned code
- With impact: See full blast radius of schema changes
- In CI/CD: Block merge if refactor finds CRITICAL issues

WHAT IT DETECTS:
Schema Changes (from migrations):
- Dropped tables: DROP TABLE, dropTable()
- Dropped columns: ALTER TABLE DROP COLUMN, removeColumn()
- Renamed tables: RENAME TO, renameTable()
- Renamed columns: renameColumn()

Code References (from database):
- SQL queries mentioning deleted tables/columns
- ORM model references (SQLAlchemy, Django, TypeORM)
- Raw SQL in string literals
- Dynamic query builders

COMMAND OPTIONS:
    aud refactor                          # Last 5 migrations
    aud refactor --migration-limit 0      # ALL migrations
    aud refactor --migration-dir ./db     # Custom directory
    aud refactor --output report.json     # Export findings
    aud refactor --file profile.yaml      # Use refactor profile (YAML required)
    aud refactor --in-file OrderDetails   # Focus on pattern
    aud refactor --query-last             # Show results from last run (NO re-analysis)
    aud refactor --validate-only          # Validate YAML without running (use with --file)

AI WORKFLOW (for custom YAML profiles):
The correct workflow for AI assistants:

    1. INVESTIGATE: Query database to understand what patterns exist
       aud query --pattern "%product%" --path "frontend/src/**"

    2. WRITE YAML: Create profile based on actual patterns found
       (See YAML PROFILE SCHEMA above)

    3. VALIDATE: Check YAML syntax before running
       aud refactor --file profile.yml --validate-only

    4. RUN: Execute the refactor analysis
       aud refactor --file profile.yml

    5. QUERY RESULTS: Get violations from database (NOT file output)
       aud refactor --query-last

    WRONG APPROACH (wastes time):
      - Guessing patterns without discovery
      - Using --output file.json then reading the JSON file
      - Running full analysis to test one rule

    RIGHT APPROACH:
      - Query DB first to discover actual patterns
      - Use --validate-only before full run
      - Use --query-last to read results from DB (stored in refactor_history table)

TROUBLESHOOTING:
- Too few matches: Add more identifiers, widen scope, use regex patterns
- Too many matches: Tighten scope, use more precise substrings
- Missing variable names: Use regex /.*\\.product\\.id/
- Expectation never fulfilled: Check spelling, verify new identifiers exist
- Need JSON for automation: Use --output report.json

RELATED:
Commands: aud refactor, aud impact, aud query, aud deadcode
Topics: aud manual impact, aud manual deadcode, aud manual context

EXIT CODES:
- 0: No schema-code mismatches found
- 1: Findings detected (review required)
- 2: Error (database missing or migration parsing failed)
""",
    },
    "context": {
        "title": "Semantic Context Classification",
        "summary": "Apply business logic rules to classify findings during migrations and refactoring",
        "explanation": """
WHAT IT IS:
Semantic context classification interprets analysis findings based on your
project's business state. During migrations, old patterns exist alongside new
ones by design - context rules let you classify what's obsolete (must fix),
current (correct pattern), or transitional (acceptable during migration).

YAML CONFIGURATION REQUIRED:
You MUST write a semantic context YAML file that defines:
- Obsolete patterns (findings to de-prioritize or flag for removal)
- Current patterns (findings that still matter)
- Transitional patterns (dual-stack code allowed until a date)

Without a YAML file, aud context has nothing to classify.

WHEN TO USE IT:
- During migrations: OAuth replaces JWT, old patterns flagged but intentional
- API deprecation: v1 endpoints still exist during transition period
- Framework upgrades: Old patterns exist until migration complete
- Database refactoring: Old table references acceptable during migration
- Any time you need to distinguish "intentional tech debt" from "bugs"

HOW TO USE IT:
PREREQUISITES:
    aud full                              # Run analysis first (populates findings)

STEPS:
    1. Write a semantic context YAML (schema below)
    2. Run: aud context --file <path>
    3. Review classified findings
    4. Fix OBSOLETE immediately, TRANSITIONAL acceptable during window

YAML SCHEMA:
    context_name: "oauth_migration_security"
    description: "Classifies JWT findings vs OAuth2 adoption state"
    version: "2025-10-26"

    patterns:
      obsolete:
        - id: "jwt_issue_calls"
          pattern: "(jwt\\.sign|AuthService\\.issueJwt)"
          reason: "Legacy JWT signing scheduled for removal"
          replacement: "AuthService.issueOAuthToken"
          severity: "medium"
          scope:
            include: ["backend/src/auth/"]
            exclude: ["tests/"]

      current:
        - id: "oauth_exchange"
          pattern: "oauth2Client\\."
          reason: "OAuth2/OIDC code must stay high-priority"
          scope:
            include: ["backend/src/auth/", "frontend/src/auth/"]

      transitional:
        - id: "jwt_oauth_bridge"
          pattern: "bridgeJwtToOAuth"
          reason: "Bridge layer allowed until Phase 3 completes"
          expires: "2025-12-31"
          scope:
            include: ["backend/src/auth/bridges/"]

    relationships:
      - type: "replaces"
        from: "jwt_issue_calls"
        to: "oauth_exchange"

    metadata:
      author: "security_team"
      jira_ticket: "SEC-2045"
      docs: "https://wiki.company.com/security/oauth-migration"

YAML FIELD REFERENCE:
    context_name              REQUIRED  Unique identifier (snake_case)
    description               REQUIRED  Short explanation
    version                   optional  Date or semver
    patterns.obsolete[]       optional  Patterns flagged as obsolete
    patterns.current[]        optional  Correct patterns (high-priority)
    patterns.transitional[]   optional  Allowed temporarily
    scope.include/exclude     optional  Path substring lists
    relationships[]           optional  Connect related pattern IDs
    metadata                  optional  Owner, tickets, tags, docs

PATTERN FIELDS:
    id           REQUIRED  Unique pattern identifier
    pattern      REQUIRED  Regex matched against finding rule, message, code_snippet
    reason       REQUIRED  Why this classification
    replacement  optional  What to use instead (obsolete only)
    severity     optional  critical/high/medium/low (obsolete only)
    expires      REQUIRED  Expiration date (transitional only)
    scope        optional  include/exclude path filters

CLASSIFICATION STATES:
- OBSOLETE: Must fix immediately - deprecated patterns
- CURRENT: Correct pattern - the target state
- TRANSITIONAL: Acceptable temporarily - during migration window

SEVERITY GUIDANCE (obsolete patterns):
    critical   Absolutely remove ASAP (e.g., leaking secrets)
    high       Blocker for launch or compliance
    medium     Should be cleaned up soon but not blocking
    low        Cosmetic or documentation-only

EXAMPLE - OAuth Migration:
    aud full
    aud context --file oauth_migration.yaml --verbose
    # Output: 15 files using JWT (obsolete), 8 using legacy API keys (transitional)
    # Action: Prioritize the 15 JWT files for immediate migration

SCOPE TIPS:
- Use broad directories (frontend/, backend/src/auth/) not specific files
- Exclude tests/, fixtures/, migrations/ to avoid false positives
- No globbing - TheAuditor does substring checks

WORKFLOW:
    1. Plan: Decide what counts as obsolete/current/transitional
    2. Author YAML: Copy template above, customize patterns
    3. Validate: Run aud context --file ... --verbose, adjust until correct
    4. Share: Check in YAML to repo
    5. Iterate: Update version, expires as migrations progress

COMBINING WITH OTHER TOOLS:
- Before context: Run aud full to generate findings to classify
- With refactor: Use context to track migration progress
- With deadcode: After migration, use deadcode to find orphaned code
- In CI/CD: Fail on obsolete count > 0, warn on transitional

COMMAND OPTIONS:
    aud context --file rules.yaml            # Classify findings
    aud context --file rules.yaml --verbose  # Show all matches
    aud context --file rules.yaml -o out.json # Custom output

TROUBLESHOOTING:
- No patterns matched: Check aud detect-patterns ran, verify scope, test regex
- Too many matches: Narrow scope or refine regex
- Transitional never expires: Update expires field, re-run after date
- Need JSON for AI agents: Use --json flag for stdout output

RELATIONSHIP TO REFACTOR PROFILES:
- Semantic context (this): Input to aud context --file, classifies existing findings
- Refactor YAML profiles: Input to aud refactor --file, scan migrations + code

Different pipelines, different schemas - use whichever matches your problem.

RELATED:
Commands: aud context, aud full, aud refactor, aud deadcode
Topics: aud manual refactor, aud manual deadcode

OUTPUT:
- Classified findings stored in database (query with aud query --findings)
- Summary counts: obsolete_count, current_count, transitional_count
- Use --json for machine-readable stdout output
""",
    },
}
