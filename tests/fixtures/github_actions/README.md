# GitHub Actions Security Test Fixtures

This directory contains intentionally vulnerable GitHub Actions workflows for testing TheAuditor's security detection capabilities.

## Test Workflows

### 1. `vulnerable-pr-target.yml` - Untrusted Code Execution
**Vulnerability**: `pull_request_target` + early checkout allows attacker PR code to run with target repo secrets.
- **Pattern**: Checks out PR code before any validation
- **Risk**: RCE with GITHUB_TOKEN write permissions
- **Detection**: Rule should flag checkout of `github.event.pull_request.head.sha` in pull_request_target before validation job

### 2. `unpinned-actions-with-secrets.yml` - Supply Chain Attack
**Vulnerability**: Third-party actions pinned to mutable refs (main, v1) while exposing secrets.
- **Pattern**: `uses: third-party/action@main` + `secrets: inherit`
- **Risk**: Upstream action compromise = instant secret theft
- **Detection**: Rule should flag mutable versions with secret access

### 3. `script-injection.yml` - Command Injection
**Vulnerability**: Untrusted PR data directly interpolated into shell scripts.
- **Pattern**: `run: echo "${{ github.event.pull_request.title }}"`
- **Risk**: Arbitrary command execution via crafted PR titles
- **Detection**: Rule should flag `${{ github.event.* }}` in run: blocks

### 4. `privileged-pr-workflow.yml` - Permission Escalation
**Vulnerability**: `pull_request_target` with excessive permissions + checkout before validation.
- **Pattern**: `permissions: write-all` or `contents: write` + untrusted checkout
- **Risk**: PR can modify repo, create releases, etc.
- **Detection**: Rule should flag broad permissions in pull_request_target workflows

### 5. `reusable-workflow-risk.yml` - Transitive Secret Exposure
**Vulnerability**: Calling external reusable workflow with `secrets: inherit`.
- **Pattern**: `uses: org/repo/.github/workflows/deploy.yml@main` + secrets inheritance
- **Risk**: External repo gains access to all secrets
- **Detection**: Rule should flag secrets: inherit with external reusable workflows

### 6. `artifact-poisoning.yml` - Artifact Tampering
**Vulnerability**: Builds in untrusted context, then deploys artifact in trusted context.
- **Pattern**: Job A (pull_request_target) builds → Job B (trusted) deploys without validation
- **Risk**: Attacker-controlled build artifacts deployed to production
- **Detection**: Rule should flag artifact downloads in trusted jobs from untrusted jobs

## Expected Detections

Rules in `theauditor/rules/github_actions/` should detect:

1. **Untrusted Checkout Sequence** (`find_untrusted_checkout_sequence`)
   - `pull_request_target` trigger
   - Early `actions/checkout` step
   - Checkout of `github.event.pull_request.head.*` ref
   - Before any validation/approval job

2. **Unpinned Actions with Secrets** (`find_unpinned_action_with_secrets`)
   - Action version is mutable tag (main, master, v1, develop)
   - Step has `env` with `secrets.*` reference
   - Or job has `secrets: inherit`

3. **PR Data Injection** (`find_pull_request_injection`)
   - Reference to `github.event.pull_request.*` or `github.event.issue.*`
   - In `run:` script block
   - Without proper sanitization/quoting

4. **Excessive Permissions in PR Workflows** (`find_excessive_pr_permissions`)
   - Trigger includes `pull_request_target` or `issue_comment`
   - Permissions include `contents: write`, `packages: write`, `id-token: write`
   - Before validation step

## Testing Strategy

1. **Extraction Test**: Run `aud index` on this fixture directory
   - Verify all 6 workflows extracted to `github_workflows` table
   - Verify jobs, steps, dependencies, references extracted correctly

2. **Rules Test**: Run `aud detect-patterns` or `aud full`
   - Verify each rule detects its target vulnerability
   - Verify correct line numbers and severity levels
   - Verify no false positives on safe patterns

3. **Regression Test**: Keep this fixture in git
   - Any schema changes should still extract these workflows
   - Any rule changes should still detect these vulnerabilities

## Safe Workflow (Control)

`safe-workflow.yml` - Properly secured workflow for comparison:
- Uses `pull_request` (not target)
- Pins actions to SHA256
- No secret exposure
- Validates inputs before use
