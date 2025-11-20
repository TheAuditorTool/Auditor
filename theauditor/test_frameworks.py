"""Test framework detection for various languages."""
from __future__ import annotations


import fnmatch
import json
import os
import re
from pathlib import Path
from typing import Any
from collections.abc import Iterable
from theauditor.manifest_parser import ManifestParser
from theauditor.framework_registry import TEST_FRAMEWORK_REGISTRY

# Directories to ignore when scanning for test files/imports (sandbox, vendor, caches)
IGNORED_DIRECTORIES: set[str] = {
    ".auditor_venv",
    ".auditor_tmp",
    ".pf",
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
}


def _iter_matching_files(
    root: Path,
    patterns: Iterable[str],
    max_matches: int | None = None,
) -> list[Path]:
    """Return files under root matching patterns, skipping ignored directories."""
    matches: list[Path] = []
    normalized_patterns = tuple(patterns)

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune directories we never want to inspect
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRECTORIES]

        if not normalized_patterns:
            continue

        for filename in filenames:
            file_path = Path(dirpath) / filename
            try:
                rel_path = file_path.relative_to(root).as_posix()
            except ValueError:
                rel_path = file_path.as_posix()

            for pattern in normalized_patterns:
                if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(rel_path, pattern):
                    matches.append(file_path)
                    if max_matches is not None and len(matches) >= max_matches:
                        return matches
                    break

    return matches


