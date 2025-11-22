# GitHub Actions Node Ecosystem Test Fixtures

**Purpose**: Test GitHub Actions extractor and rules against Node.js/npm CI/CD patterns.

**Why Separate from Python Fixtures?**
- Plant project doesn't use workflows (real-world scenario)
- Node ecosystem has unique patterns (npm publish, setup-node, package.json)
- Prevents "wtf is this" confusion - clearly labeled for Node testing

## Test Workflows

### Vulnerable Patterns (Node-Specific)

1. **npm-publish-vulnerable.yml** - NPM_TOKEN exposure in pull_request_target
2. **node-script-injection.yml** - package.json metadata in run scripts
3. **unpinned-setup-node.yml** - Mutable actions/setup-node@v3 with secrets
4. **artifact-poisoning-npm.yml** - Untrusted package build → publish chain

### Safe Control

5. **safe-node-ci.yml** - Properly secured Node CI workflow

## Expected Detections

When running `aud detect-patterns`, should find:
- Script injection (package.json data in shell)
- Unpinned actions (setup-node without SHA)
- Excessive permissions (NPM_TOKEN in PR context)
- Artifact poisoning (npm publish from untrusted builds)

## Usage

```bash
cd tests/fixtures/github_actions_node
aud index
aud detect-patterns
# Should detect 4+ vulnerabilities
```

---

**Note**: This fixture set complements `tests/fixtures/github_actions/` (Python-focused) to ensure comprehensive coverage across ecosystems.
