"""Core functionality for file system operations and AST caching.

This module contains the FileWalker class for directory traversal with monorepo
detection.
"""

import os
import json
import sqlite3
import fnmatch
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional, Set

from theauditor.utils import compute_file_hash, count_lines_in_file
from theauditor.config_runtime import load_runtime_config
from .config import (
    SKIP_DIRS, STANDARD_MONOREPO_PATHS, MONOREPO_ENTRY_FILES
)

# Import ASTCache from the new unified cache module
from ..cache.ast_cache import ASTCache


def is_text_file(file_path: Path) -> bool:
    """Check if file is text (not binary).
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if file is text, False if binary
    """
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
            if b"\0" in chunk:
                return False
            # Try to decode as UTF-8
            try:
                chunk.decode("utf-8")
                return True
            except UnicodeDecodeError:
                return False
    except (FileNotFoundError, PermissionError, UnicodeDecodeError):
        return False


def get_first_lines(file_path: Path, n: int = 2) -> List[str]:
    """Get first n lines of a text file.
    
    Args:
        file_path: Path to the file
        n: Number of lines to read
        
    Returns:
        List of first n lines from the file
    """
    lines = []
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                # Strip \r and truncate at 200 chars
                line = line.replace("\r", "").rstrip("\n")[:200]
                lines.append(line)
    except (FileNotFoundError, PermissionError, UnicodeDecodeError):
        # Gracefully skip unreadable files
        pass
    return lines


def load_gitignore_patterns(root_path: Path) -> Set[str]:
    """Load patterns from .gitignore if it exists.
    
    Args:
        root_path: Project root path
        
    Returns:
        Set of directory patterns to ignore
    """
    gitignore_path = root_path / ".gitignore"
    patterns = set()
    
    if gitignore_path.exists():
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith('#'):
                        # Convert gitignore patterns to simple dir names
                        # This is a simplified approach - just extract directory names
                        pattern = line.rstrip('/')
                        if '/' not in pattern and '*' not in pattern:
                            patterns.add(pattern)
        except Exception:
            pass  # Ignore errors reading .gitignore
    
    return patterns


