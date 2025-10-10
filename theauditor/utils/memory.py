"""Memory management utilities for TheAuditor.

This module provides intelligent memory limit detection based on system resources.
Philosophy: SAST tools need RAM. If you're running complex analysis, allocate accordingly.
"""

import os
import platform
import sys

from .logger import setup_logger
from .constants import (
    DEFAULT_MEMORY_LIMIT_MB,
    MIN_MEMORY_LIMIT_MB,
    MAX_MEMORY_LIMIT_MB,
    MEMORY_ALLOCATION_RATIO,
    ENV_MEMORY_LIMIT,
)

logger = setup_logger(__name__)

# ============================================================================
# WINDOWS MEMORY STATUS STRUCTURE (Module-level to avoid duplication)
# ============================================================================

if platform.system() == 'Windows':
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        """Windows memory status structure for GlobalMemoryStatusEx API."""
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]
else:
    MEMORYSTATUSEX = None  # Not used on non-Windows platforms
    ctypes = None  # Avoid import errors on non-Windows


def get_recommended_memory_limit() -> int:
    """Get recommended memory limit based on system RAM.

    Uses 60% of available RAM because complex SAST analysis needs resources.
    If you're analyzing enterprise codebases, you need enterprise hardware.

    Priority order:
    1. Environment variable THEAUDITOR_MEMORY_LIMIT_MB
    2. Auto-detection (60% of system RAM)
    3. Fallback to 12GB if detection fails

    Returns:
        Memory limit in MB (minimum 2GB, maximum 48GB)
    """
    # Check environment variable first - user knows best
    env_limit = os.environ.get(ENV_MEMORY_LIMIT)
    if env_limit:
        try:
            limit = int(env_limit)
            # Sanity check but respect user choice
            if limit < 1000:
                logger.warning(f"Memory limit {limit}MB is very low, performance will suffer")
            return limit
        except ValueError:
            logger.warning(f"Invalid {ENV_MEMORY_LIMIT} value: {env_limit}")

    # Try to detect system RAM
    try:
        if platform.system() == 'Windows':
            # Windows memory detection via ctypes (using module-level MEMORYSTATUSEX)
            memory_status = MEMORYSTATUSEX()
            memory_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            kernel32 = ctypes.windll.kernel32
            kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status))

            total_mb = memory_status.ullTotalPhys // (1024 * 1024)
            
        else:
            # Linux/Mac - try multiple methods
            total_mb = None
            
            # Method 1: Try psutil if available
            try:
                import psutil
                total_mb = psutil.virtual_memory().total // (1024 * 1024)
            except ImportError:
                pass
            
            # Method 2: Read from /proc/meminfo (Linux)
            if not total_mb and platform.system() == 'Linux':
                try:
                    with open('/proc/meminfo', 'r') as f:
                        for line in f:
                            if line.startswith('MemTotal:'):
                                # MemTotal is in KB
                                kb = int(line.split()[1])
                                total_mb = kb // 1024
                                break
                except Exception:
                    pass
            
            # Method 3: Use sysctl (Mac)
            if not total_mb and platform.system() == 'Darwin':
                try:
                    import subprocess
                    result = subprocess.run(['sysctl', '-n', 'hw.memsize'], 
                                         capture_output=True, text=True)
                    if result.returncode == 0:
                        bytes_total = int(result.stdout.strip())
                        total_mb = bytes_total // (1024 * 1024)
                except Exception:
                    pass
            
            if not total_mb:
                raise Exception("Could not detect system memory")
                
    except Exception as e:
        # Fallback if detection fails - assume modern system
        logger.warning(f"Could not detect system RAM: {e}")
        logger.info(f"Using fallback memory limit of {DEFAULT_MEMORY_LIMIT_MB}MB")
        return DEFAULT_MEMORY_LIMIT_MB

    # Use 60% of total RAM - SAST needs resources, deal with it
    # This is for serious code analysis, not toy projects
    recommended = int(total_mb * MEMORY_ALLOCATION_RATIO)

    # Apply minimum and maximum bounds
    final_limit = max(MIN_MEMORY_LIMIT_MB, min(MAX_MEMORY_LIMIT_MB, recommended))

    # Log the decision
    logger.info(f"System RAM: {total_mb}MB, Using: {final_limit}MB ({int(MEMORY_ALLOCATION_RATIO * 100)}% of total)")

    return final_limit


def get_available_memory() -> int:
    """Get currently available system memory in MB.

    Returns:
        Available memory in MB, or -1 if cannot detect
    """
    try:
        if platform.system() == 'Windows':
            # Windows memory detection via ctypes (using module-level MEMORYSTATUSEX)
            memory_status = MEMORYSTATUSEX()
            memory_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            kernel32 = ctypes.windll.kernel32
            kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status))

            return memory_status.ullAvailPhys // (1024 * 1024)
        else:
            # Try psutil first
            try:
                import psutil
                return psutil.virtual_memory().available // (1024 * 1024)
            except ImportError:
                pass
            
            # Linux fallback
            if platform.system() == 'Linux':
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if line.startswith('MemAvailable:'):
                            kb = int(line.split()[1])
                            return kb // 1024
    except Exception:
        pass
    
    return -1  # Cannot detect