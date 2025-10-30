"""
Deep Nesting and Inheritance Fixture (Python)

Tests extraction of:
- 3+ level class inheritance chains (parent-of-parent resolution)
- 3+ level nested classes (children-of-children symbols)
- Method Resolution Order (MRO) validation
- Inherited methods and attributes
- super() calls across multiple levels

Validates that symbol extraction correctly handles:
- symbols table: Nested class paths (Outer.Middle.Inner.DeepNested)
- parent_class column: Multi-level inheritance resolution
- Method inheritance visibility
"""

# ==============================================================================
# Deep Inheritance Chains (3+ levels)
# ==============================================================================

class BaseModel:
    """
    Root class of inheritance hierarchy.
    Tests: Base class extraction with no parent.
    """
    id = None

    def save(self):
        """Base save method."""
        return f"Saving {self.__class__.__name__}"

    def validate(self):
        """Base validation."""
        return True

    @classmethod
    def from_dict(cls, data):
        """Factory method."""
        return cls()


class TimestampedModel(BaseModel):
    """
    Level 1 inheritance: Extends BaseModel.
    Tests: Parent-child relationship resolution.
    """
    created_at = None
    updated_at = None

    def save(self):
        """Override save with timestamp logic."""
        self.updated_at = "now"
        return super().save()

    def get_age(self):
        """New method introduced at this level."""
        return "age calculation"


