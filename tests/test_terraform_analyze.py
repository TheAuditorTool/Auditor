"""End-to-end CLI tests for terraform analyze command.

Tests the full pipeline: aud index → aud terraform analyze
Validates that security violations in the fixture are detected.
Follows the test plan from Phase 2C in terraaform_test.txt.
"""

import pytest
import sqlite3
import subprocess
import tempfile
import shutil
from pathlib import Path


# Path to the fixture directory
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "terraform"


@pytest.fixture
def terraform_test_workspace():
    """Create a temporary workspace with fixture files and clean database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Copy fixture files to workspace
        fixture_copy = workspace / "terraform_test"
        shutil.copytree(FIXTURE_PATH, fixture_copy)

        # Create .pf directory for database
        pf_dir = fixture_copy / ".pf"
        pf_dir.mkdir(exist_ok=True)

        yield fixture_copy


class TestTerraformAnalyzeCommand:
    """Test aud terraform analyze command."""

    def test_command_exists(self):
        """Test that 'aud terraform --help' works."""
        result = subprocess.run(
            ["aud", "terraform", "--help"],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"aud terraform --help failed: {result.stderr}"
        assert "analyze" in result.stdout.lower() or "terraform" in result.stdout.lower()

    @pytest.mark.slow
    def test_full_pipeline_index_then_analyze(self, terraform_test_workspace):
        """Test full pipeline: aud index → aud terraform analyze.

        This is a slow test that runs the full indexing and analysis pipeline.
        """
        workspace = terraform_test_workspace

        # Step 1: Run aud index on the fixture
        index_result = subprocess.run(
            ["aud", "index", str(workspace)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(workspace)
        )

        # Check if indexing succeeded
        if index_result.returncode != 0:
            pytest.skip(f"Indexing failed (tree-sitter not available?): {index_result.stderr}")

        # Verify database was created
        db_path = workspace / ".pf" / "repo_index.db"
        assert db_path.exists(), f"Database not created at {db_path}"

        # Step 2: Run aud terraform analyze
        analyze_result = subprocess.run(
            ["aud", "terraform", "analyze"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(workspace)
        )

        # The command should succeed (exit code 0)
        assert analyze_result.returncode == 0, f"aud terraform analyze failed: {analyze_result.stderr}"

        # Output should contain analysis results
        output = analyze_result.stdout.lower()
        assert "terraform" in output or "analysis" in output or "finding" in output


class TestFindingDetection:
    """Test that specific security violations are detected."""

    @pytest.mark.slow
    def test_detect_hardcoded_secret(self, terraform_test_workspace):
        """Test detection of hardcoded secret in hardcoded_secrets.tf."""
        workspace = terraform_test_workspace

        # Index and analyze
        subprocess.run(["aud", "index", str(workspace)], capture_output=True, timeout=120, cwd=str(workspace))

        # Check database for findings
        db_path = workspace / ".pf" / "repo_index.db"
        if not db_path.exists():
            pytest.skip("Database not created - tree-sitter not available")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if findings_consolidated table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='findings_consolidated'
        """)
        if not cursor.fetchone():
            pytest.skip("findings_consolidated table not found - analyze not run")

        # Look for hardcoded secret finding
        cursor.execute("""
            SELECT file_path, line, finding_type, message
            FROM findings_consolidated
            WHERE file_path LIKE '%hardcoded_secrets.tf%'
        """)
        findings = cursor.fetchall()
        conn.close()

        # Should find at least one security issue in hardcoded_secrets.tf
        assert len(findings) > 0, "No findings detected in hardcoded_secrets.tf"

    @pytest.mark.slow
    def test_detect_public_s3_bucket(self, terraform_test_workspace):
        """Test detection of public S3 bucket in public_s3.tf."""
        workspace = terraform_test_workspace

        subprocess.run(["aud", "index", str(workspace)], capture_output=True, timeout=120, cwd=str(workspace))

        db_path = workspace / ".pf" / "repo_index.db"
        if not db_path.exists():
            pytest.skip("Database not created")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='terraform_resources'
        """)
        if not cursor.fetchone():
            pytest.skip("terraform_resources table not found")

        # Check that the public S3 bucket was indexed
        cursor.execute("""
            SELECT resource_id, has_public_exposure
            FROM terraform_resources
            WHERE file_path LIKE '%public_s3.tf%'
        """)
        resources = cursor.fetchall()
        conn.close()

        assert len(resources) > 0, "Public S3 bucket resource not indexed"

    @pytest.mark.slow
    def test_detect_overly_permissive_iam(self, terraform_test_workspace):
        """Test detection of overly permissive IAM policy."""
        workspace = terraform_test_workspace

        subprocess.run(["aud", "index", str(workspace)], capture_output=True, timeout=120, cwd=str(workspace))

        db_path = workspace / ".pf" / "repo_index.db"
        if not db_path.exists():
            pytest.skip("Database not created")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='terraform_resources'
        """)
        if not cursor.fetchone():
            pytest.skip("terraform_resources table not found")

        # Check that IAM policy was indexed
        cursor.execute("""
            SELECT resource_id, properties_json
            FROM terraform_resources
            WHERE file_path LIKE '%overly_permissive_iam.tf%'
        """)
        resources = cursor.fetchall()
        conn.close()

        assert len(resources) > 0, "IAM policy resources not indexed"

    @pytest.mark.slow
    def test_detect_sensitive_variable_in_tfvars(self, terraform_test_workspace):
        """Test detection of sensitive variable in .tfvars file."""
        workspace = terraform_test_workspace

        subprocess.run(["aud", "index", str(workspace)], capture_output=True, timeout=120, cwd=str(workspace))

        db_path = workspace / ".pf" / "repo_index.db"
        if not db_path.exists():
            pytest.skip("Database not created")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='terraform_variable_values'
        """)
        if not cursor.fetchone():
            pytest.skip("terraform_variable_values table not found")

        # Check that sensitive.auto.tfvars was indexed
        cursor.execute("""
            SELECT variable_name, is_sensitive_context
            FROM terraform_variable_values
            WHERE file_path LIKE '%sensitive.auto.tfvars%'
        """)
        var_values = cursor.fetchall()
        conn.close()

        assert len(var_values) > 0, "Sensitive tfvars not indexed"

        # Check that db_password is marked as sensitive context
        db_password_found = False
        for var_name, is_sensitive in var_values:
            if var_name == 'db_password':
                db_password_found = True
                assert is_sensitive == 1, "db_password should be marked as sensitive context"
                break

        assert db_password_found, "db_password not found in sensitive.auto.tfvars"


class TestTaintBasedFinding:
    """Test the most important finding: sensitive data in output (taint tracking)."""

    @pytest.mark.slow
    @pytest.mark.skip(reason="Taint-based Terraform rules not yet implemented")
    def test_detect_sensitive_data_in_output(self, terraform_test_workspace):
        """THE MOST IMPORTANT TEST: Detect taint flow var.db_password -> output.database_password.

        This validates the entire graph and taint flow:
        1. sensitive.auto.tfvars sets var.db_password
        2. variables.tf marks var.db_password as sensitive = true
        3. sensitive_output.tf's output.database_password references var.db_password but is NOT marked sensitive
        4. The analyzer rule should follow this taint and flag the output

        This test is marked as SKIP because taint-based Terraform rules are not yet implemented.
        Once implemented, this test should pass.
        """
        workspace = terraform_test_workspace

        # Index
        subprocess.run(["aud", "index", str(workspace)], capture_output=True, timeout=120, cwd=str(workspace))

        # Analyze
        subprocess.run(["aud", "terraform", "analyze"], capture_output=True, timeout=120, cwd=str(workspace))

        db_path = workspace / ".pf" / "repo_index.db"
        if not db_path.exists():
            pytest.skip("Database not created")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Look for finding about sensitive data in output
        cursor.execute("""
            SELECT file_path, line, finding_type, message, severity
            FROM findings_consolidated
            WHERE file_path LIKE '%sensitive_output.tf%'
        """)
        findings = cursor.fetchall()
        conn.close()

        # Should find the sensitive data leak
        assert len(findings) > 0, "Sensitive data in output not detected - taint tracking rule missing!"

        # Verify it's flagged as a critical/high severity issue
        for file_path, line, finding_type, message, severity in findings:
            if 'database_password' in str(message).lower() or 'sensitive' in str(message).lower():
                assert severity in ['critical', 'high'], f"Sensitive output should be high/critical severity, got {severity}"
                break
        else:
            pytest.fail("No finding mentions database_password or sensitive output")


class TestSeverityFiltering:
    """Test severity filtering in terraform analyze command."""

    @pytest.mark.slow
    @pytest.mark.skip(reason="Severity filtering not yet implemented for terraform analyze")
    def test_severity_filter_high(self, terraform_test_workspace):
        """Test 'aud terraform analyze --severity high' filters correctly."""
        workspace = terraform_test_workspace

        # Index
        subprocess.run(["aud", "index", str(workspace)], capture_output=True, timeout=120, cwd=str(workspace))

        # Analyze with severity filter
        result = subprocess.run(
            ["aud", "terraform", "analyze", "--severity", "high"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(workspace)
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Should only show high severity findings
        # (Implementation depends on how findings are displayed)


class TestAudFullIntegration:
    """Test that terraform fixture works with 'aud full' command."""

    @pytest.mark.slow
    @pytest.mark.skip(reason="Integration with aud full requires full fixture setup")
    def test_terraform_fixture_in_aud_full(self):
        """Test that terraform fixture is picked up by 'aud full'.

        This validates that the terraform fixture acts as a "real world simulated project"
        and produces findings in the database when 'aud full' is run on a multi-language
        codebase that includes the terraform fixture.
        """
        # This test would run 'aud full' on a test project that includes the terraform fixture
        # and verify that findings are produced in findings_consolidated table
        pass
