"""ORM-specific rule modules for detecting anti-patterns and performance issues."""

from .sequelize_analyze import find_sequelize_issues
from .prisma_analyze import find_prisma_issues
from .typeorm_analyze import find_typeorm_issues

__all__ = ['find_sequelize_issues', 'find_prisma_issues', 'find_typeorm_issues']