//! Data models for the calorie tracker.
//!
//! This module contains all the core data structures used throughout
//! the application: Food, Meal, User, and related types.

mod food;
mod meal;
mod user;

pub use food::{Food, NutritionInfo, FoodCategory};
pub use meal::{Meal, MealType, MealEntry};
pub use user::{User, DailyGoal, DailySummary, UserPreferences};

use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Trait for entities that have a unique identifier
pub trait Identifiable {
    /// Get the unique identifier
    fn id(&self) -> Uuid;

    /// Check if this is a new (unsaved) entity
    fn is_new(&self) -> bool {
        // Convention: all-zero UUID indicates new entity
        self.id() == Uuid::nil()
    }
}

/// Trait for entities that track creation/update timestamps
pub trait Timestamped {
    /// Get the creation timestamp
    fn created_at(&self) -> chrono::DateTime<chrono::Utc>;

    /// Get the last update timestamp
    fn updated_at(&self) -> chrono::DateTime<chrono::Utc>;
}

/// Marker trait for entities that support soft deletion
pub trait SoftDeletable {
    /// Check if this entity is deleted
    fn is_deleted(&self) -> bool;

    /// Mark as deleted (does not persist - call save after)
    fn mark_deleted(&mut self);
}

/// Generic wrapper for paginated results
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Page<T> {
    /// Items in this page
    pub items: Vec<T>,
    /// Total number of items across all pages
    pub total: usize,
    /// Current page number (0-indexed)
    pub page: usize,
    /// Items per page
    pub page_size: usize,
}

impl<T> Page<T> {
    /// Create a new page of results
    pub fn new(items: Vec<T>, total: usize, page: usize, page_size: usize) -> Self {
        Self { items, total, page, page_size }
    }

    /// Check if there are more pages
    pub fn has_next(&self) -> bool {
        (self.page + 1) * self.page_size < self.total
    }

    /// Check if there is a previous page
    pub fn has_prev(&self) -> bool {
        self.page > 0
    }

    /// Get total number of pages
    pub fn total_pages(&self) -> usize {
        if self.page_size == 0 {
            0
        } else {
            (self.total + self.page_size - 1) / self.page_size
        }
    }

    /// Map items to a different type
    pub fn map<U, F>(self, f: F) -> Page<U>
    where
        F: FnMut(T) -> U,
    {
        Page {
            items: self.items.into_iter().map(f).collect(),
            total: self.total,
            page: self.page,
            page_size: self.page_size,
        }
    }
}

/// Sorting direction
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SortOrder {
    Asc,
    Desc,
}

impl Default for SortOrder {
    fn default() -> Self {
        Self::Asc
    }
}

/// Common sorting options
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SortOptions {
    /// Field to sort by
    pub field: String,
    /// Sort direction
    #[serde(default)]
    pub order: SortOrder,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_page_has_next() {
        let page: Page<i32> = Page::new(vec![1, 2, 3], 10, 0, 3);
        assert!(page.has_next());

        let last_page: Page<i32> = Page::new(vec![10], 10, 3, 3);
        assert!(!last_page.has_next());
    }

    #[test]
    fn test_page_total_pages() {
        let page: Page<i32> = Page::new(vec![], 10, 0, 3);
        assert_eq!(page.total_pages(), 4); // ceil(10/3) = 4
    }

    #[test]
    fn test_page_map() {
        let page = Page::new(vec![1, 2, 3], 3, 0, 10);
        let doubled = page.map(|x| x * 2);
        assert_eq!(doubled.items, vec![2, 4, 6]);
    }
}
