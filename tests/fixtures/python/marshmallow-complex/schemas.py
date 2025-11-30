"""Complex Marshmallow schemas with advanced validation and nested relationships."""

import enum
import re
from datetime import datetime, timedelta
from decimal import Decimal

from marshmallow import (
    Schema,
    ValidationError,
    fields,
    post_dump,
    post_load,
    pre_load,
    validates,
    validates_schema,
)
from marshmallow.validate import (
    Email,
    Length,
    OneOf,
    Range,
    Regexp,
)
from marshmallow_enum import EnumField


class PhoneNumber(Regexp):
    """Custom phone number validator."""

    default_message = "Invalid phone number format"

    def __init__(self, **kwargs):
        super().__init__(
            r"^\+?1?\d{9,15}$",
            error="Phone number must be 9-15 digits, optionally starting with +",
            **kwargs,
        )


class FutureDateValidator:
    """Validate that date is in the future."""

    def __init__(self, days_ahead=0, error=None):
        self.days_ahead = days_ahead
        self.error = error or f"Date must be at least {days_ahead} days in the future"

    def __call__(self, value):
        min_date = datetime.now() + timedelta(days=self.days_ahead)
        if value < min_date:
            raise ValidationError(self.error)
        return value


class CreditCardValidator:
    """Luhn algorithm for credit card validation."""

    def __call__(self, value):
        number = re.sub(r"[\s-]", "", value)

        if not number.isdigit():
            raise ValidationError("Credit card must contain only digits")

        def luhn_checksum(card_number):
            def digits_of(n):
                return [int(d) for d in str(n)]

            digits = digits_of(card_number)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d * 2))
            return checksum % 10

        if luhn_checksum(number) != 0:
            raise ValidationError("Invalid credit card number")

        return value


