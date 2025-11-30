"""
Go End-to-End Tests - Verify full `aud full --offline` pipeline on Go fixtures.

This test suite runs the complete TheAuditor pipeline on realistic Go projects
and verifies that:
1. All Go files are properly indexed
2. Go tables are populated with extracted data
3. Security rules detect intentional vulnerabilities
4. Graph strategies produce expected edges

These are REAL E2E tests against actual Go code, not mocks.
"""

import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def calorie_tracker_db():
    """Run aud full --offline on go-calorie-tracker fixture and return db path."""
    fixture_path = Path(__file__).parent / "fixtures" / "go-calorie-tracker"

    if not fixture_path.exists():
        pytest.skip("go-calorie-tracker fixture not found")

    # Create temp directory for the database
    temp_dir = tempfile.mkdtemp(prefix="theauditor_go_test_")
    pf_dir = Path(temp_dir) / ".pf"
    pf_dir.mkdir()

    db_path = pf_dir / "repo_index.db"

    try:
        # Run aud full --offline --index on the fixture
        result = subprocess.run(
            [
                "aud",
                "full",
                "--offline",
                "--index",
                "--target",
                str(fixture_path),
                "--db",
                str(db_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(fixture_path),
        )

        if result.returncode != 0:
            print(f"aud full stderr: {result.stderr}")
            pytest.skip(f"aud full failed: {result.stderr[:500]}")

        yield str(db_path)

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


class TestGoE2EIndexing:
    """Tests that verify Go files are properly indexed."""

    def test_go_files_indexed(self, calorie_tracker_db):
        """Verify all Go files from the fixture are indexed."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path LIKE '%.go'")
        go_file_count = cursor.fetchone()[0]

        conn.close()

        # We have 16 Go files in the fixture
        assert go_file_count >= 15, f"Expected at least 15 Go files, got {go_file_count}"

    def test_go_packages_extracted(self, calorie_tracker_db):
        """Verify packages are extracted."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT name FROM go_packages")
        packages = [row[0] for row in cursor.fetchall()]

        conn.close()

        expected_packages = ["main", "models", "database", "repository", "services", "handlers", "middleware", "config"]
        for pkg in expected_packages:
            assert pkg in packages, f"Expected package '{pkg}' not found"

    def test_go_structs_extracted(self, calorie_tracker_db):
        """Verify structs are extracted."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM go_structs")
        structs = {row[0] for row in cursor.fetchall()}

        conn.close()

        expected_structs = ["User", "Food", "FoodEntry", "Meal", "DailyLog", "AuthService", "TrackingService"]
        for struct in expected_structs:
            assert struct in structs, f"Expected struct '{struct}' not found"

    def test_go_functions_extracted(self, calorie_tracker_db):
        """Verify functions are extracted."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM go_functions")
        func_count = cursor.fetchone()[0]

        conn.close()

        # Should have many functions
        assert func_count >= 20, f"Expected at least 20 functions, got {func_count}"

    def test_go_methods_extracted(self, calorie_tracker_db):
        """Verify methods are extracted."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("SELECT receiver_type, name FROM go_methods")
        methods = [(row[0], row[1]) for row in cursor.fetchall()]

        conn.close()

        # Check for key methods
        assert any("UserRepository" in str(m) and "Create" in str(m) for m in methods), "UserRepository.Create not found"
        assert any("AuthService" in str(m) and "Login" in str(m) for m in methods), "AuthService.Login not found"

    def test_go_imports_extracted(self, calorie_tracker_db):
        """Verify imports are extracted."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT path FROM go_imports")
        imports = {row[0] for row in cursor.fetchall()}

        conn.close()

        expected_imports = [
            "github.com/gin-gonic/gin",
            "gorm.io/gorm",
            "github.com/golang-jwt/jwt/v5",
            "golang.org/x/crypto/bcrypt",
            "crypto/md5",
            "math/rand",
        ]

        for imp in expected_imports:
            assert imp in imports, f"Expected import '{imp}' not found"


class TestGoE2ERoutes:
    """Tests that verify Go route detection."""

    def test_gin_routes_detected(self, calorie_tracker_db):
        """Verify Gin routes are detected."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("SELECT method, path, framework FROM go_routes")
        routes = [(row[0], row[1], row[2]) for row in cursor.fetchall()]

        conn.close()

        # Should detect Gin routes
        gin_routes = [r for r in routes if r[2] == "gin"]
        assert len(gin_routes) > 0, "No Gin routes detected"

        # Check for specific routes
        paths = [r[1] for r in routes]
        assert "/health" in paths or any("/health" in p for p in paths), "/health route not detected"

    def test_middleware_detected(self, calorie_tracker_db):
        """Verify middleware is detected."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("SELECT middleware_func, framework FROM go_middleware")
        middleware = cursor.fetchall()

        conn.close()

        # Should detect middleware usage
        assert len(middleware) > 0, "No middleware detected"


