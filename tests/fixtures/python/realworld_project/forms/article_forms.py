"""
Django forms for article management.

Test fixture for extract_django_forms() and extract_django_form_fields().
Covers: Form, ModelForm, field types, validators, max_length, required/optional.
"""

from django import forms
from django.core.exceptions import ValidationError

from ..models.article import Article
from ..models.user import User


# 1. Simple Form with basic fields (no ModelForm)
class ArticleSearchForm(forms.Form):
    """Search form - regular Form (not ModelForm)."""
    query = forms.CharField(max_length=200, required=True)
    category = forms.ChoiceField(
        choices=[('all', 'All'), ('tech', 'Technology'), ('news', 'News')],
        required=False
    )
    published_after = forms.DateField(required=False)

    def clean_query(self):
        """Custom validator for query field."""
        query = self.cleaned_data.get('query')
        if query and len(query) < 3:
            raise ValidationError("Query must be at least 3 characters")
        return query


# 2. ModelForm with custom validators
class ArticleForm(forms.ModelForm):
    """ModelForm for creating/editing articles."""

    # Extra non-model field
    notify_author = forms.BooleanField(required=False)

    class Meta:
        model = Article
        fields = ['title', 'content', 'status', 'tags', 'featured']

    title = forms.CharField(max_length=255, required=True)
    content = forms.CharField(widget=forms.Textarea, required=True)
    status = forms.ChoiceField(
        choices=[('draft', 'Draft'), ('published', 'Published'), ('archived', 'Archived')],
        required=True
    )
    tags = forms.CharField(max_length=500, required=False)
    featured = forms.BooleanField(required=False)

    def clean_title(self):
        """Custom validator - check title uniqueness."""
        title = self.cleaned_data.get('title')
        if Article.objects.filter(title=title).exists():
            raise ValidationError("Article with this title already exists")
        return title

    def clean_content(self):
        """Custom validator - minimum content length."""
        content = self.cleaned_data.get('content')
        if content and len(content) < 50:
            raise ValidationError("Content must be at least 50 characters")
        return content

    def clean(self):
        """Custom form-level validator."""
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        content = cleaned_data.get('content')

        if status == 'published' and not content:
            raise ValidationError("Published articles must have content")

        return cleaned_data


# 3. ModelForm without custom validators (SECURITY RISK)
class QuickArticleForm(forms.ModelForm):
    """Simple ModelForm without validation - direct DB write risk."""

    class Meta:
        model = Article
        fields = ['title', 'content']

    # No clean() methods - accepts any input


# 4. Form with unbounded fields (DoS RISK)
class ArticleFeedbackForm(forms.Form):
    """Feedback form with unbounded text field - DoS risk."""
    name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    feedback = forms.CharField(widget=forms.Textarea)  # NO max_length - DoS risk!
    rating = forms.IntegerField(required=False)


# 5. Form with many optional fields
class ArticleFilterForm(forms.Form):
    """Filter form - mostly optional fields."""
    author_id = forms.IntegerField(required=False)
    status = forms.ChoiceField(
        choices=[('all', 'All'), ('draft', 'Draft'), ('published', 'Published')],
        required=False
    )
    start_date = forms.DateField(required=False)
    end_date = forms.DateField(required=False)
    tag = forms.CharField(max_length=50, required=False)
    search_term = forms.CharField(max_length=100, required=False)


# 6. ModelForm with all custom validators
class ArticleModerationForm(forms.ModelForm):
    """Admin moderation form - extensive validation."""

    class Meta:
        model = Article
        fields = ['status', 'featured', 'moderation_notes']

    status = forms.ChoiceField(
        choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        required=True
    )
    featured = forms.BooleanField(required=False)
    moderation_notes = forms.CharField(max_length=1000, required=False, widget=forms.Textarea)
    moderator_email = forms.EmailField(required=True)

    def clean_status(self):
        """Validator for status field."""
        status = self.cleaned_data.get('status')
        if status == 'rejected' and not self.cleaned_data.get('moderation_notes'):
            raise ValidationError("Rejected articles must have moderation notes")
        return status

    def clean_moderator_email(self):
        """Validator for moderator_email field."""
        email = self.cleaned_data.get('moderator_email')
        # Check if moderator exists
        if not User.objects.filter(email=email, is_staff=True).exists():
            raise ValidationError("Moderator email must belong to a staff user")
        return email

    def clean(self):
        """Form-level validator."""
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        featured = cleaned_data.get('featured')

        if featured and status != 'approved':
            raise ValidationError("Only approved articles can be featured")

        return cleaned_data
