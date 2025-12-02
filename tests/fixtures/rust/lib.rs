//! Rust test fixture for TheAuditor indexing.
//! This file exercises all 20 rust_* table types (Phase 1 + Phase 2).

// ============================================================================
// 1. rust_use_statements - Use declarations
// ============================================================================
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use crate::models::User;
use super::utils::*;

// ============================================================================
// 2. rust_modules - Module declarations
// ============================================================================
mod models;
mod utils;

pub mod api {
    //! Inline module example
    pub fn handle_request() {}
}

// ============================================================================
// 3. rust_structs - Struct definitions
// ============================================================================

/// A named struct with generics
pub struct MyStruct<T> {
    pub field1: String,
    field2: T,
    count: usize,
}

/// A tuple struct
pub struct Point(pub i32, pub i32);

/// A unit struct
pub struct EmptyMarker;

// ============================================================================
// 4. rust_enums - Enum definitions
// ============================================================================

/// Enum with multiple variant types
pub enum Status<T> {
    Pending,
    Active(T),
    Error { code: i32, message: String },
}

/// Simple error enum
#[derive(Debug, Clone)]
pub enum AppError {
    NotFound,
    Unauthorized,
    Internal(String),
}

// ============================================================================
// 5. rust_traits - Trait definitions
// ============================================================================

/// A basic trait with required method
pub trait Processor {
    fn process(&self) -> Result<(), AppError>;
}

/// Trait with supertraits
pub trait AdvancedProcessor: Processor + Clone + Send {
    fn advanced_process(&self) -> i32;
}

/// Unsafe trait
pub unsafe trait UnsafeMarker {
    fn unsafe_method(&self);
}

// ============================================================================
// 6. rust_impl_blocks - Impl blocks
// ============================================================================

impl<T> MyStruct<T> {
    /// Constructor
    pub fn new(field1: String, field2: T) -> Self {
        Self { field1, field2, count: 0 }
    }

    pub fn increment(&mut self) {
        self.count += 1;
    }
}

impl Processor for MyStruct<String> {
    fn process(&self) -> Result<(), AppError> {
        Ok(())
    }
}

unsafe impl UnsafeMarker for EmptyMarker {
    fn unsafe_method(&self) {}
}

// ============================================================================
// 7. rust_functions - Function definitions
// ============================================================================

/// Sync function
pub fn sync_function(x: i32) -> i32 {
    x * 2
}

/// Async function
pub async fn async_function(data: String) -> Result<String, AppError> {
    Ok(data)
}

/// Unsafe function
pub unsafe fn unsafe_function(ptr: *const i32) -> i32 {
    // SAFETY: Caller guarantees ptr is valid
    *ptr
}

/// Const function
pub const fn const_function(x: i32) -> i32 {
    x + 1
}

/// Generic function with where clause
pub fn generic_function<T>(value: T) -> T
where
    T: Clone + Default,
{
    value.clone()
}

/// Main entry point
fn main() {
    let mut s = MyStruct::new("hello".to_string(), 42);
    s.increment();
    println!("Count: {}", s.count);
}

// ============================================================================
// PHASE 2: Advanced Tables
// ============================================================================

// ============================================================================
// 8. rust_macros - Macro definitions
// ============================================================================

macro_rules! my_macro {
    ($x:expr) => {
        println!("{}", $x);
    };
}

// ============================================================================
// 9. rust_macro_invocations - Macro calls
// ============================================================================

fn function_with_macros() {
    println!("Hello, {}!", "world");
    my_macro!(42);
    vec![1, 2, 3];
}

// ============================================================================
// 10. rust_async_functions + 11. rust_await_points
// ============================================================================

pub async fn async_with_awaits() -> Result<String, AppError> {
    let data = fetch_data().await;
    let processed = process_async(data).await;
    Ok(processed)
}

async fn fetch_data() -> String {
    "fetched".to_string()
}

async fn process_async(data: String) -> String {
    data.to_uppercase()
}

// ============================================================================
// 12. rust_unsafe_blocks - Unsafe blocks with SAFETY comments
// ============================================================================

fn function_with_unsafe() {
    let value = 42i32;
    let ptr = &value as *const i32;

    // SAFETY: ptr is valid because value is still in scope
    let deref_value = unsafe { *ptr };

    unsafe {
        // Another unsafe block without SAFETY comment
        let _ = *ptr;
    }
}

// ============================================================================
// 13. rust_extern_blocks + 14. rust_extern_functions
// ============================================================================

extern "C" {
    fn external_c_function(x: i32) -> i32;
    fn variadic_function(fmt: *const i8, ...) -> i32;
}

extern "system" {
    fn windows_api_call(handle: *mut ()) -> i32;
}

// ============================================================================
// 15. rust_generics - Generic parameters with bounds
// ============================================================================

pub struct Container<'a, T: Clone + Send, const N: usize> {
    data: &'a [T; N],
}

// ============================================================================
// 16. rust_lifetimes - Lifetime parameters
// ============================================================================

pub struct RefHolder<'a, 'b> {
    first: &'a str,
    second: &'b str,
}

fn lifetime_function<'a>(input: &'a str) -> &'a str {
    input
}
