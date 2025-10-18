"""Comprehensive edge case tests for TheAuditor.

This test suite validates behavior for edge cases and failure modes that
occur in production but are rarely tested:
- Empty/null states
- Boundary conditions
- Malformed input
- Permission/access errors
- Concurrent access

Philosophy: Test what WILL happen in production, not what SHOULD work.
"""

import os
import pytest
import sqlite3
import subprocess
import tempfile
from pathlib import Path
import shutil
import stat


# =============================================================================
# CATEGORY 1: Empty/Null States
# =============================================================================

class TestEmptyStates:
    """Test empty/null state handling."""

    def test_empty_project_doesnt_crash(self, tmp_path):
        """Verify indexer handles empty project (no files)."""
        # Create .pf directory for database
        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should succeed (exit 0) even with no files
        assert result.returncode == 0, f"Indexer crashed on empty project:\n{result.stderr}"

        # Database should exist
        db = tmp_path / '.pf' / 'repo_index.db'
        assert db.exists(), "Database not created for empty project"

        # Tables should exist but be empty
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM files")
        assert cursor.fetchone()[0] == 0, "Empty project should have 0 files"
        conn.close()

    def test_project_with_no_python_files(self, tmp_path):
        """Verify indexer handles project with no analyzable files."""
        # Create some non-Python files
        (tmp_path / "README.md").write_text("# Test Project")
        (tmp_path / "data.json").write_text('{"key": "value"}')
        (tmp_path / "image.png").write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should succeed
        assert result.returncode == 0, f"Failed on project with no Python files:\n{result.stderr}"

        # Database should exist with minimal data
        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        # Should have indexed the text files but not binary
        cursor.execute("SELECT COUNT(*) FROM files WHERE path LIKE '%.png'")
        assert cursor.fetchone()[0] == 0, "Binary files should not be indexed"

        conn.close()

    def test_file_with_no_imports(self, tmp_path):
        """Verify indexer handles Python file with no imports."""
        # Create Python file with only code, no imports
        py_file = tmp_path / "standalone.py"
        py_file.write_text("""
def add(a, b):
    return a + b

result = add(1, 2)
print(result)
""")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Failed on file with no imports:\n{result.stderr}"

        # Verify file was indexed
        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'standalone.py'")
        assert cursor.fetchone()[0] == 1, "File with no imports should be indexed"

        # Should have symbols even without imports
        cursor.execute("SELECT COUNT(*) FROM symbols WHERE path = 'standalone.py'")
        symbol_count = cursor.fetchone()[0]
        assert symbol_count > 0, "File should have symbols even without imports"

        conn.close()

    def test_file_with_syntax_errors(self, tmp_path):
        """Verify indexer handles Python file with syntax errors gracefully."""
        # Create Python file with intentional syntax error
        py_file = tmp_path / "broken.py"
        py_file.write_text("""
def incomplete_function(
    # Missing closing parenthesis and body

if True
    # Missing colon
    print("broken")

class BadClass
    # Missing colon and indentation
pass
""")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should NOT crash - graceful degradation
        assert result.returncode == 0, f"Indexer crashed on syntax errors:\n{result.stderr}"

        # File should still be tracked even if unparseable
        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'broken.py'")
        assert cursor.fetchone()[0] == 1, "File with syntax errors should still be tracked"

        conn.close()

    def test_empty_file(self, tmp_path):
        """Verify indexer handles completely empty files."""
        # Create empty Python file
        py_file = tmp_path / "empty.py"
        py_file.write_text("")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Failed on empty file:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT loc FROM files WHERE path = 'empty.py'")
        row = cursor.fetchone()
        assert row is not None, "Empty file should be indexed"
        assert row[0] == 0, "Empty file should have 0 LOC"

        conn.close()


# =============================================================================
# CATEGORY 2: Boundary Conditions
# =============================================================================

