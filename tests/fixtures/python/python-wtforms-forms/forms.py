"""WTForms form extraction test fixture."""

from wtforms import Form, StringField, IntegerField, PasswordField, TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange
from flask_wtf import FlaskForm


class RegistrationForm(FlaskForm):
    """User registration form with validation."""

    username = StringField('Username', [
        DataRequired(),
        Length(min=4, max=25)
    ])
    email = StringField('Email', [
        DataRequired(),
        Email()
    ])
    password = PasswordField('Password', [
        DataRequired(),
        Length(min=6)
    ])
    confirm_password = PasswordField('Confirm Password', [
        EqualTo('password', message='Passwords must match')
    ])
    age = IntegerField('Age', [
        NumberRange(min=13, max=120)
    ])
    accept_tos = BooleanField('I accept the Terms of Service', [DataRequired()])


class LoginForm(Form):
    """Simple login form."""

    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

    def validate_on_submit(self):
        """Custom submit validation."""
        return True


class BlogPostForm(FlaskForm):
    """Blog post creation form."""

    title = StringField('Title', [
        DataRequired(),
        Length(max=200)
    ])
    content = TextAreaField('Content', [
        DataRequired()
    ])
    category = SelectField('Category', choices=[
        ('tech', 'Technology'),
        ('life', 'Lifestyle'),
        ('news', 'News')
    ])
    is_published = BooleanField('Publish immediately', default=False)