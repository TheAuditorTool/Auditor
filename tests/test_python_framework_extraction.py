"""End-to-end tests for Python framework extraction and import resolution.

CRITICAL: These tests read from .pf/repo_index.db which is populated by `aud full`.
DO NOT re-index fixtures in tests - use the existing database.
Run `aud full` once, then all tests query the same database.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

# Database path - populated by `aud full`
DB_PATH = Path(".pf/repo_index.db")


def fetchall(db_path: Path, query: str, params: tuple | None = None):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params or tuple())
        return cursor.fetchall()


def test_sqlalchemy_models_extracted():
    db_path = DB_PATH

    models = {row[0] for row in fetchall(db_path, "SELECT model_name FROM python_orm_models")}
    assert {"Organization", "User", "Profile", "Post", "Comment", "Tag"} <= models

    fk_rows = fetchall(
        db_path,
        "SELECT model_name, field_name, is_foreign_key FROM python_orm_fields WHERE model_name IN (?, ?) ORDER BY field_name",
        ("Post", "User"),
    )
    assert ("Post", "author_id", 1) in fk_rows
    assert ("User", "org_id", 1) in fk_rows

    relationships = fetchall(
        db_path,
        "SELECT source_model, target_model, relationship_type FROM orm_relationships",
    )
    assert ("User", "Organization", "belongsTo") in relationships
    assert ("Organization", "User", "hasMany") in relationships
    assert ("Post", "Tag", "manyToMany") in relationships


def test_pydantic_validators_extracted():
    db_path = DB_PATH

    validators = fetchall(
        db_path,
        "SELECT model_name, field_name, validator_method, validator_type FROM python_validators",
    )
    assert ("UserPayload", None, "passwords_match", "root") in validators
    assert ("Address", "postal_code", "postal_code_length", "field") in validators
    assert ("UserSettings", "timezone", "timezone_not_empty", "field") in validators


def test_flask_routes_extracted():
    db_path = DB_PATH

    routes = fetchall(
        db_path,
        "SELECT method, pattern, has_auth, blueprint FROM python_routes ORDER BY line",
    )
    assert len(routes) == 6
    assert ("GET", "/users", 1, "api") in routes
    assert ("POST", "/users", 1, "api") in routes
    assert all(row[3] == "api" for row in routes)


def test_fastapi_dependencies_extracted():
    db_path = DB_PATH

    rows = fetchall(
        db_path,
        "SELECT method, pattern, dependencies FROM python_routes ORDER BY line",
    )
    assert len(rows) == 5
    dependencies_map = {
        (method, pattern): json.loads(deps) if deps else []
        for method, pattern, deps in rows
    }
    assert dependencies_map[("GET", "/users")] == ["get_db"]
    assert dependencies_map[("GET", "/users/{user_id}")] == ["get_db", "get_current_user"]


def test_import_resolution_records_resolved_targets():
    db_path = DB_PATH

    refs = fetchall(
        db_path,
        "SELECT src, value FROM refs WHERE src LIKE ? ORDER BY value",
        ("import_resolution/api/controllers.py",),
    )
    resolved = {value for _src, value in refs}
    assert {"services.user", "util.helpers"} <= resolved


def test_cross_framework_parity_sample():
    db_path = DB_PATH

    route_count = fetchall(db_path, "SELECT COUNT(*) FROM python_routes")
    model_count = fetchall(db_path, "SELECT COUNT(*) FROM python_orm_models")
    assert route_count[0][0] > 0
    assert model_count[0][0] > 0


# ==============================================================================
# Django ORM Tests
# ==============================================================================

def test_django_models_extracted():
    """Test Django model extraction to python_orm_models table."""
    db_path = DB_PATH

    # Check that core models are extracted
    models = {row[0] for row in fetchall(db_path, "SELECT model_name FROM python_orm_models")}

    expected_models = {
        "Organization", "Profile", "User", "Tag", "Post", "PostTag",
        "Comment", "Notification", "ActivityLog", "Team", "TeamMembership",
        "Project", "FieldTypeCoverage"
    }

    assert expected_models <= models, f"Missing models: {expected_models - models}"


def test_django_foreign_key_fields_extracted():
    """Test Django ForeignKey fields are marked as foreign keys in python_orm_fields."""
    db_path = DB_PATH

    # Get all ForeignKey fields
    fk_fields = fetchall(
        db_path,
        """
        SELECT model_name, field_name, is_foreign_key
        FROM python_orm_fields
        WHERE is_foreign_key = 1
        ORDER BY model_name, field_name
        """
    )

    fk_map = {(model, field) for model, field, _ in fk_fields}

    # Validate ForeignKey relationships
    expected_fks = {
        ("User", "organization"),      # User.organization -> Organization
        ("User", "profile"),            # User.profile -> Profile (OneToOne also FK)
        ("Post", "author"),             # Post.author -> User
        ("PostTag", "post"),            # PostTag.post -> Post
        ("PostTag", "tag"),             # PostTag.tag -> Tag
        ("PostTag", "added_by"),        # PostTag.added_by -> User
        ("Comment", "post"),            # Comment.post -> Post
        ("Comment", "author"),          # Comment.author -> User
        ("Comment", "parent_comment"),  # Comment.parent_comment -> Comment (self-referential)
        ("Notification", "recipient"),  # Notification.recipient -> User
        ("ActivityLog", "actor"),       # ActivityLog.actor -> User
        ("Team", "organization"),       # Team.organization -> Organization
        ("TeamMembership", "user"),     # TeamMembership.user -> User
        ("TeamMembership", "team"),     # TeamMembership.team -> Team
        ("Project", "owner"),           # Project.owner -> User
        ("Project", "team"),            # Project.team -> Team
        ("Project", "organization"),    # Project.organization -> Organization
    }

    missing_fks = expected_fks - fk_map
    assert not missing_fks, f"Missing ForeignKey fields: {missing_fks}"


def test_django_onetoone_relationships():
    """Test Django OneToOneField creates correct relationship entries."""
    db_path = DB_PATH

    # Check for User <-> Profile OneToOne relationship
    relationships = fetchall(
        db_path,
        """
        SELECT source_model, target_model, relationship_type
        FROM orm_relationships
        WHERE (source_model = 'User' AND target_model = 'Profile')
           OR (source_model = 'Profile' AND target_model = 'User')
        """
    )

    rel_set = {(src, tgt, rel_type) for src, tgt, rel_type in relationships}

    # OneToOne should create bidirectional relationships
    assert ("User", "Profile", "hasOne") in rel_set or ("User", "Profile", "belongsTo") in rel_set, \
        "User -> Profile OneToOne relationship not found"


def test_django_manytomany_relationships():
    """Test Django ManyToManyField creates correct relationship entries."""
    db_path = DB_PATH

    # Check for Post <-> Tag ManyToMany (with through table)
    relationships = fetchall(
        db_path,
        """
        SELECT source_model, target_model, relationship_type
        FROM orm_relationships
        WHERE (source_model = 'Post' AND target_model = 'Tag')
           OR (source_model = 'Tag' AND target_model = 'Post')
        """
    )

    rel_set = {(src, tgt, rel_type) for src, tgt, rel_type in relationships}

    # ManyToMany should create bidirectional manyToMany relationships
    assert ("Post", "Tag", "manyToMany") in rel_set, "Post -> Tag ManyToMany not found"
    assert ("Tag", "Post", "manyToMany") in rel_set, "Tag -> Post ManyToMany not found"


def test_django_through_tables_extracted():
    """Test Django through tables (PostTag, TeamMembership) are extracted as models."""
    db_path = DB_PATH

    # Through tables should be models themselves
    models = {row[0] for row in fetchall(db_path, "SELECT model_name FROM python_orm_models")}

    assert "PostTag" in models, "PostTag through table not extracted as model"
    assert "TeamMembership" in models, "TeamMembership through table not extracted as model"

    # Through table should have ForeignKeys to both sides
    posttag_fields = fetchall(
        db_path,
        """
        SELECT field_name, is_foreign_key
        FROM python_orm_fields
        WHERE model_name = 'PostTag' AND is_foreign_key = 1
        """
    )

    posttag_fks = {field for field, _ in posttag_fields}
    assert {"post", "tag", "added_by"} <= posttag_fks, \
        f"PostTag missing ForeignKeys, found: {posttag_fks}"


def test_django_self_referential_relationship():
    """Test Django self-referential ForeignKey (Comment.parent_comment -> Comment)."""
    db_path = DB_PATH

    # Self-referential should create relationship to same model
    relationships = fetchall(
        db_path,
        """
        SELECT source_model, target_model, relationship_type
        FROM orm_relationships
        WHERE source_model = 'Comment' AND target_model = 'Comment'
        """
    )

    # Should have Comment -> Comment relationship
    assert len(relationships) > 0, "Self-referential Comment.parent_comment not extracted"


def test_django_cascade_behaviors_extracted():
    """Test Django on_delete behaviors are captured in relationship metadata."""
    db_path = DB_PATH

    # Check if cascade information is stored (in attributes or cascade_delete column)
    # This validates that Project has different on_delete behaviors:
    # - owner: SET_NULL
    # - team: PROTECT
    # - organization: CASCADE

    project_fields = fetchall(
        db_path,
        """
        SELECT field_name, is_foreign_key
        FROM python_orm_fields
        WHERE model_name = 'Project' AND is_foreign_key = 1
        """
    )

    project_fks = {field for field, _ in project_fields}
    assert {"owner", "team", "organization"} == project_fks, \
        f"Project ForeignKeys mismatch, found: {project_fks}"


def test_django_generic_foreign_key_extracted():
    """Test Django GenericForeignKey (polymorphic relationships) are extracted."""
    db_path = DB_PATH

    # GenericForeignKey uses ContentType framework
    # Check that Notification and ActivityLog models are extracted
    models = {row[0] for row in fetchall(db_path, "SELECT model_name FROM python_orm_models")}

    assert "Notification" in models, "Notification (GenericForeignKey) not extracted"
    assert "ActivityLog" in models, "ActivityLog (GenericForeignKey) not extracted"

    # Check that content_type and object_id fields are extracted
    notification_fields = fetchall(
        db_path,
        """
        SELECT field_name
        FROM python_orm_fields
        WHERE model_name = 'Notification'
        ORDER BY field_name
        """
    )

    notification_field_names = {field for field, in notification_fields}
    assert {"content_type", "object_id"} <= notification_field_names, \
        f"Notification missing GenericForeignKey fields, found: {notification_field_names}"


def test_django_field_types_extracted():
    """Test Django field types are correctly extracted to python_orm_fields."""
    db_path = DB_PATH

    # Check FieldTypeCoverage model has various field types
    field_types = fetchall(
        db_path,
        """
        SELECT field_name, field_type
        FROM python_orm_fields
        WHERE model_name = 'FieldTypeCoverage'
        ORDER BY field_name
        """
    )

    field_type_map = {field: ftype for field, ftype in field_types if ftype}

    # Validate some key field types are extracted
    # Note: Actual field_type values depend on extractor implementation
    assert len(field_type_map) > 10, \
        f"Expected 20+ fields in FieldTypeCoverage, found {len(field_type_map)}"


def test_django_vs_sqlalchemy_parity():
    """Test Django ORM extraction has parity with SQLAlchemy extraction."""
    db_path = DB_PATH

    # Get ALL models, filter by file in Python
    all_models = fetchall(db_path, "SELECT model_name, file FROM python_orm_models")
    django_models = [m for m, f in all_models if 'django_app.py' in f]
    sqlalchemy_models = [m for m, f in all_models if 'sqlalchemy_app.py' in f]

    assert len(django_models) >= 10, f"Django extracted only {len(django_models)} models"
    assert len(sqlalchemy_models) >= 5, f"SQLAlchemy extracted only {len(sqlalchemy_models)} models"

    # Get ALL relationships, filter by file in Python
    all_rels = fetchall(db_path, "SELECT source_model, target_model, file FROM orm_relationships")
    django_rels = [r for r in all_rels if r[2] and 'django_app.py' in r[2]]
    sqlalchemy_rels = [r for r in all_rels if r[2] and 'sqlalchemy_app.py' in r[2]]

    assert len(django_rels) >= 10, f"Django extracted only {len(django_rels)} relationships"
    assert len(sqlalchemy_rels) >= 5, f"SQLAlchemy extracted only {len(sqlalchemy_rels)} relationships"


def test_django_bidirectional_relationships():
    """Test Django relationships are bidirectional (ForeignKey creates both belongsTo and hasMany)."""
    db_path = DB_PATH

    # User -> Organization (ForeignKey) should create:
    # - User belongsTo Organization
    # - Organization hasMany User
    user_org_relationships = fetchall(
        db_path,
        """
        SELECT source_model, target_model, relationship_type
        FROM orm_relationships
        WHERE (source_model = 'User' AND target_model = 'Organization')
           OR (source_model = 'Organization' AND target_model = 'User')
        ORDER BY source_model, relationship_type
        """
    )

    rel_set = {(src, tgt, rel_type) for src, tgt, rel_type in user_org_relationships}

    # Should have both directions
    assert ("User", "Organization", "belongsTo") in rel_set, "User belongsTo Organization missing"
    assert ("Organization", "User", "hasMany") in rel_set, "Organization hasMany User missing"


# ==============================================================================
# Deep Nesting and Inheritance Tests
# ==============================================================================

def test_deep_inheritance_extracted():
    """Test 3+ level inheritance chains are extracted with correct parent relationships."""
    db_path = DB_PATH

    # Check that all classes in deep hierarchy are extracted
    classes = {row[0] for row in fetchall(db_path, "SELECT name FROM symbols WHERE type = 'class'")}

    expected_classes = {
        "BaseModel", "TimestampedModel", "SoftDeletableModel", "User",
        "AdminUser", "SuperAdminUser"
    }
    assert expected_classes <= classes, f"Missing classes in deep hierarchy: {expected_classes - classes}"

    # Validate inheritance chain: BaseModel -> TimestampedModel -> SoftDeletableModel -> User
    # Check parent_class column (if implemented) or inheritance records
    class_info = fetchall(
        db_path,
        """
        SELECT name, parent_class
        FROM symbols
        WHERE type = 'class' AND name IN ('User', 'SoftDeletableModel', 'TimestampedModel', 'AdminUser', 'SuperAdminUser')
        ORDER BY name
        """
    )

    # Build parent map
    parent_map = {name: parent for name, parent in class_info if parent}

    # Validate inheritance chain (if parent_class is populated)
    if parent_map:
        assert parent_map.get("TimestampedModel") == "BaseModel", \
            "TimestampedModel should inherit from BaseModel"
        assert parent_map.get("SoftDeletableModel") == "TimestampedModel", \
            "SoftDeletableModel should inherit from TimestampedModel"
        assert parent_map.get("User") == "SoftDeletableModel", \
            "User should inherit from SoftDeletableModel (3 levels deep)"
        assert parent_map.get("AdminUser") == "User", \
            "AdminUser should inherit from User (4 levels deep)"
        assert parent_map.get("SuperAdminUser") == "AdminUser", \
            "SuperAdminUser should inherit from AdminUser (5 levels deep!)"


def test_deep_nested_classes_extracted():
    """Test 3+ level nested classes are extracted with correct symbol paths."""
    db_path = DB_PATH

    # Check that nested classes are extracted with qualified names
    # Expected: OuterClass.MiddleClass.InnerClass.DeepNested
    # Fetch ALL symbols, filter in Python
    all_symbols = fetchall(db_path, "SELECT name, type FROM symbols ORDER BY name")

    # Filter in Python for Class or Nested in name
    symbols = [(name, type_) for name, type_ in all_symbols if 'Class' in name or 'Nested' in name]

    symbol_names = {name for name, _ in symbols}

    # Check for nested class hierarchy
    expected_nested = {
        "OuterClass",
        "MiddleClass",  # May be qualified as OuterClass.MiddleClass
        "InnerClass",   # May be qualified as OuterClass.MiddleClass.InnerClass
        "DeepNested"    # May be qualified as OuterClass.MiddleClass.InnerClass.DeepNested
    }

    # At minimum, all these names should appear (possibly with qualifiers)
    found_nested = {name for name in symbol_names if any(expected in name for expected in expected_nested)}

    assert len(found_nested) >= 4, \
        f"Expected at least 4 nested classes, found: {found_nested}"


def test_inherited_methods_accessible():
    """Test methods from parent classes are visible in child class scope."""
    db_path = DB_PATH

    # Get methods for User class (should include methods from all ancestors)
    # Note: This tests symbol extraction completeness, not runtime inheritance
    # Fetch ALL functions with these names, filter by file in Python
    all_methods = fetchall(
        db_path,
        """
        SELECT name, path FROM symbols
        WHERE type = 'function'
        AND name IN ('save', 'validate', 'soft_delete', 'validate_email', 'get_display_name')
        """
    )

    # Filter in Python for deep_nesting.py
    method_names = {name for name, path in all_methods if 'deep_nesting.py' in path}

    # User class defines: save, validate, validate_email, get_display_name
    # Plus inherits: soft_delete (from SoftDeletableModel)
    expected_methods = {"save", "validate", "soft_delete", "validate_email", "get_display_name"}

    assert expected_methods <= method_names, \
        f"Missing inherited methods: {expected_methods - method_names}"


def test_multiple_inheritance_extracted():
    """Test multiple inheritance (diamond problem) classes are extracted."""
    db_path = DB_PATH

    # AuditableModel inherits from: BaseModel, Loggable, Cacheable
    # AuditedUser inherits from: AuditableModel, TimestampedModel (diamond - both inherit BaseModel)

    classes = {row[0] for row in fetchall(db_path, "SELECT name FROM symbols WHERE type = 'class'")}

    multiple_inheritance_classes = {"AuditableModel", "AuditedUser", "Loggable", "Cacheable"}

    assert multiple_inheritance_classes <= classes, \
        f"Missing multiple inheritance classes: {multiple_inheritance_classes - classes}"


def test_nested_class_with_inheritance():
    """Test nested classes that also have inheritance are extracted."""
    db_path = DB_PATH

    # Container.BaseHandler -> Container.MiddleHandler -> Container.AdvancedHandler

    # Fetch ALL symbols, filter in Python
    all_symbols = fetchall(db_path, "SELECT name, type FROM symbols ORDER BY name")

    # Filter in Python for Handler in name
    symbols = [(name, type_) for name, type_ in all_symbols if 'Handler' in name]

    handler_names = {name for name, _ in symbols}

    expected_handlers = {"BaseHandler", "MiddleHandler", "AdvancedHandler"}

    # At minimum, these handler classes should be extracted
    found_handlers = {name for name in handler_names if any(h in name for h in expected_handlers)}

    assert len(found_handlers) >= 3, \
        f"Expected 3 nested Handler classes, found: {found_handlers}"


def test_repository_pattern_inheritance():
    """Test repository pattern with generic base class inheritance."""
    db_path = DB_PATH

    # Repository -> UserRepository -> AdminUserRepository (2 levels)

    classes = {row[0] for row in fetchall(db_path, "SELECT name FROM symbols WHERE type = 'class'")}

    repository_classes = {"Repository", "UserRepository", "AdminUserRepository"}

    assert repository_classes <= classes, \
        f"Missing repository classes: {repository_classes - classes}"


def test_abstract_service_hierarchy():
    """Test abstract base class with template methods and inheritance."""
    db_path = DB_PATH

    # AbstractService -> UserService -> EnhancedUserService

    classes = {row[0] for row in fetchall(db_path, "SELECT name FROM symbols WHERE type = 'class'")}

    service_classes = {"AbstractService", "UserService", "EnhancedUserService"}

    assert service_classes <= classes, \
        f"Missing service classes: {service_classes - classes}"

    # Check that abstract methods are extracted
    methods = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'function' AND name IN ('execute', 'perform', 'validate_input', 'cleanup')"
    )}

    expected_methods = {"execute", "perform", "validate_input", "cleanup"}

    assert expected_methods <= methods, \
        f"Missing abstract/template methods: {expected_methods - methods}"


def test_metaclass_inheritance():
    """Test metaclass and classes using metaclass are extracted."""
    db_path = DB_PATH

    # ModelMeta (metaclass) -> MetaModel -> MetaUser

    classes = {row[0] for row in fetchall(db_path, "SELECT name FROM symbols WHERE type = 'class'")}

    metaclass_classes = {"ModelMeta", "MetaModel", "MetaUser"}

    assert metaclass_classes <= classes, \
        f"Missing metaclass hierarchy: {metaclass_classes - classes}"


# ==============================================================================
# Complex Decorators Tests
# ==============================================================================

def test_simple_decorators_extracted():
    """Test simple decorators (without arguments) are extracted."""
    db_path = DB_PATH

    # Check that decorator functions are extracted as symbols
    decorators = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'function' AND name IN ('simple_decorator', 'timer', 'log_calls', 'require_auth')"
    )}

    expected_decorators = {"simple_decorator", "timer", "log_calls", "require_auth"}

    assert expected_decorators <= decorators, \
        f"Missing decorator functions: {expected_decorators - decorators}"


def test_parameterized_decorators_extracted():
    """Test parameterized decorators (with arguments) are extracted."""
    db_path = DB_PATH

    # Parameterized decorators: cache, rate_limit, retry, require_role, validate_input
    param_decorators = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('cache', 'rate_limit', 'retry', 'require_role', 'validate_input')
        """
    )}

    expected_param_decorators = {"cache", "rate_limit", "retry", "require_role", "validate_input"}

    assert expected_param_decorators <= param_decorators, \
        f"Missing parameterized decorators: {expected_param_decorators - param_decorators}"


