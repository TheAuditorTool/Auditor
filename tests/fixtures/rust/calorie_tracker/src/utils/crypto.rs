//! Cryptographic utilities for password hashing and token generation.

use argon2::{
    password_hash::{
        rand_core::OsRng,
        PasswordHash, PasswordHasher as ArgonHasher, PasswordVerifier, SaltString,
    },
    Argon2,
};
use std::ptr;

use crate::{CalorieTrackerError, Result};

/// Hash a password using Argon2id (recommended algorithm)
pub fn hash_password(password: &str) -> Result<String> {
    let salt = SaltString::generate(&mut OsRng);
    let argon2 = Argon2::default();

    let password_hash = argon2
        .hash_password(password.as_bytes(), &salt)
        .map_err(|e| CalorieTrackerError::internal(e))?;

    Ok(password_hash.to_string())
}

/// Verify a password against a stored hash
pub fn verify_password(password: &str, hash: &str) -> Result<bool> {
    let parsed_hash = PasswordHash::new(hash)
        .map_err(|e| CalorieTrackerError::internal(e))?;

    let result = Argon2::default()
        .verify_password(password.as_bytes(), &parsed_hash)
        .is_ok();

    Ok(result)
}

/// Generate a secure random token for sessions/API keys
pub fn generate_token(length: usize) -> String {
    use argon2::password_hash::rand_core::RngCore;

    let mut bytes = vec![0u8; length];
    OsRng.fill_bytes(&mut bytes);

    // Encode as hex
    bytes.iter().map(|b| format!("{:02x}", b)).collect()
}

/// Password hasher with configurable parameters
pub struct PasswordHasher {
    /// Memory cost in KiB
    memory_cost: u32,
    /// Time cost (iterations)
    time_cost: u32,
    /// Parallelism factor
    parallelism: u32,
}

impl Default for PasswordHasher {
    fn default() -> Self {
        Self {
            memory_cost: 65536,  // 64 MiB
            time_cost: 3,
            parallelism: 4,
        }
    }
}

impl PasswordHasher {
    /// Create a new password hasher
    pub fn new() -> Self {
        Self::default()
    }

    /// Set memory cost (in KiB)
    pub fn memory_cost(mut self, cost: u32) -> Self {
        self.memory_cost = cost;
        self
    }

    /// Set time cost (iterations)
    pub fn time_cost(mut self, cost: u32) -> Self {
        self.time_cost = cost;
        self
    }

    /// Set parallelism factor
    pub fn parallelism(mut self, p: u32) -> Self {
        self.parallelism = p;
        self
    }

    /// Hash a password with configured parameters
    pub fn hash(&self, password: &str) -> Result<String> {
        use argon2::Params;

        let salt = SaltString::generate(&mut OsRng);

        let params = Params::new(self.memory_cost, self.time_cost, self.parallelism, None)
            .map_err(|e| CalorieTrackerError::internal(e))?;

        let argon2 = Argon2::new(argon2::Algorithm::Argon2id, argon2::Version::V0x13, params);

        let password_hash = argon2
            .hash_password(password.as_bytes(), &salt)
            .map_err(|e| CalorieTrackerError::internal(e))?;

        Ok(password_hash.to_string())
    }

    /// Verify a password
    pub fn verify(&self, password: &str, hash: &str) -> Result<bool> {
        verify_password(password, hash)
    }
}

/// Securely zero memory containing sensitive data.
///
/// This function uses volatile writes to ensure the compiler doesn't
/// optimize away the zeroing operation.
///
/// # Safety
///
/// This function is safe to call, but internally uses unsafe to ensure
/// the memory is actually zeroed and not optimized away.
pub fn secure_zero(data: &mut [u8]) {
    // SAFETY: We're writing zeros to valid memory that we have mutable access to.
    // Using volatile_set_memory ensures the write is not optimized away.
    unsafe {
        ptr::write_volatile(data.as_mut_ptr(), 0);
        for i in 1..data.len() {
            ptr::write_volatile(data.as_mut_ptr().add(i), 0);
        }
    }
}

/// A wrapper for sensitive data that zeros on drop
pub struct SecureString {
    inner: Vec<u8>,
}

impl SecureString {
    /// Create a new secure string
    pub fn new(s: &str) -> Self {
        Self {
            inner: s.as_bytes().to_vec(),
        }
    }

