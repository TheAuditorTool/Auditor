"""
WTForms forms for authentication and user management.

Test fixture for extract_wtforms_forms() and extract_wtforms_fields().
Covers FlaskForm, Form, validators, and custom validators.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, SelectField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, ValidationError


# 1. Basic login form with validators
class LoginForm(FlaskForm):
    """Basic login form with email/password."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


# 2. Registration form with custom validator
class RegistrationForm(FlaskForm):
    """User registration with custom username validation."""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    password_confirm = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, field):
        """Custom validator: check for XSS patterns."""
        if '<' in field.data or '>' in field.data:
            raise ValidationError('Username contains invalid characters')


# 3. Profile form with optional fields (SECURITY RISK: no validation on bio)
class ProfileForm(FlaskForm):
    """User profile form with optional fields."""
    display_name = StringField('Display Name')
    bio = TextAreaField('Bio')  # NO validators - XSS risk
    location = StringField('Location')
    website = StringField('Website')
    submit = SubmitField('Update Profile')


# 4. Password change form with multiple custom validators
class PasswordChangeForm(FlaskForm):
    """Password change with complex validation."""
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=8)])
    new_password_confirm = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Change Password')

    def validate_new_password(self, field):
        """Custom validator: require digit in password."""
        if not any(char.isdigit() for char in field.data):
            raise ValidationError('Password must contain at least one digit')

    def validate_current_password(self, field):
        """Custom validator: check current password (simulated)."""
        # In real app, would check against database
        pass


# 5. Article form with comprehensive validation
class ArticleForm(FlaskForm):
    """Article creation with title/content validation."""
    title = StringField('Title', validators=[DataRequired(), Length(min=5, max=200)])
    slug = StringField('Slug', validators=[DataRequired(), Length(min=5, max=200)])
    content = TextAreaField('Content', validators=[DataRequired(), Length(min=100)])
    category = SelectField('Category', choices=[('tech', 'Technology'), ('business', 'Business')])
    published = BooleanField('Publish Now')
    submit = SubmitField('Save Article')

    def validate_title(self, field):
        """Custom validator: check for script tags."""
        if '<script>' in field.data.lower():
            raise ValidationError('Title contains dangerous HTML')

    def validate_slug(self, field):
        """Custom validator: ensure slug is URL-safe."""
        if not field.data.replace('-', '').replace('_', '').isalnum():
            raise ValidationError('Slug must be URL-safe (alphanumeric, hyphens, underscores)')


# 6. Search form with all optional fields (SECURITY RISK: validation bypass)
class SearchForm(FlaskForm):
    """Search form with NO required fields - validation bypass risk."""
    query = StringField('Search Query')  # NO DataRequired - allows empty search
    category = SelectField('Category', choices=[('all', 'All'), ('articles', 'Articles')])
    author = StringField('Author')
    submit = SubmitField('Search')


# 7. Comment form without max_length (DoS RISK)
class CommentForm(FlaskForm):
    """Comment form without length limits."""
    author_name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    body = TextAreaField('Comment', validators=[DataRequired()])  # NO Length validator - DoS risk
    submit = SubmitField('Post Comment')


# 8. Admin user form with sensitive fields
class AdminUserForm(FlaskForm):
    """Admin form for user management."""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    is_admin = BooleanField('Admin Privileges')  # Sensitive field
    is_active = BooleanField('Active')
    role = SelectField('Role', choices=[('user', 'User'), ('moderator', 'Moderator'), ('admin', 'Admin')])
    submit = SubmitField('Save User')


# 9. Payment form with sensitive fields and custom validator
class PaymentForm(FlaskForm):
    """Payment form with amount validation."""
    card_number = StringField('Card Number', validators=[DataRequired(), Length(min=16, max=16)])
    amount = IntegerField('Amount', validators=[DataRequired()])
    currency = SelectField('Currency', choices=[('USD', 'US Dollar'), ('EUR', 'Euro')])
    submit = SubmitField('Process Payment')

    def validate_amount(self, field):
        """Custom validator: check amount is positive."""
        if field.data <= 0:
            raise ValidationError('Amount must be greater than zero')

    def validate_card_number(self, field):
        """Custom validator: basic Luhn check (simulated)."""
        if not field.data.isdigit():
            raise ValidationError('Card number must be numeric')


# 10. Comprehensive form mixing all patterns
class ComprehensiveForm(FlaskForm):
    """Complex form demonstrating all WTForms patterns."""
    # Required fields with inline validators
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])

    # Optional fields
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=500)])
    age = IntegerField('Age', validators=[Optional()])

    # Boolean fields
    terms_accepted = BooleanField('Accept Terms', validators=[DataRequired()])
    newsletter = BooleanField('Subscribe to Newsletter')

    # Select field
    country = SelectField('Country', choices=[('US', 'United States'), ('UK', 'United Kingdom')])

    submit = SubmitField('Submit')

    def validate_username(self, field):
        """Custom validator: username uniqueness (simulated)."""
        pass

    def validate_email(self, field):
        """Custom validator: email domain check."""
        pass


# Security Patterns Demonstrated:
# - LoginForm: Good validation (DataRequired, Email, Length)
# - RegistrationForm: Custom XSS validator on username
# - ProfileForm: RISK - TextAreaField with NO validators (XSS)
# - PasswordChangeForm: Multiple custom validators (password strength)
# - ArticleForm: Custom validators for title (script tags) and slug (URL-safe)
# - SearchForm: RISK - All optional fields (validation bypass)
# - CommentForm: RISK - NO Length validator on body (DoS)
# - AdminUserForm: Sensitive is_admin field (privilege escalation risk)
# - PaymentForm: Custom validators for amount/card_number
# - ComprehensiveForm: Mix of required/optional, custom validators
