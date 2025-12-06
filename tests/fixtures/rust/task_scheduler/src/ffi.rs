//! FFI bindings and unsafe operations
//!
//! This module tests extraction of:
//! - extern blocks
//! - extern functions
//! - unsafe blocks
//! - unsafe traits
//! - raw pointer operations

use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int, c_void};
use std::ptr;

// ============================================================================
// EXTERN BLOCKS - Tests rust_extern_blocks extraction
// ============================================================================

extern "C" {
    /// Get environment variable (libc)
    fn getenv(name: *const c_char) -> *const c_char;

    /// Set environment variable
    fn setenv(name: *const c_char, value: *const c_char, overwrite: c_int) -> c_int;

    /// Allocate memory
    fn malloc(size: usize) -> *mut c_void;

    /// Free memory
    fn free(ptr: *mut c_void);

    /// Copy memory
    fn memcpy(dest: *mut c_void, src: *const c_void, n: usize) -> *mut c_void;
}

// Windows-specific extern block
#[cfg(windows)]
extern "system" {
    fn GetLastError() -> u32;
    fn SetLastError(code: u32);
}

// ============================================================================
// UNSAFE TRAITS - Tests rust_unsafe_traits extraction
// ============================================================================

/// Marker trait for types that can be safely sent across FFI boundary
///
/// # Safety
/// Implementors must ensure the type has a stable ABI representation
pub unsafe trait FfiSafe: Sized {
    /// Get the size in bytes for FFI
    fn ffi_size() -> usize {
        std::mem::size_of::<Self>()
    }
}

/// Marker for types that can be zeroed safely
///
/// # Safety
/// All-zero bit pattern must be valid for the type
pub unsafe trait Zeroable: Sized {
    fn zeroed() -> Self {
        // Safety: Implementor guarantees all-zeros is valid
        unsafe { std::mem::zeroed() }
    }
}

// Unsafe trait implementations
unsafe impl FfiSafe for i32 {}
unsafe impl FfiSafe for u32 {}
unsafe impl FfiSafe for f64 {}
unsafe impl Zeroable for i32 {}
unsafe impl Zeroable for u32 {}

/// Combined trait requiring both FFI safety and zeroability
pub unsafe trait FfiPrimitive: FfiSafe + Zeroable {}

unsafe impl FfiPrimitive for i32 {}
unsafe impl FfiPrimitive for u32 {}

// ============================================================================
// UNSAFE BLOCKS - Tests rust_unsafe_blocks extraction
// ============================================================================

/// Get an environment variable safely
///
/// # Safety
/// Uses unsafe FFI call but wraps it safely
pub fn get_env_var(name: &str) -> Option<String> {
    let c_name = CString::new(name).ok()?;

    // SAFETY: getenv is thread-safe for reading, c_name is valid C string
    let ptr = unsafe { getenv(c_name.as_ptr()) };

    if ptr.is_null() {
        return None;
    }

    // SAFETY: We checked for null, getenv returns valid C string
    let c_str = unsafe { CStr::from_ptr(ptr) };

    c_str.to_str().ok().map(|s| s.to_string())
}

/// Set an environment variable
///
/// # Safety
/// Modifies process environment (not thread-safe in general)
pub fn set_env_var(name: &str, value: &str) -> Result<(), &'static str> {
    let c_name = CString::new(name).map_err(|_| "invalid name")?;
    let c_value = CString::new(value).map_err(|_| "invalid value")?;

    // SAFETY: Both strings are valid, overwrite=1 means replace existing
    let result = unsafe { setenv(c_name.as_ptr(), c_value.as_ptr(), 1) };

    if result == 0 {
        Ok(())
    } else {
        Err("setenv failed")
    }
}

/// Raw buffer for FFI operations
pub struct RawBuffer {
    ptr: *mut u8,
    len: usize,
    capacity: usize,
}

impl RawBuffer {
    /// Allocate a new raw buffer
    ///
    /// # Safety
    /// Uses malloc - must be freed with drop or free()
    pub fn new(capacity: usize) -> Option<Self> {
        if capacity == 0 {
            return None;
        }

        // SAFETY: malloc with non-zero size returns valid pointer or null
        let ptr = unsafe { malloc(capacity) as *mut u8 };

        if ptr.is_null() {
            return None;
        }

        Some(Self {
            ptr,
            len: 0,
            capacity,
        })
    }

    /// Write bytes to buffer
    ///
    /// # Safety
    /// Caller must ensure data fits within capacity
    pub unsafe fn write_unchecked(&mut self, data: &[u8]) {
        // SAFETY: Caller guarantees data.len() <= self.capacity - self.len
        memcpy(
            self.ptr.add(self.len) as *mut c_void,
            data.as_ptr() as *const c_void,
            data.len(),
        );
        self.len += data.len();
    }

    /// Write bytes with bounds checking
    pub fn write(&mut self, data: &[u8]) -> Result<(), &'static str> {
        if self.len + data.len() > self.capacity {
            return Err("buffer overflow");
        }

        // SAFETY: We just checked bounds
        unsafe {
            self.write_unchecked(data);
        }