class UserRole(enum.Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"
    GUEST = "guest"


class OrderStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class BaseSchema(Schema):
    """Base schema with common fields and configuration."""

    id = fields.UUID(dump_only=True)
    created_at = fields.DateTime(dump_only=True, format="%Y-%m-%dT%H:%M:%S.%fZ")
    updated_at = fields.DateTime(dump_only=True, format="%Y-%m-%dT%H:%M:%S.%fZ")

    class Meta:
        ordered = True
        unknown = "EXCLUDE"
        dateformat = "%Y-%m-%dT%H:%M:%S.%fZ"

    @pre_load
    def process_input(self, data, **kwargs):
        """Pre-process input data."""

        for key, value in data.items():
            if isinstance(value, str):
                data[key] = value.strip()
        return data


class AddressSchema(BaseSchema):
    """Address schema with validation."""

    type = fields.Str(required=True, validate=OneOf(["billing", "shipping", "home", "work"]))
    street = fields.Str(required=True, validate=Length(min=5, max=200))
    street2 = fields.Str(allow_none=True, validate=Length(max=200))
    city = fields.Str(required=True, validate=Length(min=2, max=100))
    state = fields.Str(required=True, validate=Length(equal=2))
    country = fields.Str(required=True, validate=Length(equal=2))
    postal_code = fields.Str(
        required=True, validate=Regexp(r"^\d{5}(-\d{4})?$", error="Invalid postal code format")
    )
    is_default = fields.Bool(default=False)

    @validates_schema
    def validate_address(self, data, **kwargs):
        """Cross-field validation."""
        if data.get("type") == "billing" and not data.get("street2"):
            if "apt" not in data.get("street", "").lower():
                raise ValidationError(
                    "Billing address should include apartment/suite if applicable",
                    field_name="street2",
                )


class PhoneSchema(Schema):
    """Phone number schema with complex validation."""

    type = fields.Str(required=True, validate=OneOf(["mobile", "home", "work", "fax"]))
    number = fields.Str(required=True, validate=PhoneNumber())
    extension = fields.Str(allow_none=True, validate=Length(max=10))
    is_primary = fields.Bool(default=False)
    verified = fields.Bool(dump_only=True)
    verification_code = fields.Str(load_only=True, validate=Length(equal=6))

    @validates("number")
    def validate_number_format(self, value):
        """Additional phone number validation."""

        clean = re.sub(r"[\s\-\(\)]", "", value)

        if clean.startswith("+"):
            if clean[1:3] not in ["1", "44", "33", "49", "81", "86", "91"]:
                raise ValidationError("Unsupported country code")

        return value


class UserProfileSchema(Schema):
    """User profile with nested data."""

    avatar_url = fields.URL(allow_none=True)
    bio = fields.Str(validate=Length(max=500))
    date_of_birth = fields.Date(allow_none=True)
    gender = fields.Str(
        allow_none=True, validate=OneOf(["male", "female", "other", "prefer_not_to_say"])
    )
    preferences = fields.Dict(keys=fields.Str(), values=fields.Raw())
    social_links = fields.Dict(
        keys=fields.Str(validate=OneOf(["twitter", "facebook", "linkedin", "github"])),
        values=fields.URL(),
    )
    languages = fields.List(fields.Str(validate=Length(equal=2)), validate=Length(max=10))
    timezone = fields.Str(
        validate=Regexp(r"^[A-Za-z]+/[A-Za-z_]+$", error="Invalid timezone format")
    )

    @validates("date_of_birth")
    def validate_age(self, value):
        """Ensure user is at least 13 years old."""
        if value:
            age = (datetime.now().date() - value).days / 365.25
            if age < 13:
                raise ValidationError("User must be at least 13 years old")
            if age > 120:
                raise ValidationError("Invalid date of birth")
        return value


class UserSchema(BaseSchema):
    """Complex user schema with nested relationships."""

    username = fields.Str(
        required=True,
        validate=[
            Length(min=3, max=30),
            Regexp(r"^[a-zA-Z0-9_]+$", error="Username must be alphanumeric"),
        ],
    )
    email = fields.Email(required=True, validate=Email())
    password = fields.Str(
        load_only=True,
        required=True,
        validate=[
            Length(min=8, max=128),
            Regexp(
                r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]",
                error="Password must contain uppercase, lowercase, digit and special character",
            ),
        ],
    )
    password_confirmation = fields.Str(load_only=True, required=True)
    first_name = fields.Str(validate=Length(max=50))
    last_name = fields.Str(validate=Length(max=50))
    full_name = fields.Method("get_full_name", dump_only=True)

    role = EnumField(UserRole, by_value=True, required=True)
    is_active = fields.Bool(default=True)
    email_verified = fields.Bool(dump_only=True)
    last_login = fields.DateTime(dump_only=True)

    profile = fields.Nested(UserProfileSchema, allow_none=True)
    addresses = fields.List(fields.Nested(AddressSchema), validate=Length(max=5))
    phone_numbers = fields.List(fields.Nested(PhoneSchema), validate=Length(max=3))

    manager = fields.Nested("UserSchema", only=["id", "username", "email"], dump_only=True)
    subordinates = fields.List(
        fields.Nested("UserSchema", only=["id", "username", "full_name"]), dump_only=True
    )

    order_count = fields.Method("get_order_count", dump_only=True)
    total_spent = fields.Method("get_total_spent", dump_only=True)

    def get_full_name(self, obj):
        """Compute full name."""
        if obj.first_name and obj.last_name:
            return f"{obj.first_name} {obj.last_name}"
        return obj.username

    def get_order_count(self, obj):
        """Get user's order count."""
        return len(obj.orders) if hasattr(obj, "orders") else 0

    def get_total_spent(self, obj):
        """Calculate total amount spent."""
        if hasattr(obj, "orders"):
            return sum(order.total for order in obj.orders)
        return 0

    @validates("email")
    def validate_email_domain(self, value):
        """Custom email validation."""

        disposable_domains = ["tempmail.com", "throwaway.email", "guerrillamail.com"]
        domain = value.split("@")[1].lower()
        if domain in disposable_domains:
            raise ValidationError("Disposable email addresses are not allowed")
        return value

    @validates_schema
    def validate_passwords_match(self, data, **kwargs):
        """Ensure passwords match."""
        if "password" in data and "password_confirmation" in data:
            if data["password"] != data["password_confirmation"]:
                raise ValidationError("Passwords do not match", field_name="password_confirmation")

    @validates_schema(skip_on_field_errors=True)
    def validate_user_hierarchy(self, data, **kwargs):
        """Validate manager-subordinate relationships."""
        if "manager_id" in data and "id" in data and data["manager_id"] == data["id"]:
            raise ValidationError("User cannot be their own manager", field_name="manager_id")

    @pre_load
    def normalize_email(self, data, **kwargs):
        """Normalize email to lowercase."""
        if "email" in data:
            data["email"] = data["email"].lower()
        return data

    @post_load
    def make_user(self, data, **kwargs):
        """Create user object after loading."""

        if "password" in data:
            data["password_hash"] = self.hash_password(data.pop("password"))
            data.pop("password_confirmation", None)
        return data

    def hash_password(self, password):
        """Hash password (simplified)."""
        import hashlib

        return hashlib.sha256(password.encode()).hexdigest()