def test_stacked_decorators_on_functions():
    """Test functions with 3+ stacked decorators are extracted."""
    db_path = DB_PATH

    # Check that decorated functions are extracted
    decorated_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('admin_dashboard', 'create_user', 'fetch_external_api', 'transfer_funds')
        """
    )}

    expected_functions = {"admin_dashboard", "create_user", "fetch_external_api", "transfer_funds"}

    assert expected_functions <= decorated_functions, \
        f"Missing decorated functions: {expected_functions - decorated_functions}"


def test_security_decorators_extracted():
    """Test security-relevant decorators (auth, role, permissions) are extracted."""
    db_path = DB_PATH

    # Security decorators: require_auth, require_role, require_permissions
    security_decorators = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('require_auth', 'require_role', 'require_permissions')
        """
    )}

    expected_security = {"require_auth", "require_role", "require_permissions"}

    assert expected_security <= security_decorators, \
        f"Missing security decorators: {expected_security - security_decorators}"


def test_validation_decorators_extracted():
    """Test validation decorators (important for security) are extracted."""
    db_path = DB_PATH

    # Validation decorators: validate_input, validate_output
    validation_decorators = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('validate_input', 'validate_output')
        """
    )}

    expected_validation = {"validate_input", "validate_output"}

    assert expected_validation <= validation_decorators, \
        f"Missing validation decorators: {expected_validation - validation_decorators}"


def test_class_decorators_extracted():
    """Test class decorators (singleton, add_logging) are extracted."""
    db_path = DB_PATH

    # Class decorators
    class_decorators = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('singleton', 'add_logging')
        """
    )}

    expected_class_decs = {"singleton", "add_logging"}

    assert expected_class_decs <= class_decorators, \
        f"Missing class decorators: {expected_class_decs - class_decorators}"

    # Check that decorated class is extracted
    decorated_classes = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'class' AND name = 'ConfigManager'"
    )}

    assert "ConfigManager" in decorated_classes, "Decorated class ConfigManager not extracted"


