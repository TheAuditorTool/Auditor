"""ORM-specific rule modules for detecting anti-patterns and performance issues."""

from .prisma_analyze import analyze as find_prisma_issues
from .sequelize_analyze import analyze as find_sequelize_issues
from .typeorm_analyze import analyze as find_typeorm_issues

__all__ = ["find_sequelize_issues", "find_prisma_issues", "find_typeorm_issues"]
