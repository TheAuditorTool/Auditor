"""ORM-specific rule modules for detecting anti-patterns and performance issues."""

from .sequelize_detector import find_sequelize_issues
from .prisma_detector import find_prisma_issues

__all__ = ['find_sequelize_issues', 'find_prisma_issues']