class ProductSchema(BaseSchema):
    """Product schema with complex validation."""

    sku = fields.Str(
        required=True,
        validate=Regexp(
            r"^[A-Z]{3}-[A-Z]{3,5}-\d{5}$", error="SKU must match format: XXX-XXX-00000"
        ),
    )
    name = fields.Str(required=True, validate=Length(min=3, max=200))
    description = fields.Str(validate=Length(max=5000))

    price = fields.Decimal(required=True, places=2, validate=Range(min=0, max=999999.99))
    cost = fields.Decimal(required=True, places=2, validate=Range(min=0, max=999999.99))
    profit_margin = fields.Method("calculate_profit_margin", dump_only=True)

    weight = fields.Float(validate=Range(min=0))
    dimensions = fields.Dict(
        keys=fields.Str(validate=OneOf(["length", "width", "height"])),
        values=fields.Float(validate=Range(min=0)),
    )

    status = fields.Str(
        validate=OneOf(["active", "discontinued", "out_of_stock"]), default="active"
    )

    tags = fields.List(fields.Str(validate=Length(max=30)), validate=Length(max=20))

    metadata = fields.Dict()

    category = fields.Nested("CategorySchema", only=["id", "name", "slug"])
    brand = fields.Nested("BrandSchema", only=["id", "name"])

    stock_levels = fields.Method("get_stock_levels", dump_only=True)
    total_stock = fields.Method("get_total_stock", dump_only=True)

    average_rating = fields.Float(dump_only=True)
    review_count = fields.Int(dump_only=True)

    def calculate_profit_margin(self, obj):
        """Calculate profit margin percentage."""
        if obj.cost and obj.price:
            margin = ((obj.price - obj.cost) / obj.price) * 100
            return round(margin, 2)
        return 0

    def get_stock_levels(self, obj):
        """Get stock levels per warehouse."""
        if hasattr(obj, "warehouse_associations"):
            return [
                {"warehouse_id": wa.warehouse_id, "quantity": wa.quantity, "location": wa.location}
                for wa in obj.warehouse_associations
            ]
        return []

    def get_total_stock(self, obj):
        """Calculate total stock across all warehouses."""
        if hasattr(obj, "warehouse_associations"):
            return sum(wa.quantity for wa in obj.warehouse_associations)
        return 0

    @validates("price")
    def validate_price(self, value):
        """Ensure price is reasonable."""
        if value > Decimal("10000"):
            raise ValidationError("Price seems unusually high. Please confirm.")
        return value

    @validates_schema
    def validate_pricing(self, data, **kwargs):
        """Ensure price is higher than cost."""
        if "price" in data and "cost" in data:
            if data["price"] <= data["cost"]:
                raise ValidationError("Price must be higher than cost", field_name="price")

            margin = ((data["price"] - data["cost"]) / data["price"]) * 100
            if margin < 10:
                raise ValidationError("Profit margin must be at least 10%", field_name="price")

    @validates_schema
    def validate_dimensions(self, data, **kwargs):
        """Ensure all dimensions are provided if any are."""
        dims = data.get("dimensions", {})
        if dims:
            required_dims = {"length", "width", "height"}
            if set(dims.keys()) != required_dims:
                raise ValidationError(
                    f"All dimensions required: {required_dims}", field_name="dimensions"
                )


