Phase: 0 (Pre-Implementation Verification & Planning)Objective: Assess current Terraform implementation issues and
   produce actionable remediation planStatus: VERIFICATION COMPLETE - AWAITING ARCHITECT APPROVAL

  ---
  1. Verification Phase Report (Pre-Implementation)

  Hypotheses & Verification:

  Hypothesis 1: Terraform implementation is complete and functional.
  - Verification: ❌ INCORRECT. Critical defects found:
    - .tfvars files explicitly skipped at theauditor/indexer/extractors/terraform.py:73-76
    - No rules/terraform/ directory exists
    - Security checks hardcoded in theauditor/terraform/analyzer.py instead of following rules architecture
    - Empty __init__.py at theauditor/terraform/__init__.py (1 line only)

  Hypothesis 2: Terraform rules follow standard architecture pattern.
  - Verification: ❌ INCORRECT. Security checks are hardcoded directly in TerraformAnalyzer class instead of being
  discoverable by the orchestrator through the /rules/terraform/ directory structure.

  Hypothesis 3: .tfvars secret scanning requires new database table.
  - Verification: ✅ PARTIALLY CORRECT. Schema at schema.py:1176 has source_file column in terraform_variables table
   but user requests new terraform_variable_values table for dedicated .tfvars value storage.

  Hypothesis 4: Rules use find_* naming convention.
  - Verification: ❌ INCORRECT. All rules use analyze() as entry point (verified via grep of 43 rule files).
  Orchestrator at orchestrator.py:142 searches for find_* but production rules universally use analyze().

  Hypothesis 5: Architecture separation exists between parsing (parser.py) and security analysis (analyzer.py).
  - Verification: ✅ CORRECT. Clear separation exists:
    - parser.py: Structural HCL parsing (python-hcl2)
    - analyzer.py: Security checks (should be in /rules/terraform/)
    - graph.py: Provisioning flow graph building

  Discrepancies Found:

  1. Critical Architecture Violation: Security rules hardcoded in theauditor/terraform/analyzer.py:93-385 instead of
   being in discoverable /rules/terraform/terraform_analyze.py following standard pattern seen in
  rules/deployment/docker_analyze.py and rules/deployment/nginx_analyze.py.
  2. Incomplete Feature: .tfvars parsing explicitly disabled despite extractor declaring support at terraform.py:48
  (return ['.tf', '.tfvars', '.tf.json']).
  3. Empty Module Init: theauditor/terraform/__init__.py is functionally empty (1 line), lacking proper module
  exports.
  4. Table Schema Gap: User requests terraform_variable_values table but schema only has source_file column in
  existing terraform_variables table.

  ---
  2. Deep Root Cause Analysis

  Surface Symptom:

  "Terraform implementation defers critical .tfvars secret scanning and hardcodes security rules in parser instead
  of using /rules/terraform/ architecture."

  Problem Chain Analysis:

  1. Initial Implementation Decision: Terraform support added as monolithic analyzer class in /theauditor/terraform/
   directory (separate from rules architecture).
  2. Architecture Bypass: Security checks implemented directly in TerraformAnalyzer._check_*() methods instead of
  creating /rules/terraform/terraform_analyze.py following the pattern established in:
    - rules/deployment/docker_analyze.py (uses find_docker_issues())
    - rules/deployment/nginx_analyze.py (uses analyze())
    - rules/deployment/compose_analyze.py
  3. Incomplete Extraction: Extractor at terraform.py:73-76 explicitly skips .tfvars files with TODO comment,
  preventing secret scanning in variable value files.
  4. Orchestrator Bypass: Direct analyzer invocation via aud terraform analyze command bypasses standard rule
  discovery system at orchestrator.py:110-150.

  Actual Root Cause:

  Terraform implementation treated as standalone subsystem rather than integrated rule set, violating TheAuditor's
  core architectural principle: "All security checks MUST be discoverable by orchestrator via /rules/{category}/
  structure."

  Why This Happened (Historical Context):

  Design Decision: Implemented Terraform as separate subsystem with dedicated CLI commands (aud terraform provision,
   aud terraform analyze) similar to graph commands rather than as integrated security rules.

  Missing Safeguard: No architectural review enforcing rule discovery pattern. Orchestrator allows direct analyzer
  invocation, creating two code paths:
  - Path 1: Orchestrator-discovered rules (/rules/)
  - Path 2: Direct command invocation (aud terraform analyze → TerraformAnalyzer)

  Consequence: Terraform findings isolated from FCE (Focused Context Extraction) correlation unless explicitly
  dual-written to findings_consolidated table (which analyzer.py:415-467 does correctly, but outside orchestrator
  control).

  ---
  3. Implementation Plan & Decision Log

  Files Requiring Modification:

  1. theauditor/indexer/schema.py - Add terraform_variable_values table
  2. theauditor/indexer/extractors/terraform.py - Remove .tfvars skip, add .tfvars parsing
  3. theauditor/terraform/__init__.py - Add module exports
  4. theauditor/rules/terraform/terraform_analyze.py (NEW) - Move hardcoded checks from analyzer
  5. theauditor/rules/terraform/__init__.py (NEW) - Create rules module
  6. theauditor/terraform/analyzer.py (MODIFY or DEPRECATE) - Refactor or mark for removal

  Decision Log:

  Decision 1: Create terraform_variable_values table separate from terraform_variables.

  Reasoning: User explicitly requested this table. Separation follows data modeling principle: declarations
  (terraform_variables) vs assignments (terraform_variable_values). Analogous to symbols (declarations) vs
  assignments (values) in Python/JS extraction.

  Alternative Considered: Store values in existing terraform_variables.default_json column.

  Rejected Because: .tfvars files override defaults and may provide multiple values across different environment
  files (dev.tfvars, prod.tfvars). Separate table enables querying "which .tfvars files set this variable" without
  JSON parsing.

  ---
  Decision 2: Move security checks from TerraformAnalyzer to /rules/terraform/terraform_analyze.py.

  Reasoning:
  - Follows established architecture pattern (docker_analyze.py, nginx_analyze.py)
  - Enables orchestrator discovery
  - Allows per-check metadata (severity, CWE, confidence)
  - Integrates with FCE automatically via orchestrator

  Alternative Considered: Keep TerraformAnalyzer as-is, add wrapper rule.

  Rejected Because: Violates DRY principle and maintains two code paths for same functionality.

  ---
  Decision 3: Use analyze() function signature, NOT find_*.

  Reasoning: All 43 production rules use analyze() as entry point. Orchestrator.py:142 searches for find_* but this
  appears to be dead code or migration artifact.

  Evidence:
  - grep 'def analyze(' rules/ → 43 files
  - grep 'def find_' rules/ → Only templates and deprecated code

  Implementation: Follow TEMPLATE_STANDARD_RULE.py pattern exactly.

  ---
  Decision 4: Maintain backward compatibility with aud terraform analyze command.

  Reasoning: User may have CI/CD pipelines using direct command. Refactor analyzer to delegate to rule, preserving
  CLI interface.

  Implementation Pattern:
  # theauditor/terraform/analyzer.py (REFACTORED)
  def analyze(self) -> List[TerraformFinding]:
      """Run all security checks via rules orchestrator (backward compat wrapper)."""
      from theauditor.rules.terraform.terraform_analyze import analyze as run_terraform_rules
      from theauditor.rules.base import StandardRuleContext

      context = StandardRuleContext(db_path=str(self.db_path))
      findings = run_terraform_rules(context)

      # Convert StandardFinding → TerraformFinding for backward compat
      return self._convert_findings(findings)

  ---
  4. Pre-Implementation Task Breakdown

  Phase 1: Schema Extension (CRITICAL PATH)

  Task 1.1: Add terraform_variable_values table to schema.py

  Schema Design:
  Table(
      "terraform_variable_values",
      [
          Column("id", "INTEGER", primary_key=True, autoincrement=True),
          Column("file_path", "TEXT", nullable=False),  # .tfvars file path
          Column("variable_name", "TEXT", nullable=False),
          Column("variable_value_json", "TEXT"),  # JSON-serialized value
          Column("line", "INTEGER"),
          Column("is_sensitive_context", "BOOLEAN", default="0"),  # Contains sensitive keywords
      ],
      indexes=[
          Index("idx_tfvars_file", ["file_path"]),
          Index("idx_tfvars_var", ["variable_name"]),
      ]
  )

  Location: Insert after terraform_variables table definition (schema.py:~1180)

  Validation: Run aud index on test Terraform project, verify table created.

  ---
  Phase 2: .tfvars Parsing (EXTRACTOR MODIFICATION)

  Task 2.1: Remove .tfvars skip logic at terraform.py:73-76

  Before:
  # Skip .tfvars files for now (TODO: parse for variable values)
  if file_path.endswith('.tfvars'):
      logger.debug(f"Skipping .tfvars file (not yet supported): {file_path}")
      return {}

  After:
  # Detect file type
  is_tfvars = file_path.endswith('.tfvars')

  if is_tfvars:
      # Parse .tfvars using python-hcl2 (same parser, different table)
      return self._extract_tfvars(file_path, content)
  else:
      # Parse .tf files (existing logic)
      ...

  Task 2.2: Implement _extract_tfvars() method

  Implementation:
  def _extract_tfvars(self, file_path: str, content: str) -> Dict[str, Any]:
      """Extract variable assignments from .tfvars file.

      Args:
          file_path: Path to .tfvars file
          content: File content

      Returns:
          Dict with 'terraform_variable_values' key containing list of values
      """
      try:
          with open(file_path, 'r', encoding='utf-8') as f:
              parsed = hcl2.load(f)
      except Exception as e:
          logger.error(f"Failed to parse .tfvars file {file_path}: {e}")
          return {}

      variable_values = []

      for key, value in parsed.items():
          # Check if value contains sensitive keywords
          is_sensitive = self._is_sensitive_value(key, value)

          variable_values.append({
              'file_path': file_path,
              'variable_name': key,
              'variable_value_json': json.dumps(value),
              'line': None,  # TODO: Extract line numbers from tree-sitter if available
              'is_sensitive_context': is_sensitive,
          })

      return {'terraform_variable_values': variable_values}

  def _is_sensitive_value(self, key: str, value: Any) -> bool:
      """Check if variable name or value suggests sensitive data."""
      sensitive_keywords = ['password', 'secret', 'key', 'token', 'credential', 'private']
      key_lower = key.lower()
      return any(kw in key_lower for kw in sensitive_keywords)

  Task 2.3: Update indexer to handle terraform_variable_values

  Location: theauditor/indexer/database.py (add method add_terraform_variable_value())

  Validation:
  # Create test .tfvars file
  echo 'db_password = "admin123"' > test.tfvars
  echo 'api_key = "sk-test123456"' >> test.tfvars

  # Run indexer
  aud index

  # Verify table populated
  .venv/Scripts/python.exe -c "
  import sqlite3
  conn = sqlite3.connect('.pf/repo_index.db')
  c = conn.cursor()
  c.execute('SELECT * FROM terraform_variable_values')
  for row in c.fetchall():
      print(row)
  conn.close()
  "

  ---
  Phase 3: Rules Architecture Migration (CRITICAL)

  Task 3.1: Create /rules/terraform/ directory structure

  mkdir theauditor/rules/terraform
  touch theauditor/rules/terraform/__init__.py
  touch theauditor/rules/terraform/terraform_analyze.py

  Task 3.2: Implement terraform_analyze.py following TEMPLATE_STANDARD_RULE.py

  File Structure:
  """Terraform IaC Security Analyzer - Database-First Approach.

  Detects infrastructure security issues including:
  - Public exposure (S3 buckets, databases, security groups)
  - IAM wildcards (overly permissive policies)
  - Hardcoded secrets in resources AND .tfvars files
  - Missing encryption
  - Unencrypted network traffic

  Tables Used:
  - terraform_resources
  - terraform_variables
  - terraform_variable_values  (NEW - for .tfvars secret scanning)
  - terraform_outputs
  """

  import sqlite3
  import json
  from typing import List
  from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata

  METADATA = RuleMetadata(
      name="terraform_security",
      category="deployment",
      target_extensions=[],  # Database-first rule
      exclude_patterns=['test/', '__tests__/', 'node_modules/', '.pf/'],
      requires_jsx_pass=False,
      execution_scope='database',
  )

  def analyze(context: StandardRuleContext) -> List[StandardFinding]:
      """Detect Terraform infrastructure security issues."""
      findings = []

      if not context.db_path:
          return findings

      conn = sqlite3.connect(context.db_path)
      cursor = conn.cursor()

      try:
          # MIGRATE FROM TerraformAnalyzer:
          findings.extend(_check_public_s3_buckets(cursor))
          findings.extend(_check_unencrypted_storage(cursor))
          findings.extend(_check_iam_wildcards(cursor))
          findings.extend(_check_hardcoded_secrets(cursor))  # Resources
          findings.extend(_check_tfvars_secrets(cursor))      # NEW - .tfvars files
          findings.extend(_check_missing_encryption(cursor))
          findings.extend(_check_security_groups(cursor))
      finally:
          conn.close()

      return findings

  # Copy methods from TerraformAnalyzer, converting TerraformFinding → StandardFinding
  def _check_public_s3_buckets(cursor) -> List[StandardFinding]:
      # COPY from analyzer.py:93-142, change to StandardFinding format
      ...

  def _check_tfvars_secrets(cursor) -> List[StandardFinding]:
      """NEW: Scan .tfvars files for hardcoded secrets."""
      findings = []

      cursor.execute("""
          SELECT file_path, variable_name, variable_value_json, line
          FROM terraform_variable_values
          WHERE is_sensitive_context = 1
      """)

      for row in cursor.fetchall():
          file_path, var_name, value_json, line = row

          # High-entropy check (user's requirement)
          value = json.loads(value_json)
          if isinstance(value, str) and _is_high_entropy(value):
              findings.append(StandardFinding(
                  file_path=file_path,
                  line=line or 1,
                  rule_name='terraform-tfvars-secret',
                  message=f'Hardcoded secret detected in .tfvars file: {var_name}',
                  severity=Severity.CRITICAL,
                  category='hardcoded_secret',
                  snippet=f'{var_name} = [REDACTED]',
                  cwe_id='CWE-798'
              ))

      return findings

  def _is_high_entropy(value: str, threshold: float = 4.0) -> bool:
      """Check Shannon entropy for secret detection."""
      # COPY from docker_analyze.py:393-426
      ...

  Task 3.3: Populate theauditor/terraform/__init__.py

  """Terraform infrastructure analysis subsystem.

  Provides HCL parsing, graph building, and security analysis for
  Terraform Infrastructure as Code.

  Modules:
      parser: Structural HCL parsing via python-hcl2
      analyzer: Security analysis wrapper (delegates to /rules/terraform/)
      graph: Provisioning flow graph construction
  """

  from .parser import TerraformParser
  from .analyzer import TerraformAnalyzer, TerraformFinding
  from .graph import TerraformGraphBuilder

  __all__ = [
      'TerraformParser',
      'TerraformAnalyzer',
      'TerraformFinding',
      'TerraformGraphBuilder',
  ]

  Task 3.4: Refactor TerraformAnalyzer to delegate to rule

  Location: theauditor/terraform/analyzer.py:68-91

  Before (lines 68-91):
  def analyze(self) -> List[TerraformFinding]:
      findings = []
      findings.extend(self._check_public_s3_buckets())
      findings.extend(self._check_unencrypted_storage())
      # ... 6 more checks hardcoded here
      filtered = self._filter_by_severity(findings)
      self._write_findings(filtered)
      return filtered

  After:
  def analyze(self) -> List[TerraformFinding]:
      """Run security checks via orchestrated rule (backward compat wrapper).

      DEPRECATED: Direct use of TerraformAnalyzer is deprecated.
      Use 'aud detect-patterns --category=deployment' instead.
      This method maintained for backward compatibility with existing
      'aud terraform analyze' CLI command.
      """
      from theauditor.rules.terraform.terraform_analyze import analyze as run_rules
      from theauditor.rules.base import StandardRuleContext

      # Invoke orchestrated rule
      context = StandardRuleContext(db_path=str(self.db_path))
      standard_findings = run_rules(context)

      # Convert StandardFinding → TerraformFinding for CLI backward compat
      terraform_findings = self._convert_findings(standard_findings)

      # Filter and write (preserving existing behavior)
      filtered = self._filter_by_severity(terraform_findings)
      self._write_findings(filtered)

      return filtered

  def _convert_findings(self, standard_findings: List) -> List[TerraformFinding]:
      """Convert StandardFinding to TerraformFinding format."""
      from theauditor.rules.base import StandardFinding

      terraform_findings = []
      for sf in standard_findings:
          # Map StandardFinding fields → TerraformFinding fields
          tf = TerraformFinding(
              finding_id=sf.rule_name,
              file_path=sf.file_path,
              resource_id=sf.snippet,  # Best effort mapping
              category=sf.category,
              severity=sf.severity.name.lower(),  # Severity.CRITICAL → 'critical'
              title=sf.message,
              description=sf.message,
              line=sf.line,
              remediation=getattr(sf, 'remediation', ''),
          )
          terraform_findings.append(tf)

      return terraform_findings

  Deprecation Notice: Add to analyzer.py docstring:
  """Terraform security analyzer.

  ⚠️ DEPRECATED: This module is maintained for backward compatibility only.
  New code should use the orchestrated rule at:
      theauditor/rules/terraform/terraform_analyze.py

  The 'aud terraform analyze' command delegates to the orchestrated rule
  internally. Direct instantiation of TerraformAnalyzer is discouraged.

  Preferred Usage:
      aud detect-patterns --category=deployment  # Runs all deployment rules
      aud detect-patterns --rules terraform_security  # Terraform only

  Legacy Usage (still supported):
      aud terraform analyze  # Delegates to orchestrated rule
  """

  ---
  Phase 4: Validation & Testing

  Task 4.1: Create test Terraform project

  # test_terraform/main.tf
  resource "aws_s3_bucket" "public_bucket" {
    acl = "public-read"
  }

  resource "aws_db_instance" "unencrypted_db" {
    storage_encrypted = false
  }

  # test_terraform/secrets.tfvars
  db_password = "admin123"  # Weak password
  api_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz123456"  # High entropy

  Task 4.2: Run full pipeline

  cd test_terraform
  aud index
  aud terraform analyze

  Expected Output:
  Terraform Security Analysis Complete:
    Total findings: 4
    Critical: 2  # .tfvars secrets
    High: 2      # Public S3, unencrypted DB

  Findings by category:
    hardcoded_secret: 2
    public_exposure: 1
    missing_encryption: 1

  Task 4.3: Verify orchestrator integration

  # Should discover terraform rule automatically
  aud detect-patterns --category=deployment

  # Should include terraform findings in output

  Task 4.4: Verify FCE correlation

  # Query findings_consolidated table
  .venv/Scripts/python.exe -c "
  import sqlite3
  conn = sqlite3.connect('.pf/repo_index.db')
  c = conn.cursor()
  c.execute('''
    SELECT tool, COUNT(*)
    FROM findings_consolidated
    WHERE tool = 'terraform'
    GROUP BY tool
  ''')
  print('Terraform findings in FCE:', c.fetchone())
  conn.close()
  "

  Expected: Terraform findings present in findings_consolidated table for cross-tool correlation.

  ---
  5. Edge Case & Failure Mode Analysis

  Edge Cases Considered:

  1. Empty .tfvars files: Return empty terraform_variable_values list (no findings).
  2. Malformed HCL in .tfvars: Hard fail with error log (no fallback parsing per ABSOLUTE PROHIBITION).
  3. Multiple .tfvars files with same variable: Each assignment stored separately with file_path discriminator.
  4. Secret detection false positives: Use high-entropy threshold (4.0 bits/char) and sensitive keyword whitelist to
   reduce noise.
  5. Tree-sitter vs python-hcl2 parsing: Prefer tree-sitter for line numbers (terraform.py:80-89), fallback to
  python-hcl2 only if tree unavailable.

  Performance & Scale Analysis:

  Performance Impact:
  - .tfvars parsing: Negligible (<10ms per file, HCL2 parser is fast)
  - Secret scanning: O(n) where n = number of .tfvars variables
  - Database writes: Batched via indexer (no per-row commits)

  Scalability:
  - Time complexity: O(F × V) where F = .tfvars files, V = variables per file
  - Typical project: 10 .tfvars files × 20 vars = 200 rows (sub-millisecond query)
  - Large monorepo: 100 files × 50 vars = 5000 rows (still <50ms full scan)

  Bottleneck: High-entropy calculation runs regex on every string value. Mitigate by:
  1. Skip strings <10 chars (not enough entropy)
  2. Skip if whitespace present (likely prose)
  3. Cache entropy calculations per unique value

  ---
  6. Impact, Reversion, & Testing

  Impact Assessment:

  Immediate:
  - 1 new table: terraform_variable_values
  - 1 new file: rules/terraform/terraform_analyze.py
  - 1 new directory: rules/terraform/
  - 2 modified files: terraform.py (extractor), schema.py
  - 1 refactored file: analyzer.py (backward compat wrapper)

  Downstream:
  - .tfvars files now indexed (previously skipped)
  - Terraform findings discoverable via orchestrator
  - aud detect-patterns --category=deployment includes Terraform
  - FCE automatically correlates Terraform findings with other tools

  Reversion Plan:

  Reversibility: Fully Reversible

  Steps:
  1. Drop table: DROP TABLE terraform_variable_values;
  2. Restore .tfvars skip: git checkout terraform.py
  3. Remove rules directory: rm -rf rules/terraform/
  4. Restore analyzer: git checkout analyzer.py

  Data Loss: .tfvars variable values (regenerated on next aud index)

  Migration Path: None required (tables created fresh on index)

  ---
  7. Confirmation of Understanding (Architect Review Required)

  I confirm that I have followed teamsop.md Prime Directive protocols (Phase 0: Verification Before Implementation).

  Verification Finding:
  - Current implementation hardcodes Terraform security checks in TerraformAnalyzer class
  - .tfvars files explicitly skipped despite being declared in extractor
  - Rules architecture pattern violated (checks not in /rules/terraform/)

  Root Cause:
  Terraform implemented as standalone subsystem rather than integrated rule set, bypassing orchestrator discovery
  and FCE auto-correlation.

  Implementation Logic:
  1. Add terraform_variable_values table for .tfvars value storage
  2. Remove .tfvars skip, implement _extract_tfvars() method
  3. Create /rules/terraform/terraform_analyze.py following TEMPLATE_STANDARD_RULE.py
  4. Migrate 6 security checks from TerraformAnalyzer to rule (public S3, IAM wildcards, secrets, encryption,
  security groups)
  5. Add NEW .tfvars secret scanning using high-entropy detection
  6. Refactor TerraformAnalyzer.analyze() to delegate to orchestrated rule
  7. Maintain backward compatibility with aud terraform analyze CLI command

  Confidence Level: HIGH

  Files Modified: 6 (schema, extractor, analyzer, 3 new rule files)

  Lines Changed: ~400 (200 new, 200 refactored)

  Validation: Test Terraform project with public S3, weak passwords, high-entropy secrets in .tfvars

  ---
  Awaiting Architect Approval

  Architect, please review this verification report and approve implementation plan. Specific decisions requiring
  validation:

  1. Table Design: Separate terraform_variable_values table vs extending terraform_variables?
  2. Analyzer Deprecation: Maintain TerraformAnalyzer as backward-compat wrapper or full removal?
  3. Entry Point: Use analyze() function (matches 43 production rules) vs find_* (orchestrator.py:142 suggests)?
  4. High-Entropy Threshold: 4.0 bits/char for secret detection (matches docker_analyze.py)?

  Ready to implement upon approval.