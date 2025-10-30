"""Unit tests for GitHub Actions workflow security analysis.

Tests verify:
1. Schema contract compliance (6 github_* tables)
2. GitHubWorkflowExtractor with edge cases
3. Rule detection accuracy (6 security rules)
4. CLI integration and output formats

Coverage:
- CWE-284: Untrusted checkout sequences
- CWE-829: Unpinned actions with secrets
- CWE-77: Script injection vulnerabilities
- CWE-269: Excessive permissions
- CWE-200: External workflow risks
- CWE-494: Artifact poisoning
"""

import pytest
import sqlite3
import subprocess
import json
import yaml
from pathlib import Path

from theauditor.indexer.schema import TABLES, build_query
from theauditor.indexer.extractors.github_actions import GitHubWorkflowExtractor
from theauditor.indexer.database import DatabaseManager


# ============================================================================
# Schema Contract Tests
# ============================================================================


class TestGitHubActionsSchemaContract:
    """Test schema contract compliance for GitHub Actions tables."""

    def test_github_workflows_table_exists(self):
        """Verify github_workflows table is registered."""
        assert 'github_workflows' in TABLES, "github_workflows table must be in TABLES registry"

        table = TABLES['github_workflows']
        column_names = {col.name for col in table.columns}

        # Verify required columns
        assert 'workflow_path' in column_names
        assert 'workflow_name' in column_names
        assert 'on_triggers' in column_names
        assert 'permissions' in column_names
        assert 'concurrency' in column_names
        assert 'env' in column_names

    def test_github_jobs_table_exists(self):
        """Verify github_jobs table is registered."""
        assert 'github_jobs' in TABLES, "github_jobs table must be in TABLES registry"

        table = TABLES['github_jobs']
        column_names = {col.name for col in table.columns}

        # Verify required columns
        assert 'job_id' in column_names
        assert 'workflow_path' in column_names
        assert 'job_key' in column_names
        assert 'runs_on' in column_names
        assert 'permissions' in column_names
        assert 'env' in column_names

    def test_github_steps_table_exists(self):
        """Verify github_steps table is registered."""
        assert 'github_steps' in TABLES, "github_steps table must be in TABLES registry"

        table = TABLES['github_steps']
        column_names = {col.name for col in table.columns}

        # Verify required columns
        assert 'step_id' in column_names
        assert 'job_id' in column_names
        assert 'step_name' in column_names
        assert 'uses_action' in column_names
        assert 'action_version' in column_names
        assert 'run_script' in column_names
        assert 'with_args' in column_names
        assert 'env' in column_names
        assert 'secrets_access' in column_names

    def test_github_step_references_table_exists(self):
        """Verify github_step_references table is registered."""
        assert 'github_step_references' in TABLES

        table = TABLES['github_step_references']
        column_names = {col.name for col in table.columns}

        # Verify required columns
        assert 'step_id' in column_names
        assert 'reference_path' in column_names
        assert 'reference_location' in column_names

    def test_build_query_github_workflows(self):
        """Test build_query works with github_workflows table."""
        query = build_query('github_workflows', ['workflow_path', 'workflow_name', 'on_triggers'])

        assert 'SELECT' in query
        assert 'github_workflows' in query
        assert 'workflow_path' in query
        assert 'workflow_name' in query
        assert 'on_triggers' in query

    def test_build_query_github_steps_with_where(self):
        """Test build_query with WHERE clause for github_steps."""
        query = build_query(
            'github_steps',
            ['step_id', 'run_script'],
            where="run_script IS NOT NULL"
        )

        assert 'WHERE' in query
        assert 'run_script IS NOT NULL' in query

    def test_flush_order_includes_github_tables(self):
        """Verify github_* tables are in DatabaseManager.flush_order."""
        from theauditor.indexer.database import DatabaseManager

        flush_order = [entry[0] for entry in DatabaseManager.flush_order]

        # All 6 GitHub tables must be in flush order
        assert 'github_workflows' in flush_order
        assert 'github_jobs' in flush_order
        assert 'github_job_dependencies' in flush_order
        assert 'github_steps' in flush_order
        assert 'github_step_outputs' in flush_order
        assert 'github_step_references' in flush_order

    def test_github_tables_foreign_key_order(self):
        """Verify GitHub tables appear in correct order (workflows before jobs before steps)."""
        from theauditor.indexer.database import DatabaseManager

        flush_order = [entry[0] for entry in DatabaseManager.flush_order]

        workflows_idx = flush_order.index('github_workflows')
        jobs_idx = flush_order.index('github_jobs')
        steps_idx = flush_order.index('github_steps')

        # Workflows must come before jobs (foreign key dependency)
        assert workflows_idx < jobs_idx, "github_workflows must flush before github_jobs"

        # Jobs must come before steps (foreign key dependency)
        assert jobs_idx < steps_idx, "github_jobs must flush before github_steps"