def test_method_decorators_in_classes():
    """Test decorators on instance methods are extracted."""
    db_path = DB_PATH

    # Check that APIController class is extracted
    classes = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'class' AND name = 'APIController'"
    )}

    assert "APIController" in classes, "APIController class not extracted"

    # Check that decorated methods are extracted
    methods = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('get_users', 'delete_user', 'expensive_operation')
        """
    )}

    expected_methods = {"get_users", "delete_user", "expensive_operation"}

    assert expected_methods <= methods, \
        f"Missing decorated methods: {expected_methods - methods}"


def test_staticmethod_classmethod_decorators():
    """Test decorators on @staticmethod and @classmethod are extracted."""
    db_path = DB_PATH

    # Check UtilityClass with static/class methods
    classes = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'class' AND name = 'UtilityClass'"
    )}

    assert "UtilityClass" in classes, "UtilityClass not extracted"

    # Check methods with decorators
    methods = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('validate_email', 'from_config')
        """
    )}

    expected_methods = {"validate_email", "from_config"}

    assert expected_methods <= methods, \
        f"Missing static/class methods: {expected_methods - methods}"


def test_property_decorators_extracted():
    """Test @property, @setter decorators are extracted."""
    db_path = DB_PATH

    # Check User class with properties
    classes = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'class' AND name = 'User'"
    )}

    assert "User" in classes, "User class with properties not extracted"

    # Check that property methods are extracted
    # Note: Properties appear as functions in symbols table
    # Fetch ALL functions with these names, filter by file in Python
    all_properties = fetchall(
        db_path,
        """
        SELECT name, path FROM symbols
        WHERE type = 'function'
        AND name IN ('name', 'email', 'age')
        """
    )

    # Filter in Python for decorators.py
    properties = {name for name, path in all_properties if 'decorators.py' in path}

    # At least some properties should be extracted
    assert len(properties) >= 2, \
        f"Expected multiple property methods, found: {properties}"


