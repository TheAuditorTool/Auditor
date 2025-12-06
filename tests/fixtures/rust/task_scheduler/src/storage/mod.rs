//! Storage module - job persistence backends
//!
//! This module defines the `Storage` trait and provides implementations:
//! - `JsonStorage`: JSON file storage
//! - `MemoryStorage`: In-memory storage for testing

mod json;

pub use json::{JsonStorage, MemoryStorage};

use crate::job::Job;
use crate::Result;

/// Trait for job storage backends
///
/// Implementations must be thread-safe (Send + Sync).
///
/// # Example Implementation
///
/// ```rust
/// use task_scheduler::{Result, Job};
/// use task_scheduler::storage::Storage;
///
/// struct MyStorage {
///     // ...
/// }
///
/// impl Storage for MyStorage {
///     fn load(&self) -> Result<Vec<Job>> {
///         // Load jobs from custom backend
///         Ok(vec![])
///     }
///
///     fn save(&self, jobs: &[&Job]) -> Result<()> {
///         // Save jobs to custom backend
///         Ok(())
///     }
///
///     fn clear(&self) -> Result<()> {
///         // Clear all jobs
///         Ok(())
///     }
/// }
/// ```
pub trait Storage: Send + Sync {
    /// Load all jobs from storage
    fn load(&self) -> Result<Vec<Job>>;

    /// Save jobs to storage (replaces all existing)
    fn save(&self, jobs: &[&Job]) -> Result<()>;

    /// Clear all jobs from storage
    fn clear(&self) -> Result<()>;

    /// Load a single job by ID (default implementation)
    fn load_one(&self, id: crate::job::JobId) -> Result<Option<Job>> {
        let jobs = self.load()?;
        Ok(jobs.into_iter().find(|j| j.id() == id))
    }

    /// Delete a single job by ID (default implementation)
    fn delete(&self, id: crate::job::JobId) -> Result<bool> {
        let jobs = self.load()?;
        let (remaining, removed): (Vec<_>, Vec<_>) = jobs
            .into_iter()
            .partition(|j| j.id() != id);

        if removed.is_empty() {
            return Ok(false);
        }

        let refs: Vec<&Job> = remaining.iter().collect();
        self.save(&refs)?;
        Ok(true)
    }

    /// Count jobs (default implementation)
    fn count(&self) -> Result<usize> {
        Ok(self.load()?.len())
    }

    /// Check if storage is empty (default implementation)
    fn is_empty(&self) -> Result<bool> {
        Ok(self.count()? == 0)
    }
}

/// Wrapper to add caching to any storage backend
pub struct CachedStorage<S: Storage> {
    inner: S,
    cache: std::sync::RwLock<Option<Vec<Job>>>,
}

impl<S: Storage> CachedStorage<S> {
    /// Create a new cached storage wrapper
    pub fn new(inner: S) -> Self {
        Self {
            inner,
            cache: std::sync::RwLock::new(None),
        }
    }

    /// Invalidate the cache
    pub fn invalidate(&self) {
        *self.cache.write().unwrap() = None;
    }

    /// Get inner storage reference
    pub fn inner(&self) -> &S {
        &self.inner
    }
}

impl<S: Storage> Storage for CachedStorage<S> {
    fn load(&self) -> Result<Vec<Job>> {
        // Check cache first
        if let Some(ref cached) = *self.cache.read().unwrap() {
            return Ok(cached.clone());
        }

        // Load from inner storage
        let jobs = self.inner.load()?;

        // Update cache
        *self.cache.write().unwrap() = Some(jobs.clone());

        Ok(jobs)
    }

    fn save(&self, jobs: &[&Job]) -> Result<()> {
        self.inner.save(jobs)?;

        // Update cache
        let owned: Vec<Job> = jobs.iter().map(|j| (*j).clone()).collect();
        *self.cache.write().unwrap() = Some(owned);

        Ok(())
    }

    fn clear(&self) -> Result<()> {
        self.inner.clear()?;
        self.invalidate();
        Ok(())
    }
}

/// Wrapper to add logging to any storage backend
pub struct LoggingStorage<S: Storage> {
    inner: S,
    prefix: String,
}

impl<S: Storage> LoggingStorage<S> {
    /// Create a new logging storage wrapper
    pub fn new(inner: S) -> Self {
        Self {
            inner,
            prefix: "[STORAGE]".to_string(),
        }
    }

    /// Set log prefix
    pub fn with_prefix(mut self, prefix: impl Into<String>) -> Self {
        self.prefix = prefix.into();
        self
    }
}

impl<S: Storage> Storage for LoggingStorage<S> {
    fn load(&self) -> Result<Vec<Job>> {
        println!("{} Loading jobs...", self.prefix);
        let result = self.inner.load();
        match &result {
            Ok(jobs) => println!("{} Loaded {} jobs", self.prefix, jobs.len()),
            Err(e) => println!("{} Load failed: {}", self.prefix, e),
        }
        result
    }

    fn save(&self, jobs: &[&Job]) -> Result<()> {
        println!("{} Saving {} jobs...", self.prefix, jobs.len());
        let result = self.inner.save(jobs);
        match &result {
            Ok(()) => println!("{} Save successful", self.prefix),
            Err(e) => println!("{} Save failed: {}", self.prefix, e),
        }
        result
    }

    fn clear(&self) -> Result<()> {
        println!("{} Clearing storage...", self.prefix);
        let result = self.inner.clear();
        match &result {
            Ok(()) => println!("{} Clear successful", self.prefix),
            Err(e) => println!("{} Clear failed: {}", self.prefix, e),
        }
        result
    }
}

/// Null storage that does nothing (for testing)
#[derive(Debug, Default, Clone, Copy)]
pub struct NullStorage;

impl NullStorage {
    pub fn new() -> Self {
        Self
    }
}

impl Storage for NullStorage {
    fn load(&self) -> Result<Vec<Job>> {
        Ok(Vec::new())
    }

    fn save(&self, _jobs: &[&Job]) -> Result<()> {
        Ok(())
    }

    fn clear(&self) -> Result<()> {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_null_storage() {
        let storage = NullStorage::new();

        assert!(storage.load().unwrap().is_empty());
        assert!(storage.save(&[]).is_ok());
        assert!(storage.clear().is_ok());
    }

    #[test]
    fn test_cached_storage() {
        let inner = MemoryStorage::new();
        let cached = CachedStorage::new(inner);

        let job = Job::builder()
            .name("cached-job")
            .manual()
            .build()
            .unwrap();

        cached.save(&[&job]).unwrap();

        // Should come from cache
        let loaded = cached.load().unwrap();
        assert_eq!(loaded.len(), 1);

        // Invalidate and reload
        cached.invalidate();
        let reloaded = cached.load().unwrap();
        assert_eq!(reloaded.len(), 1);
    }

    #[test]
    fn test_storage_default_methods() {
        let storage = MemoryStorage::new();

        let job = Job::builder()
            .name("default-method-test")
            .manual()
            .build()
            .unwrap();

        let id = job.id();
        storage.save(&[&job]).unwrap();

        // Test load_one
        let loaded = storage.load_one(id).unwrap();
        assert!(loaded.is_some());
        assert_eq!(loaded.unwrap().name(), "default-method-test");

        // Test count
        assert_eq!(storage.count().unwrap(), 1);

        // Test is_empty
        assert!(!storage.is_empty().unwrap());

        // Test delete
        assert!(storage.delete(id).unwrap());
        assert!(storage.is_empty().unwrap());
    }
}