        Ok(())
    }

    /// Get buffer contents as slice
    pub fn as_slice(&self) -> &[u8] {
        if self.ptr.is_null() || self.len == 0 {
            return &[];
        }

        // SAFETY: ptr is valid, len is within allocation
        unsafe { std::slice::from_raw_parts(self.ptr, self.len) }
    }

    /// Get raw pointer (for FFI)
    pub fn as_ptr(&self) -> *const u8 {
        self.ptr
    }

    /// Get mutable raw pointer (for FFI)
    pub fn as_mut_ptr(&mut self) -> *mut u8 {
        self.ptr
    }

    /// Clear buffer (reset len to 0)
    pub fn clear(&mut self) {
        self.len = 0;
    }

    /// Current length
    pub fn len(&self) -> usize {
        self.len
    }

    /// Is buffer empty
    pub fn is_empty(&self) -> bool {
        self.len == 0
    }
}

impl Drop for RawBuffer {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            // SAFETY: ptr was allocated with malloc
            unsafe {
                free(self.ptr as *mut c_void);
            }
            self.ptr = ptr::null_mut();
        }
    }
}

// Note: RawBuffer is NOT Send or Sync because it contains raw pointers.
// Rust automatically prevents this - no explicit impl needed.
// The raw pointer field (*mut u8) makes it !Send and !Sync by default.

// ============================================================================
// POINTER ARITHMETIC - More unsafe patterns
// ============================================================================

/// Demonstrates various unsafe pointer operations
pub mod raw_ops {
    use std::ptr;

    /// Swap two values via raw pointers
    ///
    /// # Safety
    /// Both pointers must be valid and properly aligned
    pub unsafe fn ptr_swap<T>(a: *mut T, b: *mut T) {
        ptr::swap(a, b);
    }

    /// Read a value from raw pointer
    ///
    /// # Safety
    /// Pointer must be valid and properly aligned
    pub unsafe fn ptr_read<T: Copy>(ptr: *const T) -> T {
        ptr::read(ptr)
    }

    /// Write a value to raw pointer
    ///
    /// # Safety
    /// Pointer must be valid and properly aligned
    pub unsafe fn ptr_write<T>(ptr: *mut T, value: T) {
        ptr::write(ptr, value);
    }

    /// Offset a pointer by n elements
    ///
    /// # Safety
    /// Result must be within same allocation
    pub unsafe fn ptr_offset<T>(ptr: *const T, n: isize) -> *const T {
        ptr.offset(n)
    }

    /// Cast between pointer types (transmute-like)
    ///
    /// # Safety
    /// Types must have compatible layouts
    pub unsafe fn ptr_cast<T, U>(ptr: *const T) -> *const U {
        ptr as *const U
    }
}

// ============================================================================
// INLINE ASSEMBLY (placeholder - actual asm requires nightly)
// ============================================================================

/// CPU feature detection via inline assembly
#[cfg(all(target_arch = "x86_64", feature = "asm"))]
pub mod cpu_features {
    /// Check if CPU supports AVX2
    pub fn has_avx2() -> bool {
        // Would use core::arch::asm! on nightly
        false
    }
}

// ============================================================================
// UNION TYPES - Another unsafe pattern
// ============================================================================

/// Union for reinterpreting bytes as different types
#[repr(C)]
pub union ByteRepr {
    pub bytes: [u8; 8],
    pub int64: i64,
    pub uint64: u64,
    pub float64: f64,
}

impl ByteRepr {
    /// Create from bytes
    pub fn from_bytes(bytes: [u8; 8]) -> Self {
        Self { bytes }
    }

    /// Get as i64 (unsafe - must know actual type)
    ///
    /// # Safety
    /// Only valid if union was created with i64 value
    pub unsafe fn as_i64(&self) -> i64 {
        self.int64
    }

    /// Get as f64 (unsafe - must know actual type)
    ///
    /// # Safety
    /// Only valid if union was created with f64 value
    pub unsafe fn as_f64(&self) -> f64 {
        self.float64
    }

    /// Reinterpret i64 as f64 (bit cast)
    pub fn i64_to_f64_bits(val: i64) -> f64 {
        let repr = Self { int64: val };
        // SAFETY: This is intentional bit reinterpretation
        unsafe { repr.float64 }
    }
}

// ============================================================================
// STATIC MUTS - Global mutable state (unsafe)
// ============================================================================

/// Global counter (unsafe to access)
static mut GLOBAL_COUNTER: u64 = 0;

/// Increment global counter
///
/// # Safety
/// Not thread-safe - must be called from single thread only
pub unsafe fn increment_counter() -> u64 {
    GLOBAL_COUNTER += 1;
    GLOBAL_COUNTER
}

/// Get global counter value
///
/// # Safety
/// Not thread-safe - must synchronize externally
pub unsafe fn get_counter() -> u64 {
    GLOBAL_COUNTER
}

/// Reset global counter
///
/// # Safety
/// Not thread-safe
pub unsafe fn reset_counter() {
    GLOBAL_COUNTER = 0;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_raw_buffer() {
        let mut buf = RawBuffer::new(64).unwrap();
        buf.write(b"hello").unwrap();
        buf.write(b" world").unwrap();

        assert_eq!(buf.as_slice(), b"hello world");
        assert_eq!(buf.len(), 11);
    }

    #[test]
    fn test_byte_repr() {
        let val: i64 = 0x4048000000000000; // 48.0 in IEEE 754
        let f = ByteRepr::i64_to_f64_bits(val);
        assert_eq!(f, 48.0);
    }

    #[test]
    fn test_ffi_safe_size() {
        assert_eq!(<i32 as FfiSafe>::ffi_size(), 4);
        assert_eq!(<f64 as FfiSafe>::ffi_size(), 8);
    }

    #[test]
    fn test_zeroable() {
        let z: i32 = Zeroable::zeroed();
        assert_eq!(z, 0);
    }
}