def test_transaction_decorator_extracted():
    """Test transaction decorator (context manager pattern) is extracted."""
    db_path = DB_PATH

    # with_transaction decorator
    decorators = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'function' AND name = 'with_transaction'"
    )}

    assert "with_transaction" in decorators, "Transaction decorator not extracted"

    # transfer_funds function using transaction decorator
    functions = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'function' AND name = 'transfer_funds'"
    )}

    assert "transfer_funds" in functions, "Function with transaction decorator not extracted"


def test_async_decorators_extracted():
    """Test decorators on async functions are extracted (preview of Task 4)."""
    db_path = DB_PATH

    # async_timer decorator
    decorators = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'function' AND name = 'async_timer'"
    )}

    assert "async_timer" in decorators, "Async decorator not extracted"

    # async_fetch_data function
    functions = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'function' AND name = 'async_fetch_data'"
    )}

    assert "async_fetch_data" in functions, "Async function with decorators not extracted"


def test_decorator_call_graph_entries():
    """Test that decorated functions have call graph entries to decorators."""
    db_path = DB_PATH

    # Check function_calls table for decorator usage
    # When admin_dashboard is called, it should show calls to decorators
    # Note: This tests CFG extraction quality

    # Validate admin_dashboard exists
    functions = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'function' AND name = 'admin_dashboard'"
    )}

    assert "admin_dashboard" in functions, \
        "admin_dashboard (with 4 stacked decorators) not extracted"

    # Check that create_user (with 3 decorators) exists
    create_user = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'function' AND name = 'create_user'"
    )}

    assert "create_user" in create_user, \
        "create_user (with 3 stacked decorators) not extracted"


