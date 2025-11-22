"""Marshmallow schema extraction test fixture."""

from marshmallow import Schema, fields, validate, validates, ValidationError
from marshmallow.validate import Length, Range, Email


class UserSchema(Schema):
    """User schema with validation."""

    class Meta:
        fields = ('id', 'username', 'email', 'age', 'created_at')
        ordered = True

    id = fields.Integer(dump_only=True)
    username = fields.String(required=True, validate=Length(min=3, max=80))
    email = fields.Email(required=True, validate=Email())
    age = fields.Integer(validate=Range(min=0, max=150))
    created_at = fields.DateTime(dump_only=True)

    @validates('username')
    def validate_username(self, value):
        """Custom username validator."""
        if value.lower() in ['admin', 'root']:
            raise ValidationError('Reserved username')


class AddressSchema(Schema):
    """Address schema without Meta class."""
    street = fields.String(required=True)
    city = fields.String(required=True)
    state = fields.String(validate=Length(equal=2))
    zip_code = fields.String(validate=validate.Regexp(r'^\d{5}$'))
    country = fields.String(default='US')


class OrderSchema(Schema):
    """Order schema with nested schemas."""

    class Meta:
        fields = ('id', 'user', 'items', 'total', 'status')

    id = fields.UUID(dump_only=True)
    user = fields.Nested(UserSchema, required=True)
    items = fields.List(fields.Dict())
    total = fields.Decimal(places=2, required=True)
    status = fields.String(
        validate=validate.OneOf(['pending', 'processing', 'shipped', 'delivered']),
        default='pending'
    )