class OrderItemSchema(Schema):
    """Order item schema."""

    product = fields.Nested(ProductSchema, only=["id", "sku", "name"])
    quantity = fields.Int(required=True, validate=Range(min=1, max=100))
    unit_price = fields.Decimal(places=2, dump_only=True)
    subtotal = fields.Method("calculate_subtotal", dump_only=True)
    discount_amount = fields.Decimal(places=2, default=0)
    tax_amount = fields.Decimal(places=2, default=0)
    total = fields.Method("calculate_total", dump_only=True)

    def calculate_subtotal(self, obj):
        """Calculate subtotal."""
        return obj.quantity * obj.unit_price

    def calculate_total(self, obj):
        """Calculate total with tax and discount."""
        subtotal = obj.quantity * obj.unit_price
        return subtotal - obj.discount_amount + obj.tax_amount


class OrderSchema(BaseSchema):
    """Complex order schema with nested items and validation."""

    user = fields.Nested(UserSchema, only=["id", "username", "email"], dump_only=True)
    order_number = fields.Str(dump_only=True)
    status = EnumField(OrderStatus, by_value=True, required=True)

    items = fields.List(
        fields.Nested(OrderItemSchema), required=True, validate=Length(min=1, max=50)
    )

    shipping_address = fields.Nested(AddressSchema, required=True)
    billing_address = fields.Nested(AddressSchema, required=True)

    subtotal = fields.Decimal(places=2, dump_only=True)
    shipping_cost = fields.Decimal(places=2, default=0)
    tax_amount = fields.Decimal(places=2, default=0)
    discount_amount = fields.Decimal(places=2, default=0)
    total = fields.Decimal(places=2, dump_only=True)

    payment_method = fields.Str(
        required=True,
        validate=OneOf(["credit_card", "debit_card", "paypal", "stripe", "bank_transfer"]),
    )

    credit_card_number = fields.Str(load_only=True, validate=[CreditCardValidator()])

    notes = fields.Str(validate=Length(max=500))

    shipped_at = fields.DateTime(allow_none=True)
    delivered_at = fields.DateTime(allow_none=True)

    tracking_number = fields.Str(allow_none=True)
    carrier = fields.Str(allow_none=True, validate=OneOf(["ups", "fedex", "usps", "dhl"]))

    @validates_schema
    def validate_addresses(self, data, **kwargs):
        """Validate shipping and billing addresses."""
        if "shipping_address" in data and "billing_address" in data:
            if data["shipping_address"].get("type") != "shipping":
                raise ValidationError(
                    'Address type must be "shipping"', field_name="shipping_address"
                )
            if data["billing_address"].get("type") != "billing":
                raise ValidationError(
                    'Address type must be "billing"', field_name="billing_address"
                )

    @validates_schema
    def validate_payment(self, data, **kwargs):
        """Validate payment information."""
        if data.get("payment_method") in ["credit_card", "debit_card"]:
            if not data.get("credit_card_number"):
                raise ValidationError(
                    "Credit card number required for card payments", field_name="credit_card_number"
                )

    @validates_schema
    def validate_status_transitions(self, data, **kwargs):
        """Validate status transitions."""

    @post_dump
    def calculate_totals(self, data, **kwargs):
        """Calculate order totals after dumping."""
        if "items" in data:
            subtotal = sum(item.get("subtotal", 0) for item in data["items"])
            data["subtotal"] = subtotal
            data["total"] = (
                subtotal
                + data.get("shipping_cost", 0)
                + data.get("tax_amount", 0)
                - data.get("discount_amount", 0)
            )
        return data


class CategorySchema(BaseSchema):
    name = fields.Str(required=True, validate=Length(min=2, max=100))
    slug = fields.Str(required=True, validate=Regexp(r"^[a-z0-9-]+$"))
    parent = fields.Nested("CategorySchema", only=["id", "name"], allow_none=True)


class BrandSchema(BaseSchema):
    name = fields.Str(required=True, validate=Length(min=2, max=100))
    logo = fields.URL(allow_none=True)
