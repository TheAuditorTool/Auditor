"""Authentication and authorization security rules."""

from .jwt_detect import find_jwt_flaws

__all__ = ["find_jwt_flaws"]