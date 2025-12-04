//! JSON file storage implementation
//!
//! Persists jobs to a JSON file with atomic writes.

use super::Storage;
use crate::job::Job;
use crate::{Result, SchedulerError};
use serde::{Deserialize, Serialize};
use std::fs::{self, File};
use std::io::{BufReader, BufWriter};
use std::path::{Path, PathBuf};

/// File format version for migration support
const FILE_VERSION: u32 = 1;

/// JSON file header with metadata
#[derive(Debug, Serialize, Deserialize)]
struct FileHeader {
    /// File format version
    version: u32,
    /// Creation timestamp
    created_at: chrono::DateTime<chrono::Utc>,
    /// Last modified timestamp
    modified_at: chrono::DateTime<chrono::Utc>,
    /// Number of jobs
    job_count: usize,
}

impl FileHeader {
    fn new(job_count: usize) -> Self {
        let now = chrono::Utc::now();
        Self {
            version: FILE_VERSION,
            created_at: now,
            modified_at: now,
            job_count,
        }
    }
}

/// Complete file content
#[derive(Debug, Serialize, Deserialize)]
struct FileContent {
    /// File metadata
    header: FileHeader,
    /// Jobs data
    jobs: Vec<Job>,
}

/// JSON file storage backend
///
/// Stores jobs in a JSON file with atomic writes and backup support.
#[derive(Debug)]
pub struct JsonStorage {
    /// Path to the main storage file
    path: PathBuf,
    /// Path to backup file
    backup_path: PathBuf,
    /// Whether to create backup before writes
    backup_enabled: bool,
    /// Pretty print JSON output
    pretty_print: bool,
}

impl JsonStorage {
    /// Create a new JSON storage
    pub fn new(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref().to_path_buf();
        let backup_path = path.with_extension("json.bak");

        Ok(Self {
            path,
            backup_path,
            backup_enabled: true,
            pretty_print: true,
        })
    }

    /// Create storage with custom options
    pub fn with_options(
        path: impl AsRef<Path>,
        backup_enabled: bool,
        pretty_print: bool,
    ) -> Result<Self> {
        let mut storage = Self::new(path)?;
        storage.backup_enabled = backup_enabled;
        storage.pretty_print = pretty_print;
        Ok(storage)
    }

    /// Get the storage file path
    pub fn path(&self) -> &Path {
        &self.path
    }

    /// Check if storage file exists
    pub fn exists(&self) -> bool {
        self.path.exists()
    }

    /// Get file size in bytes
    pub fn file_size(&self) -> Option<u64> {
        fs::metadata(&self.path).ok().map(|m| m.len())
    }

    /// Create backup of current file
    fn create_backup(&self) -> Result<()> {
        if self.backup_enabled && self.path.exists() {
            fs::copy(&self.path, &self.backup_path).map_err(|e| {
                SchedulerError::StorageError(format!("failed to create backup: {}", e))
            })?;
        }
        Ok(())
    }

    /// Restore from backup
    pub fn restore_backup(&self) -> Result<()> {
        if !self.backup_path.exists() {
            return Err(SchedulerError::StorageError("no backup file found".into()));
        }

        fs::copy(&self.backup_path, &self.path).map_err(|e| {
            SchedulerError::StorageError(format!("failed to restore backup: {}", e))
        })?;

        Ok(())
    }

    /// Delete storage file
    pub fn delete(&self) -> Result<()> {
        if self.path.exists() {
            fs::remove_file(&self.path)?;
        }
        Ok(())
    }

    /// Read file content
    fn read_file(&self) -> Result<FileContent> {
        let file = File::open(&self.path).map_err(|e| {
            SchedulerError::StorageError(format!("failed to open file: {}", e))
        })?;

        let reader = BufReader::new(file);
        let content: FileContent = serde_json::from_reader(reader)?;

        // Check version
        if content.header.version > FILE_VERSION {
            return Err(SchedulerError::StorageError(format!(
                "file version {} is newer than supported version {}",
                content.header.version, FILE_VERSION
            )));
        }

        Ok(content)
    }

