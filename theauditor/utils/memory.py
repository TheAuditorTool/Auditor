"""Memory management utilities for TheAuditor."""

import os
import platform

from theauditor.utils.logging import logger

from .constants import (
    DEFAULT_MEMORY_LIMIT_MB,
    ENV_MEMORY_LIMIT,
    MAX_MEMORY_LIMIT_MB,
    MEMORY_ALLOCATION_RATIO,
    MIN_MEMORY_LIMIT_MB,
)

_SYSTEM = platform.system()

if _SYSTEM == "Windows":
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
    MEMORYSTATUSEX = None
    ctypes = None


def _get_total_memory_windows() -> int:
    """Get total memory on Windows using ctypes."""
    memory_status = MEMORYSTATUSEX()
    memory_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status))
    return memory_status.ullTotalPhys // (1024 * 1024)


def _get_total_memory_linux() -> int:
    """Get total memory on Linux from /proc/meminfo."""
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemTotal:"):
                kb = int(line.split()[1])
                return kb // 1024
    raise RuntimeError("MemTotal not found in /proc/meminfo")


def _get_total_memory_darwin() -> int:
    """Get total memory on macOS using sysctl."""
    import subprocess

    result = subprocess.run(
        ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=True
    )
    bytes_total = int(result.stdout.strip())
    return bytes_total // (1024 * 1024)


def _get_available_memory_windows() -> int:
    """Get available memory on Windows using ctypes."""
    memory_status = MEMORYSTATUSEX()
    memory_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status))
    return memory_status.ullAvailPhys // (1024 * 1024)


def _get_available_memory_linux() -> int:
    """Get available memory on Linux from /proc/meminfo."""
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                kb = int(line.split()[1])
                return kb // 1024
    raise RuntimeError("MemAvailable not found in /proc/meminfo")


def get_recommended_memory_limit() -> int:
    """Get recommended memory limit based on system RAM."""
    env_limit = os.environ.get(ENV_MEMORY_LIMIT)
    if env_limit:
        try:
            limit = int(env_limit)
            if limit < 1000:
                logger.warning(f"Memory limit {limit}MB is very low, performance will suffer")
            return limit
        except ValueError:
            logger.warning(f"Invalid {ENV_MEMORY_LIMIT} value: {env_limit}")

    total_mb = None
    try:
        if _SYSTEM == "Windows":
            total_mb = _get_total_memory_windows()
        elif _SYSTEM == "Linux":
            total_mb = _get_total_memory_linux()
        elif _SYSTEM == "Darwin":
            total_mb = _get_total_memory_darwin()
        else:
            logger.warning(f"Unsupported platform: {_SYSTEM}")
    except Exception as e:
        logger.warning(f"Could not detect system RAM: {e}")

    if not total_mb:
        logger.info(f"Using default memory limit of {DEFAULT_MEMORY_LIMIT_MB}MB")
        return DEFAULT_MEMORY_LIMIT_MB

    recommended = int(total_mb * MEMORY_ALLOCATION_RATIO)
    final_limit = max(MIN_MEMORY_LIMIT_MB, min(MAX_MEMORY_LIMIT_MB, recommended))

    logger.info(
        f"System RAM: {total_mb}MB, Using: {final_limit}MB ({int(MEMORY_ALLOCATION_RATIO * 100)}% of total)"
    )

    return final_limit


def get_available_memory() -> int:
    """Get currently available system memory in MB.

    Returns:
        Available memory in MB, or -1 if platform is unsupported (macOS).

    Raises:
        RuntimeError: If memory detection fails on supported platform.
    """
    if _SYSTEM == "Windows":
        return _get_available_memory_windows()
    elif _SYSTEM == "Linux":
        return _get_available_memory_linux()
    return -1