class SoftDeletableModel(TimestampedModel):
    """
    Level 2 inheritance: Extends TimestampedModel (which extends BaseModel).
    Tests: Parent-of-parent resolution (BaseModel -> TimestampedModel -> SoftDeletableModel).
    """
    deleted_at = None
    is_deleted = False

    def save(self):
        """Override save with soft-delete logic."""
        if self.is_deleted:
            self.deleted_at = "now"
        return super().save()

    def soft_delete(self):
        """Soft delete instead of hard delete."""
        self.is_deleted = True
        return self.save()

    def restore(self):
        """Restore soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None


class User(SoftDeletableModel):
    """
    Level 3 inheritance: 3 levels deep (BaseModel -> TimestampedModel -> SoftDeletableModel -> User).
    Tests: Deep inheritance chain resolution - User inherits methods from all ancestors.
    """
    username = None
    email = None
    password_hash = None

    def save(self):
        """Override save with user-specific validation."""
        if not self.validate_email():
            raise ValueError("Invalid email")
        return super().save()

    def validate(self):
        """Override base validation with user rules."""
        if not self.username or not self.email:
            return False
        return super().validate()

    def validate_email(self):
        """User-specific validation method."""
        return "@" in (self.email or "")

    def get_display_name(self):
        """New method at User level."""
        return self.username


# ==============================================================================
# Even Deeper Inheritance (4+ levels)
# ==============================================================================

class AdminUser(User):
    """
    Level 4 inheritance: 4 levels deep.
    Tests: Extreme depth - AdminUser inherits from 4 ancestors.
    """
    admin_level = None
    permissions = []

    def save(self):
        """Override save with admin logging."""
        result = super().save()
        self.log_admin_action("save")
        return result

    def log_admin_action(self, action):
        """Admin-specific method."""
        return f"Admin action: {action}"

    def grant_permission(self, permission):
        """Grant admin permission."""
        if permission not in self.permissions:
            self.permissions.append(permission)


class SuperAdminUser(AdminUser):
    """
    Level 5 inheritance: 5 levels deep!
    Tests: EXTREME depth - SuperAdminUser inherits from 5 ancestors.
    """
    can_delete_users = True

    def save(self):
        """Super admin save with extra logging."""
        print(f"SuperAdmin {self.username} saving")
        return super().save()

    def delete_user(self, user):
        """Super admin privilege."""
        if self.can_delete_users:
            user.soft_delete()


# ==============================================================================
# Multiple Inheritance (Diamond Problem)
# ==============================================================================

class Loggable:
    """Mixin for logging functionality."""

    def log(self, message):
        """Log a message."""
        return f"LOG: {message}"


class Cacheable:
    """Mixin for caching functionality."""

    def cache_key(self):
        """Generate cache key."""
        return f"cache:{self.__class__.__name__}"

    def invalidate_cache(self):
        """Invalidate cache."""
        return "cache invalidated"


class AuditableModel(BaseModel, Loggable, Cacheable):
    """
    Multiple inheritance: Inherits from BaseModel + 2 mixins.
    Tests: Multiple parent resolution (Diamond problem handling).
    """
    audit_log = []

    def save(self):
        """Save with audit logging and cache invalidation."""
        self.log(f"Saving {self.__class__.__name__}")
        self.invalidate_cache()
        return super().save()


class AuditedUser(AuditableModel, TimestampedModel):
    """
    Diamond inheritance: Both parents inherit from BaseModel.
    Tests: MRO (Method Resolution Order) - which parent's methods are called first.
    """
    username = None

    def save(self):
        """Save with full audit trail."""
        self.log(f"User {self.username} save started")
        result = super().save()
        self.log(f"User {self.username} save completed")
        return result


# ==============================================================================
# Deeply Nested Classes (3+ levels)
# ==============================================================================

class OuterClass:
    """
    Outer class - Level 0.
    Tests: Root of nested class hierarchy.
    """
    outer_attribute = "outer"

    def outer_method(self):
        """Method on outer class."""
        return "outer method"

    class MiddleClass:
        """
        Middle nested class - Level 1.
        Tests: First level of nesting.
        Symbol path should be: OuterClass.MiddleClass
        """
        middle_attribute = "middle"

        def middle_method(self):
            """Method on middle class."""
            return "middle method"

        class InnerClass:
            """
            Inner nested class - Level 2.
            Tests: Second level of nesting.
            Symbol path should be: OuterClass.MiddleClass.InnerClass
            """
            inner_attribute = "inner"

            def inner_method(self):
                """Method on inner class."""
                return "inner method"

            class DeepNested:
                """
                Deep nested class - Level 3.
                Tests: THIRD level of nesting (children-of-children resolution).
                Symbol path should be: OuterClass.MiddleClass.InnerClass.DeepNested
                """
                deep_attribute = "deep"

                def deep_method(self):
                    """Method on deeply nested class."""
                    return "deep method"

                def access_ancestors(self):
                    """Access attributes from ancestor nested classes."""
                    # This tests that nested class can reference outer classes
                    outer = OuterClass()
                    middle = OuterClass.MiddleClass()
                    inner = OuterClass.MiddleClass.InnerClass()
                    return (outer, middle, inner)


# ==============================================================================
# Nested Classes With Inheritance
# ==============================================================================

class Container:
    """Container class with nested hierarchy."""

    class BaseHandler:
        """Nested base class."""
        def handle(self):
            return "base handling"

    class MiddleHandler(BaseHandler):
        """Nested class inheriting from nested parent."""
        def handle(self):
            return f"{super().handle()} + middle"

    class AdvancedHandler(MiddleHandler):
        """
        Nested class with 2-level inheritance (within nested hierarchy).
        Tests: Inheritance within nested classes.
        """
        def handle(self):
            return f"{super().handle()} + advanced"


# ==============================================================================
# Generic Base Classes
# ==============================================================================

class Repository:
    """Generic repository base."""
    model_class = None

    def find_by_id(self, id):
        """Find entity by ID."""
        return f"Finding {self.model_class.__name__} by ID {id}"

    def find_all(self):
        """Find all entities."""
        return f"Finding all {self.model_class.__name__}"


class UserRepository(Repository):
    """User repository extending generic base."""
    model_class = User

    def find_by_username(self, username):
        """User-specific finder."""
        return f"Finding user by username: {username}"


class AdminUserRepository(UserRepository):
    """
    Admin user repository - 2 levels of inheritance.
    Tests: Repository pattern inheritance.
    """
    model_class = AdminUser

    def find_admins_with_level(self, level):
        """Admin-specific query."""
        return f"Finding admins with level {level}"


# ==============================================================================
# Abstract Method Patterns
# ==============================================================================

class AbstractService:
    """Abstract service base."""

    def execute(self):
        """Template method."""
        self.validate_input()
        result = self.perform()
        self.cleanup()
        return result

    def validate_input(self):
        """Hook method - to be overridden."""
        pass

    def perform(self):
        """Abstract method - must be implemented by subclasses."""
        raise NotImplementedError("Subclass must implement perform()")

    def cleanup(self):
        """Hook method - to be overridden."""
        pass


class UserService(AbstractService):
    """Concrete service implementing abstract methods."""

    def validate_input(self):
        """Override validation."""
        return "validating user input"

    def perform(self):
        """Implement abstract perform method."""
        return "performing user operation"

    def cleanup(self):
        """Override cleanup."""
        return "cleaning up user resources"


class EnhancedUserService(UserService):
    """
    Extended service - 2 levels deep from abstract base.
    Tests: Method override chain validation.
    """

    def perform(self):
        """Enhanced implementation."""
        base_result = super().perform()
        return f"{base_result} with enhancements"


# ==============================================================================
# Metaclass Inheritance
# ==============================================================================

class ModelMeta(type):
    """Metaclass for models."""

    def __new__(cls, name, bases, attrs):
        """Customize class creation."""
        attrs['_meta'] = {'class_name': name}
        return super().__new__(cls, name, bases, attrs)


class MetaModel(metaclass=ModelMeta):
    """Base model using metaclass."""

    def get_meta(self):
        """Access metaclass-injected attribute."""
        return self._meta


class MetaUser(MetaModel):
    """
    User model with metaclass inheritance.
    Tests: Metaclass inheritance extraction.
    """
    username = None

    def get_info(self):
        """Get user info including meta."""
        return f"User {self.username}, meta: {self.get_meta()}"