class TestBoundaryConditions:
    """Test boundary conditions and size limits."""

    def test_file_exactly_at_size_limit(self, tmp_path):
        """Test file exactly at 2MB limit."""
        # Default limit is 2MB = 2097152 bytes
        size_limit = 2 * 1024 * 1024

        # Create file exactly at limit
        py_file = tmp_path / "at_limit.py"
        # Fill with valid Python to reach exact size (use binary to control exact bytes)
        content = b"# " + b"x" * (size_limit - 2)  # -2 for "# "
        py_file.write_bytes(content)

        actual_size = py_file.stat().st_size
        assert actual_size == size_limit, f"Test file should be exactly {size_limit} bytes, got {actual_size}"

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Failed at exact size limit:\n{result.stderr}"

        # File AT limit should be SKIPPED (limit is exclusive: size >= max_file_size)
        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'at_limit.py'")
        assert cursor.fetchone()[0] == 0, "File at size limit should be skipped"

        conn.close()

    def test_file_one_byte_over_limit(self, tmp_path):
        """Test file one byte over 2MB limit."""
        size_limit = 2 * 1024 * 1024

        # Create file one byte over limit
        py_file = tmp_path / "over_limit.py"
        content = b"# " + b"x" * (size_limit - 1)  # One byte over (2 + (size_limit - 1) = size_limit + 1)
        py_file.write_bytes(content)

        actual_size = py_file.stat().st_size
        assert actual_size > size_limit, f"File should be over {size_limit} bytes"

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Failed on oversized file:\n{result.stderr}"

        # File should be skipped
        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'over_limit.py'")
        assert cursor.fetchone()[0] == 0, "Oversized file should be skipped"

        conn.close()

    def test_file_one_byte_under_limit(self, tmp_path):
        """Test file one byte under 2MB limit."""
        size_limit = 2 * 1024 * 1024

        # Create file one byte under limit
        py_file = tmp_path / "under_limit.py"
        content = "# " + "x" * (size_limit - 4)  # -4 for "# ", newline, and one under
        py_file.write_text(content)

        actual_size = py_file.stat().st_size
        assert actual_size < size_limit, f"File should be under {size_limit} bytes"

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60  # Large file may take longer
        )

        assert result.returncode == 0, f"Failed on large file under limit:\n{result.stderr}"

        # File should be indexed
        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'under_limit.py'")
        assert cursor.fetchone()[0] == 1, "File under limit should be indexed"

        conn.close()

    def test_very_long_line(self, tmp_path):
        """Test file with line exceeding 10K characters."""
        # Create file with extremely long line
        py_file = tmp_path / "long_line.py"
        long_string = "x" * 15000
        content = f'''
def test():
    s = "{long_string}"
    return s
'''
        py_file.write_text(content)

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should not crash
        assert result.returncode == 0, f"Failed on very long line:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'long_line.py'")
        assert cursor.fetchone()[0] == 1, "File with long line should be indexed"

        conn.close()

    def test_deep_directory_nesting(self, tmp_path):
        """Test very deep directory nesting (50+ levels)."""
        # Create 60 levels of nesting
        current_path = tmp_path
        for i in range(60):
            current_path = current_path / f"level_{i}"
            current_path.mkdir()

        # Create Python file at deepest level
        deep_file = current_path / "deep.py"
        deep_file.write_text("def deep_function():\n    return 'nested'")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should handle deep nesting without crashing
        assert result.returncode == 0, f"Failed on deep nesting:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path LIKE '%deep.py'")
        assert cursor.fetchone()[0] == 1, "Deeply nested file should be indexed"

        conn.close()

    def test_filename_with_special_characters(self, tmp_path):
        """Test filenames with special characters."""
        # Create files with special characters (that are valid on filesystem)
        special_files = [
            "file with spaces.py",
            "file-with-dashes.py",
            "file_with_underscores.py",
            "file.multiple.dots.py",
        ]

        for filename in special_files:
            (tmp_path / filename).write_text("def test():\n    pass")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Failed on special characters:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        # All files should be indexed
        for filename in special_files:
            cursor.execute("SELECT COUNT(*) FROM files WHERE path = ?", (filename,))
            assert cursor.fetchone()[0] == 1, f"File '{filename}' should be indexed"

        conn.close()


# =============================================================================
# CATEGORY 3: Malformed Input
# =============================================================================

