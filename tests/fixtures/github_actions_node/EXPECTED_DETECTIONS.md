# Expected Detections - Node Test Fixtures

When running `aud detect-patterns` on this fixture, the GitHub Actions rules should detect:

## npm-publish-vulnerable.yml

**Expected Findings: 3**

1. **untrusted_checkout_sequence** (CRITICAL)
   - pull_request_target + early checkout of `github.event.pull_request.head.sha`
   - Has write permissions (contents, packages)

2. **excessive_pr_permissions** (CRITICAL)
   - pull_request_target + permissions: write (contents, packages)
   - Can publish to npm from untrusted context

3. **unpinned_action_with_secrets** (HIGH)
   - `actions/setup-node@v3` (mutable) + NPM_TOKEN secret

---

## node-script-injection.yml

**Expected Findings: 3**

1. **pull_request_injection** (CRITICAL)
   - `${{ github.event.pull_request.title }}` directly in run script

2. **pull_request_injection** (CRITICAL)
   - `${{ github.event.comment.body }}` in shell command

3. **pull_request_injection** (CRITICAL)
   - `${{ github.event.pull_request.head.ref }}` (branch name) in script

---

## unpinned-setup-node.yml

**Expected Findings: 3**

1. **unpinned_action_with_secrets** (HIGH)
   - `actions/setup-node@v3` + CODECOV_TOKEN + SENTRY_AUTH_TOKEN

2. **unpinned_action_with_secrets** (MEDIUM)
   - `pnpm/action-setup@v2` (mutable version)

3. **unpinned_action_with_secrets** (HIGH)
   - `codecov/codecov-action@v3` (external org) + CODECOV_TOKEN

---

## artifact-poisoning-npm.yml

**Expected Findings: 2**

1. **artifact_poisoning_risk** (CRITICAL)
   - Build job in pull_request_target → Publish job with npm publish
   - NPM_TOKEN used to publish untrusted artifact

2. **untrusted_checkout_sequence** (HIGH)
   - pull_request_target + checkout of untrusted PR sha

---

## safe-node-ci.yml

**Expected Findings: 0**

- Uses `pull_request` (not `pull_request_target`)
- Pinned to SHA: `actions/setup-node@5e33196f...`
- No secrets in untrusted context
- Read-only permissions

---

## Total Expected

**Minimum: 11 findings**
- 4 CRITICAL (script injection + artifact poisoning + excessive perms)
- 5 HIGH (unpinned actions + untrusted checkout)
- 2 MEDIUM (unpinned internal actions)

**False Positives: 0** (safe-node-ci.yml should be clean)