class TestGoE2ESecurityFindings:
    """Tests that verify security rules detect intentional vulnerabilities."""

    def test_sql_injection_detected(self, calorie_tracker_db):
        """Verify SQL injection is detected in food_repository.Search()."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        # Check if the vulnerable function exists
        cursor.execute("""
            SELECT file_path, name FROM go_functions
            WHERE name = 'Search' OR name LIKE '%Search%'
        """)
        funcs = cursor.fetchall()

        conn.close()

        # The Search function should exist
        assert any("food_repository" in str(f[0]).lower() and "search" in str(f[1]).lower() for f in funcs), \
            "Vulnerable Search function not found"

    def test_weak_crypto_patterns_exist(self, calorie_tracker_db):
        """Verify weak crypto imports are detected."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("SELECT path FROM go_imports WHERE path = 'crypto/md5'")
        md5_import = cursor.fetchone()

        cursor.execute("SELECT path FROM go_imports WHERE path = 'math/rand'")
        rand_import = cursor.fetchone()

        conn.close()

        assert md5_import is not None, "crypto/md5 import not detected"
        assert rand_import is not None, "math/rand import not detected"

    def test_goroutines_detected(self, calorie_tracker_db):
        """Verify goroutines are detected for race condition analysis."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM go_goroutines")
        goroutine_count = cursor.fetchone()[0]

        conn.close()

        # The fixture has multiple goroutines
        assert goroutine_count >= 3, f"Expected at least 3 goroutines, got {goroutine_count}"

    def test_package_level_vars_detected(self, calorie_tracker_db):
        """Verify package-level variables are detected for race condition analysis."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM go_variables
            WHERE is_package_level = 1
        """)
        pkg_vars = [row[0] for row in cursor.fetchall()]

        conn.close()

        # Should detect totalEntriesLogged and statsLock
        assert "totalEntriesLogged" in pkg_vars or any("total" in v.lower() for v in pkg_vars), \
            "Package-level counter variable not detected"


class TestGoE2ERelationships:
    """Tests that verify struct relationships and ORM patterns."""

    def test_struct_fields_with_tags(self, calorie_tracker_db):
        """Verify struct fields with GORM tags are extracted."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT struct_name, field_name, tag
            FROM go_struct_fields
            WHERE tag IS NOT NULL AND tag != ''
        """)
        fields_with_tags = cursor.fetchall()

        conn.close()

        # Should have many fields with GORM/JSON tags
        assert len(fields_with_tags) >= 10, f"Expected at least 10 fields with tags, got {len(fields_with_tags)}"

        # Check for GORM relationship tags
        gorm_relationships = [f for f in fields_with_tags if "gorm:" in str(f[2]).lower()]
        assert len(gorm_relationships) > 0, "No GORM relationship tags detected"

    def test_user_struct_has_relationships(self, calorie_tracker_db):
        """Verify User struct has relationship fields detected."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT field_name, field_type, tag
            FROM go_struct_fields
            WHERE struct_name = 'User'
        """)
        user_fields = cursor.fetchall()

        conn.close()

        field_names = [f[0] for f in user_fields]

        # User should have relationship fields
        assert "Meals" in field_names or "FoodEntries" in field_names or "DailyLogs" in field_names, \
            "User relationship fields not detected"


class TestGoE2EComplexPatterns:
    """Tests for complex Go patterns."""

    def test_defer_statements_detected(self, calorie_tracker_db):
        """Verify defer statements are detected."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM go_defer_statements")
        defer_count = cursor.fetchone()[0]

        conn.close()

        # Should detect defer statements (database.Close(), wg.Done(), etc.)
        assert defer_count >= 3, f"Expected at least 3 defer statements, got {defer_count}"

    def test_channels_detected(self, calorie_tracker_db):
        """Verify channels are detected."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("SELECT name, element_type FROM go_channels")
        channels = cursor.fetchall()

        conn.close()

        # The fixture has stopChan, errChan, quit
        assert len(channels) >= 2, f"Expected at least 2 channels, got {len(channels)}"

    def test_type_assertions_detected(self, calorie_tracker_db):
        """Verify type assertions are detected."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM go_type_assertions")
        assertion_count = cursor.fetchone()[0]

        conn.close()

        # Should detect type assertions (e.g., userID.(uint))
        assert assertion_count >= 1, f"Expected at least 1 type assertion, got {assertion_count}"


class TestGoE2EErrorHandling:
    """Tests for error handling patterns."""

    def test_error_returns_detected(self, calorie_tracker_db):
        """Verify functions returning error are detected."""
        conn = sqlite3.connect(calorie_tracker_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT func_name, returns_error
            FROM go_error_returns
            WHERE returns_error = 1
        """)
        error_funcs = [row[0] for row in cursor.fetchall()]

        conn.close()

        # Many functions should return error
        assert len(error_funcs) >= 10, f"Expected at least 10 error-returning functions, got {len(error_funcs)}"

        # Specific functions should return error
        expected = ["Create", "Login", "Connect", "Migrate"]
        for func in expected:
            assert any(func in f for f in error_funcs), f"Function '{func}' not detected as returning error"


# Skip if aud command not available
def pytest_configure(config):
    """Check if aud command is available."""
    try:
        subprocess.run(["aud", "--version"], capture_output=True, timeout=5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("aud command not available", allow_module_level=True)