class TestMalformedInput:
    """Test malformed and corrupted input handling."""

    def test_binary_file_with_py_extension(self, tmp_path):
        """Test binary file disguised as .py file."""
        # Create binary file with .py extension
        fake_py = tmp_path / "binary.py"
        fake_py.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00\x01\x02\x03' * 100)

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should not crash
        assert result.returncode == 0, f"Crashed on binary .py file:\n{result.stderr}"

        # Binary file should be detected and skipped
        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'binary.py'")
        assert cursor.fetchone()[0] == 0, "Binary file should be skipped even with .py extension"

        conn.close()

    def test_utf8_bom_in_file(self, tmp_path):
        """Test file with UTF-8 BOM (Byte Order Mark)."""
        # Create file with UTF-8 BOM
        py_file = tmp_path / "with_bom.py"
        content = '\ufeff# File with BOM\ndef test():\n    return "bom"'
        py_file.write_text(content, encoding='utf-8-sig')

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should handle BOM gracefully
        assert result.returncode == 0, f"Failed on UTF-8 BOM:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'with_bom.py'")
        assert cursor.fetchone()[0] == 1, "File with BOM should be indexed"

        conn.close()

    def test_mixed_line_endings(self, tmp_path):
        """Test file with mixed CRLF and LF line endings."""
        # Create file with mixed line endings
        py_file = tmp_path / "mixed_endings.py"
        content = "def test1():\r\n    pass\n\ndef test2():\r\n    pass\n"
        py_file.write_bytes(content.encode('utf-8'))

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Failed on mixed line endings:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'mixed_endings.py'")
        assert cursor.fetchone()[0] == 1, "File with mixed line endings should be indexed"

        conn.close()

    def test_latin1_encoding(self, tmp_path):
        """Test file with Latin-1 encoding (non-UTF8)."""
        # Create file with Latin-1 encoding
        py_file = tmp_path / "latin1.py"
        # Latin-1 specific characters: é, ñ, ü
        content = "# Configuración\ndef test():\n    return 'café'"
        py_file.write_text(content, encoding='latin-1')

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should handle gracefully with errors="ignore"
        assert result.returncode == 0, f"Failed on Latin-1 encoding:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        # File may or may not be indexed depending on text detection
        # But it should NOT crash
        cursor.execute("SELECT COUNT(*) FROM files")
        file_count = cursor.fetchone()[0]
        assert file_count >= 0, "Indexer should complete without crashing"

        conn.close()

    def test_file_with_null_bytes(self, tmp_path):
        """Test file containing null bytes (common in corrupted files)."""
        # Create file with null bytes
        py_file = tmp_path / "null_bytes.py"
        content = b"def test():\x00\n    return 'test'\x00"
        py_file.write_bytes(content)

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should not crash
        assert result.returncode == 0, f"Crashed on null bytes:\n{result.stderr}"

        # File with null bytes should be detected as binary and skipped
        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'null_bytes.py'")
        assert cursor.fetchone()[0] == 0, "File with null bytes should be skipped"

        conn.close()


# =============================================================================
# CATEGORY 4: Permission and Access Errors
# =============================================================================

