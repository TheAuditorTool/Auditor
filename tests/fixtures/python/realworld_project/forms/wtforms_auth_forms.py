"""
WTForms forms for authentication and user management.

Test fixture for extract_wtforms_forms() and extract_wtforms_fields().
Covers FlaskForm, Form, validators, and custom validators.
"""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError


class LoginForm(FlaskForm):
    """Basic login form with email/password."""

    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Sign In")


class RegistrationForm(FlaskForm):
    """User registration with custom username validation."""

    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    password_confirm = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password")]
    )
    submit = SubmitField("Register")

    def validate_username(self, field):
        """Custom validator: check for XSS patterns."""
        if "<" in field.data or ">" in field.data:
            raise ValidationError("Username contains invalid characters")


class ProfileForm(FlaskForm):
    """User profile form with optional fields."""

    display_name = StringField("Display Name")
    bio = TextAreaField("Bio")
    location = StringField("Location")
    website = StringField("Website")
    submit = SubmitField("Update Profile")


class PasswordChangeForm(FlaskForm):
    """Password change with complex validation."""

    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(min=8)])
    new_password_confirm = PasswordField(
        "Confirm New Password", validators=[DataRequired(), EqualTo("new_password")]
    )
    submit = SubmitField("Change Password")

    def validate_new_password(self, field):
        """Custom validator: require digit in password."""
        if not any(char.isdigit() for char in field.data):
            raise ValidationError("Password must contain at least one digit")

    def validate_current_password(self, field):
        """Custom validator: check current password (simulated)."""

        pass


class ArticleForm(FlaskForm):
    """Article creation with title/content validation."""

    title = StringField("Title", validators=[DataRequired(), Length(min=5, max=200)])
    slug = StringField("Slug", validators=[DataRequired(), Length(min=5, max=200)])
    content = TextAreaField("Content", validators=[DataRequired(), Length(min=100)])
    category = SelectField("Category", choices=[("tech", "Technology"), ("business", "Business")])
    published = BooleanField("Publish Now")
    submit = SubmitField("Save Article")

    def validate_title(self, field):
        """Custom validator: check for script tags."""
        if "<script>" in field.data.lower():
            raise ValidationError("Title contains dangerous HTML")

    def validate_slug(self, field):
        """Custom validator: ensure slug is URL-safe."""
        if not field.data.replace("-", "").replace("_", "").isalnum():
            raise ValidationError("Slug must be URL-safe (alphanumeric, hyphens, underscores)")


class SearchForm(FlaskForm):
    """Search form with NO required fields - validation bypass risk."""

    query = StringField("Search Query")
    category = SelectField("Category", choices=[("all", "All"), ("articles", "Articles")])
    author = StringField("Author")
    submit = SubmitField("Search")


class CommentForm(FlaskForm):
    """Comment form without length limits."""

    author_name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    body = TextAreaField("Comment", validators=[DataRequired()])
    submit = SubmitField("Post Comment")


class AdminUserForm(FlaskForm):
    """Admin form for user management."""

    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    is_admin = BooleanField("Admin Privileges")
    is_active = BooleanField("Active")
    role = SelectField(
        "Role", choices=[("user", "User"), ("moderator", "Moderator"), ("admin", "Admin")]
    )
    submit = SubmitField("Save User")


class PaymentForm(FlaskForm):
    """Payment form with amount validation."""

    card_number = StringField("Card Number", validators=[DataRequired(), Length(min=16, max=16)])
    amount = IntegerField("Amount", validators=[DataRequired()])
    currency = SelectField("Currency", choices=[("USD", "US Dollar"), ("EUR", "Euro")])
    submit = SubmitField("Process Payment")

    def validate_amount(self, field):
        """Custom validator: check amount is positive."""
        if field.data <= 0:
            raise ValidationError("Amount must be greater than zero")

    def validate_card_number(self, field):
        """Custom validator: basic Luhn check (simulated)."""
        if not field.data.isdigit():
            raise ValidationError("Card number must be numeric")


class ComprehensiveForm(FlaskForm):
    """Complex form demonstrating all WTForms patterns."""

    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])

    bio = TextAreaField("Bio", validators=[Optional(), Length(max=500)])
    age = IntegerField("Age", validators=[Optional()])

    terms_accepted = BooleanField("Accept Terms", validators=[DataRequired()])
    newsletter = BooleanField("Subscribe to Newsletter")

    country = SelectField("Country", choices=[("US", "United States"), ("UK", "United Kingdom")])

    submit = SubmitField("Submit")

    def validate_username(self, field):
        """Custom validator: username uniqueness (simulated)."""
        pass

    def validate_email(self, field):
        """Custom validator: email domain check."""
        pass