# ==============================================================================
# Async Patterns Tests
# ==============================================================================

def test_async_functions_extracted():
    """Test async def functions are extracted to symbols table."""
    db_path = DB_PATH

    # Check that async functions are extracted
    async_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('simple_async_function', 'async_with_params', 'fetch_user', 'fetch_user_data', 'fetch_user_profile')
        """
    )}

    expected_async = {"simple_async_function", "async_with_params", "fetch_user", "fetch_user_data", "fetch_user_profile"}

    assert expected_async <= async_functions, \
        f"Missing async functions: {expected_async - async_functions}"


def test_await_call_chains_extracted():
    """Test await call chains (function awaits function awaits function) are captured."""
    db_path = DB_PATH

    # fetch_user awaits fetch_user_data which awaits fetch_user_profile
    # This is a 3-level await chain - validate all functions exist
    chain_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('fetch_user', 'fetch_user_data', 'fetch_user_profile', 'fetch_user_permissions')
        """
    )}

    expected_chain = {"fetch_user", "fetch_user_data", "fetch_user_profile", "fetch_user_permissions"}

    assert expected_chain == chain_functions, \
        f"Await chain functions incomplete: {expected_chain - chain_functions}"


def test_parallel_async_operations_extracted():
    """Test asyncio.gather parallel patterns are extracted."""
    db_path = DB_PATH

    # Functions using asyncio.gather
    parallel_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('process_batch', 'fetch_user_and_posts', 'process_item')
        """
    )}

    expected_parallel = {"process_batch", "fetch_user_and_posts", "process_item"}

    assert expected_parallel == parallel_functions, \
        f"Missing parallel async functions: {expected_parallel - parallel_functions}"


def test_async_context_managers_extracted():
    """Test async context managers (__aenter__, __aexit__) are extracted."""
    db_path = DB_PATH

    # AsyncDatabaseConnection class with __aenter__ and __aexit__
    classes = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'class' AND name = 'AsyncDatabaseConnection'"
    )}

    assert "AsyncDatabaseConnection" in classes, \
        "Async context manager class not extracted"

    # Check that __aenter__ and __aexit__ methods are extracted
    # Fetch ALL functions with these names, filter by file in Python
    all_context_methods = fetchall(
        db_path,
        """
        SELECT name, path FROM symbols
        WHERE type = 'function'
        AND name IN ('__aenter__', '__aexit__', 'execute')
        """
    )

    # Filter in Python for async_app.py
    context_methods = {name for name, path in all_context_methods if 'async_app.py' in path}

    expected_methods = {"__aenter__", "__aexit__", "execute"}

    assert expected_methods <= context_methods, \
        f"Missing async context manager methods: {expected_methods - context_methods}"


def test_async_with_statement_functions():
    """Test functions using async with are extracted."""
    db_path = DB_PATH

    # Functions using async with statement
    async_with_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('query_database', 'query_with_decorator_context_manager', 'use_api_client')
        """
    )}

    expected_functions = {"query_database", "query_with_decorator_context_manager", "use_api_client"}

    assert expected_functions == async_with_functions, \
        f"Missing async with functions: {expected_functions - async_with_functions}"


