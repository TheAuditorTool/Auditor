"""Rust-specific security and safety rules.

Rules in this module:
- ffi_boundary: FFI boundary security (raw pointers, variadic functions)
- integer_safety: Integer overflow/underflow detection
- memory_safety: Memory safety issues (use-after-free, buffer overflows)
- panic_paths: Panic-inducing patterns (unwrap, panic!, assert)
- rust_injection_analyze: Command/SQL injection in Rust
- unsafe_analysis: Unsafe block analysis
"""