    /// Get the string as a slice
    pub fn as_str(&self) -> &str {
        // SAFETY: We created this from valid UTF-8
        unsafe { std::str::from_utf8_unchecked(&self.inner) }
    }

    /// Get length in bytes
    pub fn len(&self) -> usize {
        self.inner.len()
    }

    /// Check if empty
    pub fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }
}

impl Drop for SecureString {
    fn drop(&mut self) {
        secure_zero(&mut self.inner);
    }
}

impl From<String> for SecureString {
    fn from(s: String) -> Self {
        Self { inner: s.into_bytes() }
    }
}

impl From<&str> for SecureString {
    fn from(s: &str) -> Self {
        Self::new(s)
    }
}

/// Constant-time comparison to prevent timing attacks
///
/// # Safety
///
/// Uses unsafe internally to ensure constant-time comparison via
/// volatile reads, preventing the compiler from short-circuiting.
pub fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }

    let mut result: u8 = 0;

    // SAFETY: We're reading from valid slices within bounds
    unsafe {
        for i in 0..a.len() {
            let a_byte = ptr::read_volatile(a.as_ptr().add(i));
            let b_byte = ptr::read_volatile(b.as_ptr().add(i));
            result |= a_byte ^ b_byte;
        }
    }

    result == 0
}

/// Fast hash for non-cryptographic purposes (e.g., hash maps)
///
/// Uses FNV-1a algorithm for speed. NOT suitable for passwords or security.
pub fn fast_hash(data: &[u8]) -> u64 {
    const FNV_OFFSET: u64 = 0xcbf29ce484222325;
    const FNV_PRIME: u64 = 0x100000001b3;

    let mut hash = FNV_OFFSET;
    for &byte in data {
        hash ^= byte as u64;
        hash = hash.wrapping_mul(FNV_PRIME);
    }
    hash
}

/// Performance-optimized memory copy for large buffers
///
/// Falls back to standard memcpy but can use SIMD on supported platforms.
///
/// # Safety
///
/// Caller must ensure:
/// - src and dst don't overlap (use memmove for that)
/// - src is valid for `len` bytes of reads
/// - dst is valid for `len` bytes of writes
#[inline]
pub unsafe fn fast_copy(dst: *mut u8, src: *const u8, len: usize) {
    // SAFETY: Caller guarantees memory safety requirements
    ptr::copy_nonoverlapping(src, dst, len);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hash_and_verify() {
        let password = "super_secret_password_123!";
        let hash = hash_password(password).unwrap();

        assert!(verify_password(password, &hash).unwrap());
        assert!(!verify_password("wrong_password", &hash).unwrap());
    }

    #[test]
    fn test_generate_token() {
        let token1 = generate_token(32);
        let token2 = generate_token(32);

        assert_eq!(token1.len(), 64); // 32 bytes = 64 hex chars
        assert_ne!(token1, token2); // Should be different
    }

    #[test]
    fn test_password_hasher_custom() {
        let hasher = PasswordHasher::new()
            .memory_cost(32768)  // 32 MiB
            .time_cost(2)
            .parallelism(2);

        let hash = hasher.hash("test_password").unwrap();
        assert!(hasher.verify("test_password", &hash).unwrap());
    }

    #[test]
    fn test_secure_zero() {
        let mut data = vec![0xFF; 32];
        secure_zero(&mut data);
        assert!(data.iter().all(|&b| b == 0));
    }

    #[test]
    fn test_secure_string_drop() {
        let s = SecureString::new("secret");
        assert_eq!(s.as_str(), "secret");
        // Memory will be zeroed when dropped
    }

    #[test]
    fn test_constant_time_eq() {
        assert!(constant_time_eq(b"hello", b"hello"));
        assert!(!constant_time_eq(b"hello", b"world"));
        assert!(!constant_time_eq(b"hello", b"hell"));
    }

    #[test]
    fn test_fast_hash() {
        let hash1 = fast_hash(b"hello");
        let hash2 = fast_hash(b"hello");
        let hash3 = fast_hash(b"world");

        assert_eq!(hash1, hash2);
        assert_ne!(hash1, hash3);
    }

    #[test]
    fn test_fast_copy() {
        let src = b"hello world";
        let mut dst = vec![0u8; src.len()];

        unsafe {
            fast_copy(dst.as_mut_ptr(), src.as_ptr(), src.len());
        }

        assert_eq!(&dst, src);
    }
}