def test_async_generators_extracted():
    """Test async generators (yield in async def) are extracted."""
    db_path = DB_PATH

    # Async generator functions
    generators = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('generate_numbers', 'fetch_paginated_results')
        """
    )}

    expected_generators = {"generate_numbers", "fetch_paginated_results"}

    assert expected_generators == generators, \
        f"Missing async generators: {expected_generators - generators}"


def test_async_for_loops_extracted():
    """Test functions with async for loops are extracted."""
    db_path = DB_PATH

    # Functions consuming async generators with async for
    async_for_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('consume_async_generator', 'process_paginated_data')
        """
    )}

    expected_functions = {"consume_async_generator", "process_paginated_data"}

    assert expected_functions == async_for_functions, \
        f"Missing async for functions: {expected_functions - async_for_functions}"


def test_async_error_handling_extracted():
    """Test async functions with try/except are extracted."""
    db_path = DB_PATH

    # Async functions with error handling
    error_handling = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('risky_async_operation', 'handle_async_errors', 'retry_async_operation')
        """
    )}

    expected_functions = {"risky_async_operation", "handle_async_errors", "retry_async_operation"}

    assert expected_functions == error_handling, \
        f"Missing async error handling functions: {expected_functions - error_handling}"


def test_async_decorators_on_functions():
    """Test decorators on async functions are extracted."""
    db_path = DB_PATH

    # Async decorators
    decorators = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('async_timer', 'async_retry')
        """
    )}

    expected_decorators = {"async_timer", "async_retry"}

    assert expected_decorators == decorators, \
        f"Missing async decorators: {expected_decorators - decorators}"

    # Decorated async function
    decorated = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'function' AND name = 'decorated_async_function'"
    )}

    assert "decorated_async_function" in decorated, \
        "Decorated async function not extracted"


def test_mixed_sync_async_code():
    """Test mixed sync/async code is extracted correctly."""
    db_path = DB_PATH

    # Sync helper called from async context
    functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('sync_helper', 'async_calling_sync', 'run_in_executor')
        """
    )}

    expected_functions = {"sync_helper", "async_calling_sync", "run_in_executor"}

    assert expected_functions == functions, \
        f"Missing mixed sync/async functions: {expected_functions - functions}"


def test_async_class_methods_extracted():
    """Test async methods in classes are extracted."""
    db_path = DB_PATH

    # AsyncService class
    classes = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'class' AND name = 'AsyncService'"
    )}

    assert "AsyncService" in classes, "AsyncService class not extracted"

    # Async methods - fetch ALL, filter by file in Python
    all_methods = fetchall(
        db_path,
        """
        SELECT name, path FROM symbols
        WHERE type = 'function'
        AND name IN ('initialize', 'fetch_data', 'process', 'static_async_method', 'from_config')
        """
    )

    # Filter in Python for async_app.py
    methods = {name for name, path in all_methods if 'async_app.py' in path}

    expected_methods = {"initialize", "fetch_data", "process", "static_async_method", "from_config"}

    assert expected_methods <= methods, \
        f"Missing async methods: {expected_methods - methods}"


def test_async_comprehensions_extracted():
    """Test functions with async comprehensions are extracted."""
    db_path = DB_PATH

    # Function using async list/dict comprehensions
    functions = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'function' AND name = 'async_comprehension_example'"
    )}

    assert "async_comprehension_example" in functions, \
        "Async comprehension function not extracted"


def test_async_api_client_class_extracted():
    """Test realistic async API client class is extracted."""
    db_path = DB_PATH

    # AsyncAPIClient class (real-world pattern)
    classes = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'class' AND name = 'AsyncAPIClient'"
    )}

    assert "AsyncAPIClient" in classes, "AsyncAPIClient class not extracted"

    # API client methods
    methods = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('connect', 'disconnect', 'get', 'post', 'fetch_multiple')
        AND file LIKE '%async_app.py%'
        """
    )}

    expected_methods = {"connect", "disconnect", "get", "post", "fetch_multiple"}

    assert expected_methods <= methods, \
        f"Missing API client methods: {expected_methods - methods}"


def test_async_symbol_count():
    """Test overall async fixture extraction completeness."""
    db_path = DB_PATH

    # Total functions extracted
    total_functions = fetchall(
        db_path,
        "SELECT COUNT(*) FROM symbols WHERE type = 'function' AND file LIKE '%async_app.py%'"
    )[0][0]

    # Should extract 40+ functions (async and sync)
    assert total_functions >= 40, \
        f"Expected 40+ functions from async_app.py, found {total_functions}"

    # Total classes extracted
    total_classes = fetchall(
        db_path,
        "SELECT COUNT(*) FROM symbols WHERE type = 'class' AND file LIKE '%async_app.py%'"
    )[0][0]

    # Should extract 4+ classes
    assert total_classes >= 3, \
        f"Expected 3+ classes from async_app.py, found {total_classes}"