    /// Write file content atomically
    fn write_file(&self, content: &FileContent) -> Result<()> {
        // Write to temp file first
        let temp_path = self.path.with_extension("json.tmp");

        {
            let file = File::create(&temp_path).map_err(|e| {
                SchedulerError::StorageError(format!("failed to create temp file: {}", e))
            })?;

            let writer = BufWriter::new(file);

            if self.pretty_print {
                serde_json::to_writer_pretty(writer, content)?;
            } else {
                serde_json::to_writer(writer, content)?;
            }
        }

        // Create backup
        self.create_backup()?;

        // Rename temp to final (atomic on most filesystems)
        fs::rename(&temp_path, &self.path).map_err(|e| {
            SchedulerError::StorageError(format!("failed to finalize write: {}", e))
        })?;

        Ok(())
    }
}

impl Storage for JsonStorage {
    fn load(&self) -> Result<Vec<Job>> {
        if !self.exists() {
            return Ok(Vec::new());
        }

        let content = self.read_file()?;
        Ok(content.jobs)
    }

    fn save(&self, jobs: &[&Job]) -> Result<()> {
        // Ensure parent directory exists
        if let Some(parent) = self.path.parent() {
            if !parent.exists() {
                fs::create_dir_all(parent)?;
            }
        }

        let owned_jobs: Vec<Job> = jobs.iter().map(|j| (*j).clone()).collect();
        let content = FileContent {
            header: FileHeader::new(owned_jobs.len()),
            jobs: owned_jobs,
        };

        self.write_file(&content)
    }

    fn clear(&self) -> Result<()> {
        self.delete()
    }
}

/// In-memory storage for testing
#[derive(Debug, Default)]
pub struct MemoryStorage {
    jobs: std::sync::RwLock<Vec<Job>>,
}

impl MemoryStorage {
    /// Create a new memory storage
    pub fn new() -> Self {
        Self {
            jobs: std::sync::RwLock::new(Vec::new()),
        }
    }

    /// Get number of stored jobs
    pub fn len(&self) -> usize {
        self.jobs.read().unwrap().len()
    }

    /// Check if empty
    pub fn is_empty(&self) -> bool {
        self.jobs.read().unwrap().is_empty()
    }
}

impl Storage for MemoryStorage {
    fn load(&self) -> Result<Vec<Job>> {
        Ok(self.jobs.read().unwrap().clone())
    }

    fn save(&self, jobs: &[&Job]) -> Result<()> {
        let mut storage = self.jobs.write().unwrap();
        storage.clear();
        storage.extend(jobs.iter().map(|j| (*j).clone()));
        Ok(())
    }

    fn clear(&self) -> Result<()> {
        self.jobs.write().unwrap().clear();
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_json_storage_save_load() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("jobs.json");

        let storage = JsonStorage::new(&path).unwrap();

        // Create test job
        let job = Job::builder()
            .name("test-job")
            .manual()
            .build()
            .unwrap();

        // Save
        storage.save(&[&job]).unwrap();
        assert!(storage.exists());

        // Load
        let loaded = storage.load().unwrap();
        assert_eq!(loaded.len(), 1);
        assert_eq!(loaded[0].name(), "test-job");
    }

    #[test]
    fn test_json_storage_empty_load() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("nonexistent.json");

        let storage = JsonStorage::new(&path).unwrap();
        let jobs = storage.load().unwrap();

        assert!(jobs.is_empty());
    }

    #[test]
    fn test_memory_storage() {
        let storage = MemoryStorage::new();

        let job = Job::builder()
            .name("memory-job")
            .manual()
            .build()
            .unwrap();

        storage.save(&[&job]).unwrap();
        assert_eq!(storage.len(), 1);

        let loaded = storage.load().unwrap();
        assert_eq!(loaded[0].name(), "memory-job");

        storage.clear().unwrap();
        assert!(storage.is_empty());
    }
}
