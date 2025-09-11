"""Memory management utilities for TheAuditor.

This module provides intelligent memory limit detection based on system resources.
Philosophy: SAST tools need RAM. If you're running complex analysis, allocate accordingly.
"""

import os
import platform
import sys


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
    env_limit = os.environ.get('THEAUDITOR_MEMORY_LIMIT_MB')
    if env_limit:
        try:
            limit = int(env_limit)
            # Sanity check but respect user choice
            if limit < 1000:
                print(f"[WARNING] Memory limit {limit}MB is very low, performance will suffer", file=sys.stderr)
            return limit
        except ValueError:
            print(f"[WARNING] Invalid THEAUDITOR_MEMORY_LIMIT_MB value: {env_limit}", file=sys.stderr)
    
    # Try to detect system RAM
    try:
        if platform.system() == 'Windows':
            # Windows memory detection via ctypes
            import ctypes
            
            class MEMORYSTATUSEX(ctypes.Structure):
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
        print(f"[WARNING] Could not detect system RAM: {e}", file=sys.stderr)
        print("[INFO] Using fallback memory limit of 12GB", file=sys.stderr)
        return 12000  # 12GB fallback for modern systems
    
    # Use 60% of total RAM - SAST needs resources, deal with it
    # This is for serious code analysis, not toy projects
    recommended = int(total_mb * 0.60)
    
    # Minimum 2GB (below this, cache is useless)
    # Maximum 48GB (beyond this, you're probably doing something wrong)
    final_limit = max(2000, min(48000, recommended))
    
    # Log the decision
    print(f"[MEMORY] System RAM: {total_mb}MB, Using: {final_limit}MB (60% of total)", file=sys.stderr)
    
    return final_limit


def get_available_memory() -> int:
    """Get currently available system memory in MB.
    
    Returns:
        Available memory in MB, or -1 if cannot detect
    """
    try:
        if platform.system() == 'Windows':
            import ctypes
            
            class MEMORYSTATUSEX(ctypes.Structure):
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