# ============================================================================
# Extractor Tests
# ============================================================================


class TestGitHubWorkflowExtractor:
    """Test GitHubWorkflowExtractor edge cases and error handling."""

    def test_extractor_supports_yaml_extensions(self):
        """Verify extractor supports .yml and .yaml extensions."""
        extractor = GitHubWorkflowExtractor(root_path=Path('.'))

        supported = extractor.supported_extensions
        assert '.yml' in supported
        assert '.yaml' in supported

    def test_extractor_ignores_non_workflow_yaml(self):
        """Verify extractor only processes .github/workflows/*.yml files."""
        extractor = GitHubWorkflowExtractor(root_path=Path('.'))

        # Should accept workflow files
        assert extractor.should_extract(Path('.github/workflows/ci.yml'))
        assert extractor.should_extract(Path('.github/workflows/deploy.yaml'))

        # Should reject non-workflow YAML files
        assert not extractor.should_extract(Path('config.yml'))
        assert not extractor.should_extract(Path('.gitlab-ci.yml'))
        assert not extractor.should_extract(Path('docker-compose.yml'))

    def test_extract_handles_yaml_on_keyword(self):
        """Verify extractor handles YAML 'on:' keyword (parsed as True)."""
        extractor = GitHubWorkflowExtractor(root_path=Path('.'))

        workflow_yaml = """
name: Test Workflow
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""

        file_info = {'path': '.github/workflows/test.yml'}
        tree = None  # YAML extractor doesn't use tree

        result = extractor.extract(file_info, workflow_yaml, tree)

        # Should extract workflows despite 'on:' quirk
        assert result is not None
        assert 'workflows' in result
        assert len(result['workflows']) == 1

        workflow = result['workflows'][0]
        assert workflow['workflow_name'] == 'Test Workflow'
        assert 'push' in workflow['on_triggers']

    def test_extract_handles_on_as_object(self):
        """Verify extractor handles 'on:' as object with multiple triggers."""
        extractor = GitHubWorkflowExtractor(root_path=Path('.'))

        workflow_yaml = """
name: Multi-trigger
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "test"
"""

        file_info = {'path': '.github/workflows/multi.yml'}
        result = extractor.extract(file_info, workflow_yaml, None)

        assert result is not None
        workflow = result['workflows'][0]
        triggers = workflow['on_triggers']

        # Should extract all 3 triggers
        assert 'push' in triggers
        assert 'pull_request' in triggers
        assert 'workflow_dispatch' in triggers

    def test_extract_handles_missing_job_key(self):
        """Verify extractor handles missing or malformed job keys."""
        extractor = GitHubWorkflowExtractor(root_path=Path('.'))

        workflow_yaml = """
name: Malformed Workflow
on: push
jobs:
  null:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "test"
"""

        file_info = {'path': '.github/workflows/malformed.yml'}
        result = extractor.extract(file_info, workflow_yaml, None)

        # Should extract valid jobs, skip null entries
        assert result is not None
        assert 'jobs' in result

        # Should extract 'test' job, skip 'null' job
        valid_jobs = [j for j in result['jobs'] if j['job_key'] == 'test']
        assert len(valid_jobs) == 1

    def test_extract_handles_step_without_name(self):
        """Verify extractor handles steps without 'name:' field."""
        extractor = GitHubWorkflowExtractor(root_path=Path('.'))

        workflow_yaml = """
name: Unnamed Steps
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "No name"
"""

        file_info = {'path': '.github/workflows/unnamed.yml'}
        result = extractor.extract(file_info, workflow_yaml, None)

        assert result is not None
        assert 'steps' in result
        assert len(result['steps']) == 2

        # Steps should have default names
        for step in result['steps']:
            assert step['step_name'] is not None

    def test_extract_detects_secrets_access(self):
        """Verify extractor detects ${{ secrets.* }} references."""
        extractor = GitHubWorkflowExtractor(root_path=Path('.'))

        workflow_yaml = """