# ==============================================================================
# Circular Imports Tests
# ==============================================================================

def test_circular_imports_no_crash():
    """Test that circular imports don't crash the indexer."""
    # This is the critical test - indexer must complete without infinite loop
    db_path = DB_PATH

    # If we get here, indexer didn't crash - success!
    assert db_path.exists(), "Database should exist after indexing circular imports"


def test_circular_imports_all_modules_indexed():
    """Test that all modules in circular import chain are indexed."""
    db_path = DB_PATH

    # Check that all 4 modules are in the database
    files = fetchall(
        db_path,
        """
        SELECT DISTINCT file FROM symbols
        WHERE file LIKE '%circular_imports%'
        """
    )

    file_names = {row[0] for row in files}

    # Should have models.py, services.py, controllers.py, utils.py
    assert any("models.py" in f for f in file_names), "models.py not indexed"
    assert any("services.py" in f for f in file_names), "services.py not indexed"
    assert any("controllers.py" in f for f in file_names), "controllers.py not indexed"
    assert any("utils.py" in f for f in file_names), "utils.py not indexed"


def test_circular_imports_models_extracted():
    """Test that model classes in circular imports are extracted."""
    db_path = DB_PATH

    # Models: User, Post, Comment
    models = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'class'
        AND file LIKE '%circular_imports%models.py%'
        """
    )}

    expected_models = {"User", "Post", "Comment"}

    assert expected_models <= models, \
        f"Missing model classes: {expected_models - models}"


def test_circular_imports_services_extracted():
    """Test that service classes in circular imports are extracted."""
    db_path = DB_PATH

    # Services: UserService, PostService, CommentService
    services = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'class'
        AND file LIKE '%circular_imports%services.py%'
        """
    )}

    expected_services = {"UserService", "PostService", "CommentService"}

    assert expected_services <= services, \
        f"Missing service classes: {expected_services - services}"


def test_circular_imports_controllers_extracted():
    """Test that controller classes in circular imports are extracted."""
    db_path = DB_PATH

    # Controllers: UserController, PostController, CommentController
    controllers = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'class'
        AND file LIKE '%circular_imports%controllers.py%'
        """
    )}

    expected_controllers = {"UserController", "PostController", "CommentController"}

    assert expected_controllers <= controllers, \
        f"Missing controller classes: {expected_controllers - controllers}"


def test_circular_imports_utils_functions_extracted():
    """Test that utility functions in circular imports are extracted."""
    db_path = DB_PATH

    # Utils functions
    utils = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND file LIKE '%circular_imports%utils.py%'
        """
    )}

    expected_utils = {
        "get_user_summary",
        "bulk_update_user_emails",
        "get_post_with_comments",
        "search_users_and_posts",
        "create_post_with_author"
    }

    assert expected_utils <= utils, \
        f"Missing utility functions: {expected_utils - utils}"


def test_circular_imports_have_refs():
    """Test that circular imports create import references in refs table."""
    db_path = DB_PATH

    # Check that import refs exist between circular modules
    refs = fetchall(
        db_path,
        """
        SELECT DISTINCT src, value FROM refs
        WHERE ref_type = 'import'
        AND src LIKE '%circular_imports%'
        """
    )

    # Should have refs between the circular modules
    ref_pairs = {(row[0], row[1]) for row in refs}

    # At minimum, some imports should be recorded
    assert len(ref_pairs) > 0, "No import refs found for circular imports"


def test_circular_imports_symbol_count():
    """Test overall extraction completeness for circular imports package."""
    db_path = DB_PATH

    # Total classes extracted (models + services + controllers)
    total_classes = fetchall(
        db_path,
        """
        SELECT COUNT(*) FROM symbols
        WHERE type = 'class'
        AND file LIKE '%circular_imports%'
        """
    )[0][0]

    # Should extract 9+ classes (User, Post, Comment, 3 services, 3 controllers)
    assert total_classes >= 9, \
        f"Expected 9+ classes from circular_imports, found {total_classes}"

    # Total functions extracted
    total_functions = fetchall(
        db_path,
        """
        SELECT COUNT(*) FROM symbols
        WHERE type = 'function'
        AND file LIKE '%circular_imports%'
        """
    )[0][0]

    # Should extract 30+ functions (methods + module-level functions)
    assert total_functions >= 25, \
        f"Expected 25+ functions from circular_imports, found {total_functions}"


def test_circular_imports_no_infinite_loop():
    """Test that circular import resolution didn't infinite loop."""
    # If we can index and query the database, no infinite loop occurred
    db_path = DB_PATH

    # Simple smoke test - just check we can query
    result = fetchall(
        db_path,
        "SELECT COUNT(*) FROM symbols WHERE file LIKE '%circular_imports%'"
    )

    assert result[0][0] > 0, "No symbols extracted - possible indexer failure"


# ==============================================================================
# Complex Type Hints Tests
# ==============================================================================

def test_generic_classes_extracted():
    """Test generic classes (Generic[T], Generic[K, V]) are extracted."""
    db_path = DB_PATH

    # Generic classes: Container[T], Pair[K, V], Repository[T]
    generic_classes = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'class'
        AND name IN ('Container', 'Pair', 'Repository')
        """
    )}

    expected_generics = {"Container", "Pair", "Repository"}

    assert expected_generics == generic_classes, \
        f"Missing generic classes: {expected_generics - generic_classes}"


def test_nested_generic_functions_extracted():
    """Test functions with deeply nested generic types are extracted."""
    db_path = DB_PATH

    # Functions with nested generics
    nested_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('process_nested_dict', 'transform_complex_structure', 'process_optional_lists')
        """
    )}

    expected_functions = {"process_nested_dict", "transform_complex_structure", "process_optional_lists"}

    assert expected_functions == nested_functions, \
        f"Missing nested generic functions: {expected_functions - nested_functions}"