class FileWalker:
    """Handles directory walking with monorepo detection and filtering."""
    
    def __init__(self, root_path: Path, config: Dict[str, Any], 
                 follow_symlinks: bool = False, exclude_patterns: Optional[List[str]] = None):
        """Initialize the file walker.
        
        Args:
            root_path: Root directory to walk
            config: Runtime configuration
            follow_symlinks: Whether to follow symbolic links
            exclude_patterns: Additional patterns to exclude
        """
        self.root_path = root_path
        self.config = config
        self.follow_symlinks = follow_symlinks
        self.exclude_patterns = exclude_patterns or []
        
        # Load gitignore patterns and combine with default skip dirs
        gitignore_patterns = load_gitignore_patterns(root_path)
        self.skip_dirs = SKIP_DIRS | gitignore_patterns
        
        # Stats tracking
        self.stats = {
            "total_files": 0,
            "text_files": 0,
            "binary_files": 0,
            "large_files": 0,
            "skipped_dirs": 0,
        }
    
    def detect_monorepo(self) -> Tuple[bool, List[Path], List[Path]]:
        """Detect if project is a monorepo and return source directories.
        
        Returns:
            Tuple of (is_monorepo, src_directories, root_entry_files)
        """
        monorepo_dirs = []
        monorepo_detected = False
        
        # Check which monorepo directories exist
        for base_dir, src_dir in STANDARD_MONOREPO_PATHS:
            base_path = self.root_path / base_dir
            if base_path.exists() and base_path.is_dir():
                if src_dir:
                    # Check if src subdirectory exists
                    src_path = base_path / src_dir
                    if src_path.exists() and src_path.is_dir():
                        monorepo_dirs.append(src_path)
                        monorepo_detected = True
                else:
                    # For packages/apps directories, add all subdirectories with src folders
                    for subdir in base_path.iterdir():
                        if subdir.is_dir() and not subdir.name.startswith('.'):
                            src_path = subdir / "src"
                            if src_path.exists() and src_path.is_dir():
                                monorepo_dirs.append(src_path)
                                monorepo_detected = True
        
        # Check for root-level entry files in monorepo
        root_entry_files = []
        if monorepo_detected:
            for entry_file in MONOREPO_ENTRY_FILES:
                entry_path = self.root_path / entry_file
                if entry_path.exists() and entry_path.is_file():
                    root_entry_files.append(entry_path)
        
        return monorepo_detected, monorepo_dirs, root_entry_files
    
    def process_file(self, file: Path, exclude_file_patterns: List[str]) -> Optional[Dict[str, Any]]:
        """Process a single file and return its info.
        
        Args:
            file: Path to the file to process
            exclude_file_patterns: Patterns for files to exclude
            
        Returns:
            File info dictionary or None if file should be skipped
        """
        # Check if file matches any exclude pattern
        if exclude_file_patterns:
            filename = file.name
            relative_path = file.relative_to(self.root_path).as_posix()
            for pattern in exclude_file_patterns:
                # Check both the filename and the full relative path
                if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(relative_path, pattern):
                    return None
        
        # Skip symlinks if not following
        try:
            if not self.follow_symlinks and file.is_symlink():
                return None
        except (OSError, PermissionError):
            # On Windows, is_symlink() can fail on certain paths
            return None
        
        try:
            file_size = file.stat().st_size
            
            # Skip large files
            if file_size >= self.config["limits"]["max_file_size"]:
                self.stats["large_files"] += 1
                return None
            
            # Check if text file
            if not is_text_file(file):
                self.stats["binary_files"] += 1
                return None
            
            self.stats["text_files"] += 1
            
            # Compute metadata
            relative_path = file.relative_to(self.root_path)
            posix_path = relative_path.as_posix()
            
            file_info = {
                "path": posix_path,
                "sha256": compute_file_hash(file),
                "ext": file.suffix,
                "bytes": file_size,
                "loc": count_lines_in_file(file),
                "first_lines": get_first_lines(file),
            }
            
            return file_info
            
        except (FileNotFoundError, PermissionError, UnicodeDecodeError, sqlite3.Error, OSError):
            # Skip files we can't read
            return None
    
    def walk(self) -> Tuple[List[Dict], Dict[str, Any]]:
        """Walk directory and collect file information.
        
        Returns:
            Tuple of (files_list, statistics)
        """
        files = []
        
        # Separate file and directory patterns from exclude_patterns
        exclude_file_patterns = []
        if self.exclude_patterns:
            for pattern in self.exclude_patterns:
                # Directory patterns
                if pattern.endswith('/**'):
                    # Pattern like "theauditor/**" means skip the directory
                    self.skip_dirs.add(pattern.rstrip('/**'))
                elif pattern.endswith('/'):
                    self.skip_dirs.add(pattern.rstrip('/'))
                elif '/' in pattern and '*' not in pattern:
                    # Add the first directory component
                    self.skip_dirs.add(pattern.split('/')[0])
                else:
                    # File pattern (e.g., "*.md", "pyproject.toml")
                    exclude_file_patterns.append(pattern)
        
        # Detect if this is a monorepo
        monorepo_detected, monorepo_dirs, root_entry_files = self.detect_monorepo()
        
        if monorepo_detected:
            print(f"[Indexer] Monorepo detected. Using whitelist for {len(monorepo_dirs)} src directories")
            
            # Process whitelisted directories only
            for src_dir in monorepo_dirs:
                for dirpath, dirnames, filenames in os.walk(src_dir, followlinks=self.follow_symlinks):
                    # Still apply skip_dirs within the whitelisted paths
                    skipped_count = len([d for d in dirnames if d in self.skip_dirs])
                    self.stats["skipped_dirs"] += skipped_count
                    dirnames[:] = [d for d in dirnames if d not in self.skip_dirs]
                    
                    # Process files in this directory
                    for filename in filenames:
                        self.stats["total_files"] += 1
                        file = Path(dirpath) / filename
                        
                        file_info = self.process_file(file, exclude_file_patterns)
                        if file_info:
                            files.append(file_info)
            
            # CRITICAL: Also collect config files from monorepo directories
            # These are outside src/ but essential for module resolution
            config_patterns = ['tsconfig.json', 'tsconfig.*.json', 'package.json',
                             'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
                             'webpack.config.js', 'vite.config.ts', '.babelrc*']
            
            for base_dir, _ in STANDARD_MONOREPO_PATHS:
                base_path = self.root_path / base_dir
                if base_path.exists() and base_path.is_dir():
                    # Look for config files in the base directory (not just src)
                    for pattern in config_patterns:
                        for config_file in base_path.glob(pattern):
                            if config_file.is_file():
                                self.stats["total_files"] += 1
                                file_info = self.process_file(config_file, [])
                                if file_info:
                                    files.append(file_info)
            
            # Also check root directory for configs
            for pattern in config_patterns:
                for config_file in self.root_path.glob(pattern):
                    if config_file.is_file() and config_file not in [f for f in files]:
                        self.stats["total_files"] += 1
                        file_info = self.process_file(config_file, [])
                        if file_info:
                            files.append(file_info)
            
            # Also process root-level entry files
            for entry_file in root_entry_files:
                self.stats["total_files"] += 1
                file_info = self.process_file(entry_file, [])
                if file_info:
                    files.append(file_info)
        
        else:
            # Not a monorepo, use traditional approach
            print("[Indexer] Standard project structure detected. Using traditional scanning.")
            
            for dirpath, dirnames, filenames in os.walk(self.root_path, followlinks=self.follow_symlinks):
                # Count directories that will be skipped
                skipped_count = len([d for d in dirnames if d in self.skip_dirs])
                self.stats["skipped_dirs"] += skipped_count
                
                # Skip ignored directories
                dirnames[:] = [d for d in dirnames if d not in self.skip_dirs]
                
                # On Windows, skip problematic symlink directories in venv
                current_path = Path(dirpath)
                try:
                    if not os.access(dirpath, os.R_OK):
                        continue
                    # Skip known problematic symlinks in virtual environments
                    if any(part in [".venv", "venv", "virtualenv"] for part in current_path.parts):
                        if current_path.name in ["lib64", "bin64", "include64"]:
                            dirnames.clear()
                            continue
                except (OSError, PermissionError):
                    continue
                
                for filename in filenames:
                    self.stats["total_files"] += 1
                    file = Path(dirpath) / filename
                    
                    file_info = self.process_file(file, exclude_file_patterns)
                    if file_info:
                        files.append(file_info)
        
        # Sort by path for deterministic output
        files.sort(key=lambda x: x["path"])
        
        return files, self.stats