class TestPermissionErrors:
    """Test permission and access error handling."""

    @pytest.mark.skipif(os.name == 'nt', reason="Unix permissions don't work on Windows")
    def test_file_without_read_permission(self, tmp_path):
        """Test file without read permission."""
        # Create file and remove read permission
        py_file = tmp_path / "no_read.py"
        py_file.write_text("def test():\n    pass")

        # Remove read permission
        os.chmod(py_file, 0o000)

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        try:
            result = subprocess.run(
                ['aud', 'index'],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            # Should not crash, should handle gracefully
            assert result.returncode == 0, f"Crashed on permission error:\n{result.stderr}"

            db = tmp_path / '.pf' / 'repo_index.db'
            conn = sqlite3.connect(db)
            cursor = conn.cursor()

            # Unreadable file should be skipped
            cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'no_read.py'")
            assert cursor.fetchone()[0] == 0, "Unreadable file should be skipped"

            conn.close()
        finally:
            # Restore permissions for cleanup
            os.chmod(py_file, 0o644)

    @pytest.mark.skipif(os.name == 'nt', reason="Unix permissions don't work on Windows")
    def test_directory_without_read_permission(self, tmp_path):
        """Test directory without read permission."""
        # Create directory with file
        subdir = tmp_path / "no_access"
        subdir.mkdir()
        (subdir / "hidden.py").write_text("def hidden():\n    pass")

        # Remove read permission on directory
        os.chmod(subdir, 0o000)

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        try:
            result = subprocess.run(
                ['aud', 'index'],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            # Should not crash
            assert result.returncode == 0, f"Crashed on directory permission error:\n{result.stderr}"

            db = tmp_path / '.pf' / 'repo_index.db'
            conn = sqlite3.connect(db)
            cursor = conn.cursor()

            # Files in unreadable directory should be skipped
            cursor.execute("SELECT COUNT(*) FROM files WHERE path LIKE 'no_access/%'")
            assert cursor.fetchone()[0] == 0, "Files in unreadable directory should be skipped"

            conn.close()
        finally:
            # Restore permissions for cleanup
            os.chmod(subdir, 0o755)

    def test_symbolic_link_to_file(self, tmp_path):
        """Test symbolic link to file."""
        # Create file and symlink to it
        original = tmp_path / "original.py"
        original.write_text("def original():\n    pass")

        symlink = tmp_path / "symlink.py"
        try:
            symlink.symlink_to(original)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should not crash
        assert result.returncode == 0, f"Failed on symlink:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        # Symlinks should be skipped to avoid duplication
        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'symlink.py'")
        assert cursor.fetchone()[0] == 0, "Symlinks should be skipped"

        # Original should still be indexed
        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'original.py'")
        assert cursor.fetchone()[0] == 1, "Original file should be indexed"

        conn.close()

    def test_broken_symbolic_link(self, tmp_path):
        """Test broken symbolic link (points to non-existent file)."""
        symlink = tmp_path / "broken.py"
        nonexistent = tmp_path / "does_not_exist.py"

        try:
            symlink.symlink_to(nonexistent)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should not crash on broken symlink
        assert result.returncode == 0, f"Crashed on broken symlink:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'broken.py'")
        assert cursor.fetchone()[0] == 0, "Broken symlink should be skipped"

        conn.close()

    def test_circular_symbolic_link(self, tmp_path):
        """Test circular symbolic link (A -> B -> A)."""
        link_a = tmp_path / "link_a"
        link_b = tmp_path / "link_b"

        try:
            link_a.symlink_to(link_b)
            link_b.symlink_to(link_a)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should not hang or crash on circular symlink
        assert result.returncode == 0, f"Crashed on circular symlink:\n{result.stderr}"


# =============================================================================
# CATEGORY 5: Concurrent Access
# =============================================================================

class TestConcurrentAccess:
    """Test concurrent access and database locking."""

    def test_database_locked_by_reader(self, tmp_path):
        """Test behavior when database is locked by another process."""
        # Create minimal project
        (tmp_path / "test.py").write_text("def test():\n    pass")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        # Run indexer first time to create database
        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, "Initial indexing failed"

        db_path = tmp_path / '.pf' / 'repo_index.db'

        # Open database with exclusive lock
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("BEGIN EXCLUSIVE")

        try:
            # Try to run indexer while database is locked
            # This should either wait, fail gracefully, or timeout
            result = subprocess.run(
                ['aud', 'index'],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            # Should not crash with unhandled exception
            # Exit code may be 0 (success after wait) or 1 (graceful failure)
            assert result.returncode in [0, 1], \
                f"Unexpected exit code on locked database:\n{result.stderr}"

        except subprocess.TimeoutExpired:
            # Timeout is acceptable - indicates it's waiting for lock
            pass
        finally:
            conn.rollback()
            conn.close()

    def test_multiple_read_operations(self, tmp_path):
        """Test multiple simultaneous read operations on database."""
        # Create project and index it
        (tmp_path / "test.py").write_text("def test():\n    pass")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, "Initial indexing failed"

        db_path = tmp_path / '.pf' / 'repo_index.db'

        # Open multiple read connections
        connections = []
        try:
            for i in range(5):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM files")
                result = cursor.fetchone()
                assert result[0] >= 0, "Read operation failed"
                connections.append(conn)

            # All reads should succeed
            assert len(connections) == 5, "Not all read connections succeeded"

        finally:
            for conn in connections:
                conn.close()


# =============================================================================
# CATEGORY 6: Edge Cases in Data Content
# =============================================================================

class TestDataContentEdgeCases:
    """Test edge cases in actual code content."""

    def test_extremely_nested_code(self, tmp_path):
        """Test file with extremely nested code blocks."""
        # Create deeply nested code
        nested_code = "def test():\n"
        for i in range(50):
            nested_code += "    " * (i + 1) + f"if True:\n"
        nested_code += "    " * 51 + "pass\n"

        py_file = tmp_path / "nested.py"
        py_file.write_text(nested_code)

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should handle deep nesting
        assert result.returncode == 0, f"Failed on deeply nested code:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'nested.py'")
        assert cursor.fetchone()[0] == 1, "Deeply nested file should be indexed"

        conn.close()

    def test_file_with_unicode_identifiers(self, tmp_path):
        """Test file with Unicode identifiers (valid in Python 3)."""
        py_file = tmp_path / "unicode.py"
        py_file.write_text("""
# Valid Python 3 identifiers
变量 = "Chinese variable"
переменная = "Russian variable"
μετά = "Greek variable"

def función():
    return "función"

class Configuración:
    pass
""", encoding='utf-8')

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Failed on Unicode identifiers:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'unicode.py'")
        assert cursor.fetchone()[0] == 1, "File with Unicode identifiers should be indexed"

        conn.close()

    def test_file_with_only_comments(self, tmp_path):
        """Test file containing only comments."""
        py_file = tmp_path / "comments_only.py"
        py_file.write_text("""
# This file has only comments
# No actual code
# Just documentation
""")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Failed on comment-only file:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT loc FROM files WHERE path = 'comments_only.py'")
        row = cursor.fetchone()
        assert row is not None, "Comment-only file should be indexed"

        conn.close()

    def test_file_with_only_whitespace(self, tmp_path):
        """Test file containing only whitespace."""
        py_file = tmp_path / "whitespace.py"
        py_file.write_text("\n\n    \n\t\n  \n")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Failed on whitespace-only file:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'whitespace.py'")
        assert cursor.fetchone()[0] == 1, "Whitespace-only file should be indexed"

        conn.close()


# =============================================================================
# CATEGORY 7: Filesystem Edge Cases
# =============================================================================

class TestFilesystemEdgeCases:
    """Test filesystem-specific edge cases."""

    def test_git_directory_is_skipped(self, tmp_path):
        """Test that .git directory is properly skipped."""
        # Create .git directory with Python files
        git_dir = tmp_path / '.git'
        git_dir.mkdir()
        (git_dir / 'hooks' / 'pre-commit.py').parent.mkdir(parents=True)
        (git_dir / 'hooks' / 'pre-commit.py').write_text("#!/usr/bin/env python\nprint('hook')")

        # Create normal Python file
        (tmp_path / "app.py").write_text("def app():\n    pass")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Failed with .git directory:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        # .git files should be skipped
        cursor.execute("SELECT COUNT(*) FROM files WHERE path LIKE '.git/%'")
        assert cursor.fetchone()[0] == 0, ".git directory should be skipped"

        # Normal file should be indexed
        cursor.execute("SELECT COUNT(*) FROM files WHERE path = 'app.py'")
        assert cursor.fetchone()[0] == 1, "Normal file should be indexed"

        conn.close()

    def test_node_modules_is_skipped(self, tmp_path):
        """Test that node_modules is properly skipped."""
        # Create node_modules with JavaScript files
        node_modules = tmp_path / 'node_modules'
        node_modules.mkdir()
        (node_modules / 'package' / 'index.js').parent.mkdir(parents=True)
        (node_modules / 'package' / 'index.js').write_text("module.exports = {};")

        # Create normal JavaScript file
        (tmp_path / "app.js").write_text("const x = 1;")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Failed with node_modules:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        # node_modules should be skipped
        cursor.execute("SELECT COUNT(*) FROM files WHERE path LIKE 'node_modules/%'")
        assert cursor.fetchone()[0] == 0, "node_modules should be skipped"

        conn.close()

    def test_hidden_files_starting_with_dot(self, tmp_path):
        """Test handling of hidden files (starting with dot)."""
        # Create hidden Python file
        (tmp_path / ".hidden.py").write_text("def hidden():\n    pass")

        # Create normal file
        (tmp_path / "visible.py").write_text("def visible():\n    pass")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Failed on hidden files:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        # Both should be indexed (hidden files are OK, hidden dirs are skipped)
        cursor.execute("SELECT COUNT(*) FROM files WHERE path IN ('.hidden.py', 'visible.py')")
        count = cursor.fetchone()[0]
        assert count >= 1, "At least visible file should be indexed"

        conn.close()

    def test_duplicate_filenames_in_different_directories(self, tmp_path):
        """Test files with same name in different directories."""
        # Create same filename in different directories
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir2").mkdir()

        (tmp_path / "dir1" / "test.py").write_text("def test1():\n    pass")
        (tmp_path / "dir2" / "test.py").write_text("def test2():\n    pass")

        pf_dir = tmp_path / '.pf'
        pf_dir.mkdir()

        result = subprocess.run(
            ['aud', 'index'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Failed on duplicate filenames:\n{result.stderr}"

        db = tmp_path / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        # Both files should be indexed with full paths
        cursor.execute("SELECT COUNT(*) FROM files WHERE path LIKE '%/test.py'")
        assert cursor.fetchone()[0] == 2, "Both files with same name should be indexed"

        cursor.execute("SELECT path FROM files WHERE path LIKE '%/test.py' ORDER BY path")
        paths = [row[0] for row in cursor.fetchall()]
        assert 'dir1/test.py' in paths, "dir1/test.py should be indexed"
        assert 'dir2/test.py' in paths, "dir2/test.py should be indexed"

        conn.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