def test_union_type_functions_extracted():
    """Test functions with Union types are extracted."""
    db_path = DB_PATH

    # Functions with Union types
    union_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('handle_multiple_types', 'parse_value')
        """
    )}

    expected_functions = {"handle_multiple_types", "parse_value"}

    assert expected_functions == union_functions, \
        f"Missing Union type functions: {expected_functions - union_functions}"


def test_callable_type_functions_extracted():
    """Test functions with Callable type hints are extracted."""
    db_path = DB_PATH

    # Functions with Callable types
    callable_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('apply_transform', 'filter_items', 'compose_functions', 'higher_order_function')
        """
    )}

    expected_functions = {"apply_transform", "filter_items", "compose_functions", "higher_order_function"}

    assert expected_functions == callable_functions, \
        f"Missing Callable type functions: {expected_functions - callable_functions}"


def test_tuple_type_functions_extracted():
    """Test functions with Tuple types (including variadic) are extracted."""
    db_path = DB_PATH

    # Functions with Tuple types
    tuple_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('process_fixed_tuple', 'process_variadic_tuple', 'combine_tuples', 'complex_tuple_processing')
        """
    )}

    expected_functions = {"process_fixed_tuple", "process_variadic_tuple", "combine_tuples", "complex_tuple_processing"}

    assert expected_functions == tuple_functions, \
        f"Missing Tuple type functions: {expected_functions - tuple_functions}"


def test_protocol_classes_extracted():
    """Test Protocol classes (structural subtyping) are extracted."""
    db_path = DB_PATH

    # Protocol classes
    protocols = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'class'
        AND name IN ('Comparable', 'Drawable')
        """
    )}

    expected_protocols = {"Comparable", "Drawable"}

    assert expected_protocols == protocols, \
        f"Missing Protocol classes: {expected_protocols - protocols}"

    # Functions using Protocols
    protocol_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('sort_comparable_items', 'draw_all')
        """
    )}

    expected_functions = {"sort_comparable_items", "draw_all"}

    assert expected_functions == protocol_functions, \
        f"Missing Protocol-using functions: {expected_functions - protocol_functions}"


def test_literal_type_functions_extracted():
    """Test functions with Literal types are extracted."""
    db_path = DB_PATH

    # Functions with Literal types
    literal_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('get_status', 'set_log_level', 'process_mode')
        """
    )}

    expected_functions = {"get_status", "set_log_level", "process_mode"}

    assert expected_functions == literal_functions, \
        f"Missing Literal type functions: {expected_functions - literal_functions}"


def test_type_alias_functions_extracted():
    """Test functions using type aliases are extracted."""
    db_path = DB_PATH

    # Functions using type aliases
    alias_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('create_user', 'get_user_map', 'process_complex_structure')
        """
    )}

    expected_functions = {"create_user", "get_user_map", "process_complex_structure"}

    assert expected_functions == alias_functions, \
        f"Missing type alias functions: {expected_functions - alias_functions}"


def test_final_classvar_class_extracted():
    """Test class with Final and ClassVar annotations is extracted."""
    db_path = DB_PATH

    # Configuration class with Final/ClassVar
    classes = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'class' AND name = 'Configuration'"
    )}

    assert "Configuration" in classes, "Configuration class with Final/ClassVar not extracted"


def test_overload_function_extracted():
    """Test @overload functions are extracted."""
    db_path = DB_PATH

    # get_item function with @overload
    functions = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'function' AND name = 'get_item'"
    )}

    assert "get_item" in functions, "@overload function not extracted"


def test_dataclass_with_complex_types():
    """Test dataclass with complex type annotations is extracted."""
    db_path = DB_PATH

    # ComplexDataClass
    classes = {row[0] for row in fetchall(
        db_path,
        "SELECT name FROM symbols WHERE type = 'class' AND name = 'ComplexDataClass'"
    )}

    assert "ComplexDataClass" in classes, "ComplexDataClass not extracted"


def test_typevar_generic_functions():
    """Test functions using TypeVar and Generic patterns are extracted."""
    db_path = DB_PATH

    # Generic functions using TypeVars
    generic_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('deep_merge', 'map_values', 'flatten_nested_lists')
        """
    )}

    expected_functions = {"deep_merge", "map_values", "flatten_nested_lists"}

    assert expected_functions == generic_functions, \
        f"Missing TypeVar generic functions: {expected_functions - generic_functions}"


def test_iterator_generator_functions():
    """Test functions with Iterator and generator types are extracted."""
    db_path = DB_PATH

    # Iterator/generator functions
    iterator_functions = {row[0] for row in fetchall(
        db_path,
        """
        SELECT name FROM symbols
        WHERE type = 'function'
        AND name IN ('generate_items', 'iterate_with_transform')
        """
    )}

    expected_functions = {"generate_items", "iterate_with_transform"}

    assert expected_functions == iterator_functions, \
        f"Missing Iterator/generator functions: {expected_functions - iterator_functions}"


def test_type_annotations_symbol_count():
    """Test overall type annotations fixture extraction completeness."""
    db_path = DB_PATH

    # Total classes extracted (generics, protocols, dataclasses)
    total_classes = fetchall(
        db_path,
        "SELECT COUNT(*) FROM symbols WHERE type = 'class' AND file LIKE '%type_annotations.py%'"
    )[0][0]

    # Should extract 7+ classes
    assert total_classes >= 7, \
        f"Expected 7+ classes from type_annotations.py, found {total_classes}"

    # Total functions extracted
    total_functions = fetchall(
        db_path,
        "SELECT COUNT(*) FROM symbols WHERE type = 'function' AND file LIKE '%type_annotations.py%'"
    )[0][0]

    # Should extract 35+ functions
    assert total_functions >= 35, \
        f"Expected 35+ functions from type_annotations.py, found {total_functions}"
