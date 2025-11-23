"""Tests for CodeSnippetManager."""

import pytest
from pathlib import Path
from theauditor.utils.code_snippets import CodeSnippetManager


@pytest.fixture
def snippet_manager(tmp_path):
    """Create snippet manager with test files."""
    # Create test Python file
    test_py = tmp_path / "test.py"
    test_py.write_text("""def foo():
    x = 1
    if x > 0:
        return x
    return 0

class Bar:
    def method(self):
        pass
""")

    # Create test TypeScript file
    test_ts = tmp_path / "test.ts"
    test_ts.write_text("""function greet(name: string): string {
    return `Hello, ${name}`;
}

export class UserService {
    getUser(id: number) {
        return this.db.find(id);
    }
}
""")

    return CodeSnippetManager(tmp_path)


def test_get_snippet_simple_line(snippet_manager, tmp_path):
    """Test getting a single line without expansion."""
    snippet = snippet_manager.get_snippet("test.py", 1, expand_block=False)
    assert "def foo():" in snippet
    assert "1 |" in snippet


def test_get_snippet_block_expansion(snippet_manager, tmp_path):
    """Test block expansion based on indentation."""
    snippet = snippet_manager.get_snippet("test.py", 3, expand_block=True)
    assert "if x > 0:" in snippet
    assert "return x" in snippet


def test_get_snippet_typescript(snippet_manager, tmp_path):
    """Test TypeScript file support."""
    snippet = snippet_manager.get_snippet("test.ts", 1, expand_block=True)
    assert "function greet" in snippet
    assert "return" in snippet


def test_missing_file(snippet_manager):
    """Test handling of non-existent files."""
    snippet = snippet_manager.get_snippet("nonexistent.py", 1)
    assert "[File not found" in snippet


def test_line_out_of_range(snippet_manager):
    """Test handling of line number beyond file length."""
    snippet = snippet_manager.get_snippet("test.py", 999)
    assert "out of range" in snippet


def test_cache_reuse(snippet_manager, tmp_path):
    """Test that cache is used for subsequent accesses."""
    # Access same file twice
    snippet_manager.get_snippet("test.py", 1)
    snippet_manager.get_snippet("test.py", 2)
    # Should only have one entry in cache
    assert len(snippet_manager._cache) == 1


def test_cache_eviction(tmp_path):
    """Test LRU cache eviction when capacity exceeded."""
    manager = CodeSnippetManager(tmp_path)
    manager.MAX_CACHE_SIZE = 2  # Override for test

    # Create 3 files
    for i in range(3):
        (tmp_path / f"file{i}.py").write_text(f"# File {i}")

    # Access all 3 files
    manager.get_snippet("file0.py", 1)
    manager.get_snippet("file1.py", 1)
    manager.get_snippet("file2.py", 1)

    # Only 2 should be in cache (oldest evicted)
    assert len(manager._cache) == 2
    assert "file0.py" not in manager._cache  # Oldest evicted


def test_get_lines_range(snippet_manager):
    """Test getting specific range of lines."""
    snippet = snippet_manager.get_lines("test.py", 1, 3)
    assert "def foo():" in snippet
    assert "x = 1" in snippet
    assert "if x > 0:" in snippet


def test_cache_stats(snippet_manager):
    """Test cache statistics."""
    snippet_manager.get_snippet("test.py", 1)
    stats = snippet_manager.cache_stats()

    assert stats['cached_files'] == 1
    assert "test.py" in stats['files']


def test_clear_cache(snippet_manager):
    """Test cache clearing."""
    snippet_manager.get_snippet("test.py", 1)
    assert len(snippet_manager._cache) == 1

    snippet_manager.clear_cache()
    assert len(snippet_manager._cache) == 0