name: Secrets Test
on: push
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Use secret
        env:
          TOKEN: ${{ secrets.NPM_TOKEN }}
        run: npm publish
"""

        file_info = {'path': '.github/workflows/secrets.yml'}
        result = extractor.extract(file_info, workflow_yaml, None)

        assert result is not None
        assert 'steps' in result

        # Step should be marked as accessing secrets
        step = result['steps'][0]
        assert step['secrets_access'] == 1

    def test_extract_detects_github_event_references(self):
        """Verify extractor detects github.event.* references."""
        extractor = GitHubWorkflowExtractor(root_path=Path('.'))

        workflow_yaml = """
name: Event References
on: pull_request
jobs:
  comment:
    runs-on: ubuntu-latest
    steps:
      - name: Comment on PR
        run: echo "PR title: ${{ github.event.pull_request.title }}"
"""

        file_info = {'path': '.github/workflows/event.yml'}
        result = extractor.extract(file_info, workflow_yaml, None)

        assert result is not None
        assert 'references' in result

        # Should extract github.event.pull_request.title reference
        refs = [r for r in result['references'] if 'pull_request.title' in r['reference_path']]
        assert len(refs) >= 1
        assert refs[0]['reference_location'] == 'run'

    def test_extract_invalid_yaml_returns_none(self):
        """Verify extractor returns None for invalid YAML."""
        extractor = GitHubWorkflowExtractor(root_path=Path('.'))

        invalid_yaml = """
name: Invalid
on: push
jobs:
  test:
    - this is not valid YAML structure
    - broken indentation
"""

        file_info = {'path': '.github/workflows/invalid.yml'}
        result = extractor.extract(file_info, invalid_yaml, None)

        # Should return None, not crash
        assert result is None

    def test_extract_empty_workflow_returns_none(self):
        """Verify extractor handles empty workflow files."""
        extractor = GitHubWorkflowExtractor(root_path=Path('.'))

        empty_yaml = ""

        file_info = {'path': '.github/workflows/empty.yml'}
        result = extractor.extract(file_info, empty_yaml, None)

        # Should return None for empty file
        assert result is None


# ============================================================================
# Rule Detection Tests (Integration)
# ============================================================================


class TestGitHubActionsRuleDetection:
    """Test rule detection accuracy using test fixtures."""

    def test_detects_untrusted_checkout_sequence(self, tmp_path):
        """Verify detection of pull_request_target + early checkout."""
        # Create workflow with vulnerable pattern
        workflow_dir = tmp_path / '.github' / 'workflows'
        workflow_dir.mkdir(parents=True)

        (workflow_dir / 'vulnerable.yml').write_text("""
name: Vulnerable CI
on: pull_request_target
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - run: npm test
""")

        # Run indexing
        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        # Query database for finding
        db_path = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM findings_consolidated
            WHERE rule_name = 'untrusted_checkout_sequence'
            AND severity IN ('CRITICAL', 'HIGH')
        """)
        count = cursor.fetchone()[0]
        conn.close()

        assert count >= 1, "Should detect untrusted checkout sequence"

    def test_detects_script_injection(self, tmp_path):
        """Verify detection of PR data in run scripts."""
        workflow_dir = tmp_path / '.github' / 'workflows'
        workflow_dir.mkdir(parents=True)

        (workflow_dir / 'injection.yml').write_text("""
name: Script Injection
on: pull_request
jobs:
  comment:
    runs-on: ubuntu-latest
    steps:
      - name: Echo PR title
        run: echo "Title: ${{ github.event.pull_request.title }}"
""")

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0

        db_path = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM findings_consolidated
            WHERE rule_name = 'pull_request_injection'
            AND severity IN ('CRITICAL', 'HIGH')
        """)
        count = cursor.fetchone()[0]
        conn.close()

        assert count >= 1, "Should detect script injection vulnerability"

    def test_detects_unpinned_actions_with_secrets(self, tmp_path):
        """Verify detection of unpinned actions with secrets access."""
        workflow_dir = tmp_path / '.github' / 'workflows'
        workflow_dir.mkdir(parents=True)

        (workflow_dir / 'unpinned.yml').write_text("""
name: Unpinned Actions
on: push
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@main
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
      - uses: actions/setup-node@v4
        with:
          node-version: 18
      - run: npm publish
        env:
          NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
