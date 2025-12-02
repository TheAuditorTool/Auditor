//! Storage layer for persisting calorie tracker data.
//!
//! This module provides the `Repository` trait defining the storage interface,
//! along with concrete implementations for SQLite.

mod repository;
mod sqlite;

pub use repository::Repository;
pub use sqlite::SqliteRepository;

use crate::Result;

/// Connection pool configuration
#[derive(Debug, Clone)]
pub struct PoolConfig {
    /// Maximum connections in pool
    pub max_connections: u32,
    /// Minimum connections to keep alive
    pub min_connections: u32,
    /// Connection timeout in seconds
    pub connect_timeout_secs: u64,
    /// Idle connection timeout in seconds
    pub idle_timeout_secs: u64,
}

impl Default for PoolConfig {
    fn default() -> Self {
        Self {
            max_connections: 10,
            min_connections: 1,
            connect_timeout_secs: 30,
            idle_timeout_secs: 600,
        }
    }
}

/// Transaction isolation level
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IsolationLevel {
    ReadUncommitted,
    ReadCommitted,
    RepeatableRead,
    Serializable,
}

impl Default for IsolationLevel {
    fn default() -> Self {
        Self::ReadCommitted
    }
}

/// Helper trait for running operations in a transaction
#[async_trait::async_trait]
pub trait Transactional {
    /// Execute a closure within a transaction
    async fn with_transaction<F, T>(&self, f: F) -> Result<T>
    where
        F: FnOnce() -> Result<T> + Send + 'static,
        T: Send + 'static;
}

/// Health check result for storage
#[derive(Debug, Clone)]
pub struct HealthCheck {
    /// Whether storage is healthy
    pub healthy: bool,
    /// Response time in milliseconds
    pub latency_ms: u64,
    /// Connection pool status
    pub pool_size: u32,
    /// Idle connections
    pub idle_connections: u32,
    /// Any error message
    pub error: Option<String>,
}

impl HealthCheck {
    pub fn healthy(latency_ms: u64) -> Self {
        Self {
            healthy: true,
            latency_ms,
            pool_size: 0,
            idle_connections: 0,
            error: None,
        }
    }

    pub fn unhealthy(error: impl Into<String>) -> Self {
        Self {
            healthy: false,
            latency_ms: 0,
            pool_size: 0,
            idle_connections: 0,
            error: Some(error.into()),
        }
    }
}