def detect_test_framework(root: str | Path) -> dict[str, Any]:
    """Detect the test framework used in a project using unified registry approach.

    Args:
        root: Root directory of the project.

    Returns:
        Dictionary with framework info:
        {
            "name": str,  # pytest, jest, rspec, go, junit, etc.
            "language": str,  # python, javascript, etc.
            "cmd": str,  # Command to run tests
        }
    """
    root = Path(root)
    parser = ManifestParser()
    
    # Parse all relevant manifests once
    manifests = {}
    manifest_files = {
        "pyproject.toml": root / "pyproject.toml",
        "package.json": root / "package.json",
        "requirements.txt": root / "requirements.txt",
        "requirements-dev.txt": root / "requirements-dev.txt",
        "requirements-test.txt": root / "requirements-test.txt",
        "setup.cfg": root / "setup.cfg",
        "setup.py": root / "setup.py",
        "tox.ini": root / "tox.ini",
        "Gemfile": root / "Gemfile",
        "Gemfile.lock": root / "Gemfile.lock",
        "go.mod": root / "go.mod",
        "pom.xml": root / "pom.xml",
        "build.gradle": root / "build.gradle",
        "build.gradle.kts": root / "build.gradle.kts",
    }
    
    for name, path in manifest_files.items():
        if path.exists():
            try:
                if name.endswith('.toml'):
                    manifests[name] = parser.parse_toml(path)
                elif name.endswith('.json'):
                    manifests[name] = parser.parse_json(path)
                elif name.endswith('.cfg') or name.endswith('.ini'):
                    manifests[name] = parser.parse_ini(path)
                elif name.endswith('.txt'):
                    manifests[name] = parser.parse_requirements_txt(path)
                elif name in ['Gemfile', 'Gemfile.lock']:
                    with open(path, encoding='utf-8') as f:
                        manifests[name] = f.read()
                elif name.endswith(('.xml', '.gradle', '.kts', '.mod', '.py')):
                    with open(path, encoding='utf-8') as f:
                        manifests[name] = f.read()
            except Exception:
                # Skip files that can't be parsed
                continue

    python_manifest_present = any(
        key in manifests
        for key in (
            "pyproject.toml",
            "requirements.txt",
            "requirements-dev.txt",
            "requirements-test.txt",
            "setup.cfg",
            "setup.py",
            "tox.ini",
        )
    )
    
    # Check each test framework in priority order
    for tf_name, tf_config in TEST_FRAMEWORK_REGISTRY.items():
        # Check config files first (highest confidence)
        if "config_files" in tf_config:
            for config_file in tf_config["config_files"]:
                if (root / config_file).exists():
                    # Special handling for different test runners
                    cmd = tf_config.get("command", "")
                    # For JUnit, determine build tool
                    if tf_name == "junit":
                        if (root / "pom.xml").exists():
                            cmd = tf_config.get("command_maven", "mvn test")
                        elif (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
                            cmd = tf_config.get("command_gradle", "gradle test")
                    return {
                        "name": tf_name,
                        "language": tf_config["language"],
                        "cmd": cmd
                    }
        
        # Check config sections in manifests
        if "config_sections" in tf_config:
            for manifest_name, section_paths in tf_config.get("config_sections", {}).items():
                if manifest_name in manifests:
                    for section_path in section_paths:
                        section = parser.extract_nested_value(manifests[manifest_name], section_path)
                        if section is not None:
                            return {
                                "name": tf_name,
                                "language": tf_config["language"],
                                "cmd": tf_config.get("command", "")
                            }
        
        # Check dependencies in manifests
        if "detection_sources" in tf_config:
            for manifest_name, search_configs in tf_config["detection_sources"].items():
                if manifest_name not in manifests:
                    continue
                    
                manifest_data = manifests[manifest_name]
                
                if search_configs == "line_search":
                    # Text search for requirements.txt or Gemfile
                    if isinstance(manifest_data, list):
                        for line in manifest_data:
                            if tf_name in line:
                                return {
                                    "name": tf_name,
                                    "language": tf_config["language"],
                                    "cmd": tf_config.get("command", "")
                                }
                    elif isinstance(manifest_data, str) and tf_name in manifest_data:
                        return {
                            "name": tf_name,
                            "language": tf_config["language"],
                            "cmd": tf_config.get("command", "")
                        }
                
                elif search_configs == "content_search":
                    # Content search for text files
                    if isinstance(manifest_data, str):
                        # Check for test framework patterns
                        if tf_config.get("content_patterns"):
                            for pattern in tf_config["content_patterns"]:
                                if pattern in manifest_data:
                                    # Determine command based on build tool
                                    cmd = tf_config.get("command", "")
                                    if tf_name == "junit":
                                        if (root / "pom.xml").exists():
                                            cmd = tf_config.get("command_maven", "mvn test")
                                        elif (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
                                            cmd = tf_config.get("command_gradle", "gradle test")
                                    return {
                                        "name": tf_name,
                                        "language": tf_config["language"],
                                        "cmd": cmd
                                    }
                
                elif search_configs == "exists":
                    # Just check if file exists (for go.mod)
                    return {
                        "name": tf_name,
                        "language": tf_config["language"],
                        "cmd": tf_config.get("command", "")
                    }
                
                else:
                    # Structured search for dependencies
                    for key_path in search_configs:
                        deps = parser.extract_nested_value(manifest_data, key_path)
                        if deps:
                            # Check if test framework is in dependencies
                            version = parser.check_package_in_deps(deps, tf_name)
                            if version:
                                return {
                                    "name": tf_name,
                                    "language": tf_config["language"],
                                    "cmd": tf_config.get("command", "")
                                }
        
        # Check for directory markers
        if "directory_markers" in tf_config:
            for dir_marker in tf_config["directory_markers"]:
                if (root / dir_marker.rstrip('/')).is_dir():
                    return {
                        "name": tf_name,
                        "language": tf_config["language"],
                        "cmd": tf_config.get("command", "")
                    }
        
        # Check for file patterns
        if "file_patterns" in tf_config:
            if tf_config.get("language") == "python" and not python_manifest_present:
                # Defer to import-based detection to avoid false positives from stray files
                pass
            else:
                for pattern in tf_config["file_patterns"]:
                    if _iter_matching_files(root, [pattern], max_matches=1):
                        return {
                            "name": tf_name,
                            "language": tf_config["language"],
                            "cmd": tf_config.get("command", "")
                        }
    
    # Fallback: Check for import patterns in source files (for unittest)
    # This is last resort for frameworks like unittest that don't have manifest entries
    max_files_to_check = 20
    files_checked = 0
    
    for tf_name, tf_config in TEST_FRAMEWORK_REGISTRY.items():
        if "import_patterns" not in tf_config:
            continue
            
        # Find files matching the language
        ext_map = {
            "python": ["*.py"],
            "javascript": ["*.js", "*.jsx", "*.ts", "*.tsx"],
            "java": ["*.java"],
            "go": ["*.go"],
            "ruby": ["*.rb"],
        }
        
        extensions = ext_map.get(tf_config["language"], [])
        for ext in extensions:
            if files_checked >= max_files_to_check:
                break

            remaining = max_files_to_check - files_checked
            candidate_files = _iter_matching_files(root, [ext], max_matches=remaining if remaining > 0 else None)

            for file_path in candidate_files:
                if files_checked >= max_files_to_check:
                    break
                    
                files_checked += 1
                try:
                    with open(file_path, encoding='utf-8', errors='ignore') as f:
                        content = f.read(2000)  # Read first 2000 chars
                        
                    for import_pattern in tf_config["import_patterns"]:
                        if import_pattern in content:
                            return {
                                "name": tf_name,
                                "language": tf_config["language"],
                                "cmd": tf_config.get("command", "")
                            }
                except Exception:
                    continue
    
    # Unknown framework
    return {"name": "unknown", "language": "unknown", "cmd": ""}

# Old detection functions removed - now using unified registry-based detection