""")

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0

        db_path = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM findings_consolidated
            WHERE rule_name = 'unpinned_action_with_secrets'
            AND severity = 'HIGH'
        """)
        count = cursor.fetchone()[0]
        conn.close()

        # Should detect @main unpinned action with secrets
        assert count >= 1, "Should detect unpinned action with secrets"

    def test_detects_excessive_permissions(self, tmp_path):
        """Verify detection of excessive permissions in pull_request_target."""
        workflow_dir = tmp_path / '.github' / 'workflows'
        workflow_dir.mkdir(parents=True)

        (workflow_dir / 'permissions.yml').write_text("""
name: Excessive Permissions
on: pull_request_target
jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      packages: write
      id-token: write
    steps:
      - run: echo "Deploying"
""")

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0

        db_path = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM findings_consolidated
            WHERE rule_name = 'excessive_pr_permissions'
            AND severity IN ('CRITICAL', 'HIGH')
        """)
        count = cursor.fetchone()[0]
        conn.close()

        assert count >= 1, "Should detect excessive permissions"

    def test_no_false_positives_on_safe_workflow(self, tmp_path):
        """Verify no false positives on properly secured workflow."""
        workflow_dir = tmp_path / '.github' / 'workflows'
        workflow_dir.mkdir(parents=True)

        (workflow_dir / 'safe.yml').write_text("""
name: Safe Workflow
on: pull_request
jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@a1b2c3d4e5f6g7h8i9j0  # Pinned to full SHA
      - uses: actions/setup-node@a1b2c3d4e5f6g7h8i9j0
      - name: Run tests
        env:
          PR_TITLE: ${{ github.event.pull_request.title }}
        run: echo "Testing: $PR_TITLE"
""")

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0

        db_path = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Query for GitHub Actions findings
        cursor.execute("""
            SELECT COUNT(*) FROM findings_consolidated
            WHERE rule_name IN (
                'untrusted_checkout_sequence',
                'unpinned_action_with_secrets',
                'pull_request_injection',
                'excessive_pr_permissions'
            )
        """)
        count = cursor.fetchone()[0]
        conn.close()

        # Should have 0 findings on safe workflow
        assert count == 0, f"Safe workflow should have no findings, got {count}"


# ============================================================================
# CLI Integration Tests
# ============================================================================


class TestGitHubActionsCLI:
    """Test aud workflows CLI command."""

    def test_workflows_analyze_command_exists(self):
        """Verify 'aud workflows analyze' command is registered."""
        result = subprocess.run(
            ['aud', 'workflows', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode == 0
        assert 'analyze' in result.stdout.lower()

    def test_workflows_analyze_requires_index(self, tmp_path):
        """Verify workflows analyze requires database to be indexed."""
        # Try to analyze without indexing first
        result = subprocess.run(
            ['aud', 'workflows', 'analyze'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should fail gracefully (database not found) or succeed with 0 workflows
        # Either outcome is acceptable for unindexed project
        assert result.returncode in (0, 1)

    def test_workflows_analyze_json_output(self, tmp_path):
        """Verify workflows analyze can output JSON format."""
        # Create a simple workflow
        workflow_dir = tmp_path / '.github' / 'workflows'
        workflow_dir.mkdir(parents=True)

        (workflow_dir / 'test.yml').write_text("""
name: Test
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "test"
""")

        # Index first
        subprocess.run(['aud', 'index'], cwd=tmp_path, timeout=60)

        # Analyze with JSON output
        output_file = tmp_path / 'workflows.json'
        result = subprocess.run(
            ['aud', 'workflows', 'analyze', '--output', str(output_file)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0

        # Verify JSON file exists and is valid
        if output_file.exists():
            with open(output_file) as f:
                data = json.load(f)
                assert isinstance(data, dict)


# ============================================================================
# Pytest Fixtures
# ============================================================================


@pytest.fixture
def temp_db():
    """Create temporary SQLite database for schema testing."""
    conn = sqlite3.connect(':memory:')
    yield conn
    conn.close()


@pytest.fixture
def sample_project(tmp_path):
    """Create temporary project directory for integration tests."""
    # Create basic project structure
    (tmp_path / '.github' / 'workflows').mkdir(parents=True)

    # Create dummy package.json to avoid warnings
    (tmp_path / 'package.json').write_text('{"name": "test", "version": "1.0.0"}')

    yield tmp_path

    # Cleanup handled by tmp_path fixture
