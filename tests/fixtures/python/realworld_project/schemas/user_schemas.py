"""
Marshmallow schemas for user-related validation.

Test fixture for extract_marshmallow_schemas() and extract_marshmallow_fields().
Covers all field types, validators, nested schemas, and validation patterns.
"""

from marshmallow import Schema, ValidationError, fields, validates, validates_schema


class UserRegistrationSchema(Schema):
    """Basic user registration with common field types."""

    username = fields.String(required=True)
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=lambda x: len(x) >= 8)
    age = fields.Integer(allow_none=True)
    is_active = fields.Boolean()
    bio = fields.String(allow_none=True)


class AddressSchema(Schema):
    """Address validation schema (nested)."""

    street = fields.String(required=True)
    city = fields.String(required=True)
    state = fields.String(required=True)
    zip_code = fields.String(required=True, validate=lambda x: len(x) == 5)


class UserProfileSchema(Schema):
    """User profile with nested address."""

    user_id = fields.Integer(required=True)
    full_name = fields.String(required=True)
    address = fields.Nested(AddressSchema, required=True)
    phone = fields.String(allow_none=True)


class ArticleSchema(Schema):
    """Article schema with custom validators."""

    title = fields.String(required=True)
    slug = fields.String(required=True)
    content = fields.String(required=True)
    author_id = fields.Integer(required=True)
    status = fields.String(required=True)

    @validates("title")
    def validate_title(self, value):
        """Custom title validator (security: check for XSS patterns)."""
        if "<script>" in value.lower():
            raise ValidationError("Title contains dangerous HTML")
        if len(value) < 5:
            raise ValidationError("Title too short")

    @validates("slug")
    def validate_slug(self, value):
        """Custom slug validator (alphanumeric only)."""
        if not value.replace("-", "").replace("_", "").isalnum():
            raise ValidationError("Slug must be alphanumeric")

    @validates("status")
    def validate_status(self, value):
        """Validate status enum."""
        allowed_statuses = ["draft", "published", "archived"]
        if value not in allowed_statuses:
            raise ValidationError(f"Status must be one of: {allowed_statuses}")


class PasswordChangeSchema(Schema):
    """Password change with cross-field validation."""

    old_password = fields.String(required=True)
    new_password = fields.String(required=True, validate=lambda x: len(x) >= 8)
    confirm_password = fields.String(required=True)

    @validates_schema
    def validate_passwords(self, data, **kwargs):
        """Schema-level validator (cross-field validation)."""
        if data.get("new_password") != data.get("confirm_password"):
            raise ValidationError("Passwords do not match", "confirm_password")
        if data.get("old_password") == data.get("new_password"):
            raise ValidationError("New password must be different", "new_password")


class CommentSchema(Schema):
    """Comment schema (nested in article)."""

    comment_id = fields.Integer()
    author_id = fields.Integer(required=True)
    body = fields.String(required=True, validate=lambda x: len(x) <= 500)
    created_at = fields.DateTime()


class ArticleWithCommentsSchema(Schema):
    """Article with nested comments and author."""

    article_id = fields.Integer()
    title = fields.String(required=True)
    author = fields.Nested(UserProfileSchema)
    comments = fields.List(fields.Nested(CommentSchema))
    tags = fields.List(fields.String())

    @validates("title")
    def validate_title(self, value):
        """Revalidate title in complex schema."""
        if len(value) < 3:
            raise ValidationError("Title too short")


class OptionalMetadataSchema(Schema):
    """All optional fields (SECURITY RISK: everything can be omitted)."""

    metadata_key = fields.String()
    metadata_value = fields.String()
    created_by = fields.Integer()


class PaymentSchema(Schema):
    """Payment schema with allow_none on sensitive fields."""

    user_id = fields.Integer(required=True)
    amount = fields.Decimal(required=True)
    currency = fields.String(required=True)
    payment_method = fields.String(allow_none=True)
    billing_address = fields.Nested(AddressSchema, allow_none=True)


class SearchQuerySchema(Schema):
    """Search query with inline validators."""

    query = fields.String(required=True, validate=lambda x: len(x) >= 2)
    page = fields.Integer(validate=lambda x: x > 0)
    per_page = fields.Integer(validate=lambda x: 1 <= x <= 100)
    sort_by = fields.String(validate=lambda x: x in ["relevance", "date", "popularity"])


class ComprehensiveUserSchema(Schema):
    """Comprehensive schema mixing all patterns."""

    username = fields.String(required=True, validate=lambda x: len(x) >= 3)
    email = fields.Email(required=True)

    avatar_url = fields.URL(allow_none=True)

    profile = fields.Nested(UserProfileSchema, allow_none=True)

    addresses = fields.List(fields.Nested(AddressSchema))

    role = fields.String(required=True, validate=lambda x: x in ["admin", "user", "moderator"])

    @validates("username")
    def validate_username(self, value):
        """Custom username validator."""
        if not value[0].isalpha():
            raise ValidationError("Username must start with letter")

    @validates_schema
    def validate_schema(self, data, **kwargs):
        """Schema-level validation."""
        if data.get("role") == "admin" and not data.get("email").endswith("@admin.com"):
            raise ValidationError("Admin must use admin.com email")
