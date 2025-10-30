"""
Django REST Framework serializers for user management and articles.

Test fixture for extract_drf_serializers() and extract_drf_serializer_fields().
Covers ModelSerializer, Serializer, read_only/write_only fields, and custom validators.
"""

from rest_framework import serializers
from ..models.user_models import User, Article


# 1. Basic Serializer with various field types
class UserRegistrationSerializer(serializers.Serializer):
    """Basic user registration serializer."""
    username = serializers.CharField(required=True, max_length=50)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True, min_length=8)
    confirm_password = serializers.CharField(required=True, write_only=True)
    age = serializers.IntegerField(allow_null=True)
    is_active = serializers.BooleanField(default=True)

    def validate_username(self, value):
        """Custom validator for username (XSS check)."""
        if '<' in value or '>' in value:
            raise serializers.ValidationError("Username contains invalid characters")
        return value

    def validate(self, data):
        """Schema-level validation."""
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError("Passwords do not match")
        return data


# 2. ModelSerializer with Meta (read_only_fields)
class UserSerializer(serializers.ModelSerializer):
    """User serializer with Meta.model."""
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'created_at', 'is_active']
        read_only_fields = ['id', 'created_at']


# 3. ModelSerializer without read_only_fields (SECURITY RISK: mass assignment)
class VulnerableUserSerializer(serializers.ModelSerializer):
    """User serializer WITHOUT read_only_fields - mass assignment risk."""

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_admin']  # RISK: is_admin is writable!


# 4. Serializer with nested serializers
class AuthorSerializer(serializers.ModelSerializer):
    """Nested author serializer."""
    article_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'article_count']
        read_only_fields = ['id']

    def get_article_count(self, obj):
        """Calculate article count."""
        return obj.articles.count()


class ArticleSerializer(serializers.ModelSerializer):
    """Article with nested author."""
    author = AuthorSerializer(read_only=True)
    author_id = serializers.IntegerField(write_only=True)
    tags = serializers.ListField(child=serializers.CharField())

    class Meta:
        model = Article
        fields = ['id', 'title', 'slug', 'content', 'author', 'author_id', 'tags']
        read_only_fields = ['id', 'slug']

    def validate_title(self, value):
        """Custom title validator (XSS check)."""
        if '<script>' in value.lower():
            raise serializers.ValidationError("Title contains dangerous HTML")
        return value


# 5. Serializer with source= parameter
class UserProfileSerializer(serializers.ModelSerializer):
    """User profile with field mapping using source."""
    display_name = serializers.CharField(source='username', read_only=True)
    email_address = serializers.EmailField(source='email')
    member_since = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = User
        fields = ['display_name', 'email_address', 'member_since']
        read_only_fields = ['display_name', 'member_since']


# 6. Serializer with all optional fields (SECURITY RISK: no validation)
class OptionalMetadataSerializer(serializers.Serializer):
    """All optional fields - validation bypass risk."""
    key = serializers.CharField()
    value = serializers.CharField()
    created_by = serializers.IntegerField()
    # NO required=True on any field = validation bypass


# 7. Serializer with write_only sensitive fields
class PasswordChangeSerializer(serializers.Serializer):
    """Password change with write_only fields."""
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)

    def validate_new_password(self, value):
        """Validate new password strength."""
        if not any(char.isdigit() for char in value):
            raise serializers.ValidationError("Password must contain at least one number")
        return value


# 8. ModelSerializer with PrimaryKeyRelatedField
class CommentSerializer(serializers.ModelSerializer):
    """Comment with related fields."""
    article = serializers.PrimaryKeyRelatedField(queryset=Article.objects.all())
    author = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = None  # Assume Comment model exists
        fields = ['id', 'article', 'author', 'body', 'created_at']
        read_only_fields = ['id', 'author', 'created_at']


# 9. Serializer with allow_null on sensitive field (SECURITY RISK)
class PaymentSerializer(serializers.Serializer):
    """Payment serializer with allow_null on amount (RISK)."""
    user_id = serializers.IntegerField(required=True)
    amount = serializers.DecimalField(required=True, max_digits=10, decimal_places=2, allow_null=True)  # RISK!
    currency = serializers.CharField(required=True)
    payment_method = serializers.CharField(allow_null=True)  # RISK: null payment method


# 10. Complex serializer mixing all patterns
class ComprehensiveArticleSerializer(serializers.ModelSerializer):
    """Complex serializer demonstrating all DRF patterns."""
    # Read-only fields
    id = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    # Write-only fields
    author_id = serializers.IntegerField(write_only=True, required=True)

    # Nested serializer
    author = AuthorSerializer(read_only=True)

    # Field with source
    article_title = serializers.CharField(source='title')

    # Custom validator
    slug = serializers.SlugField()

    class Meta:
        model = Article
        fields = ['id', 'article_title', 'slug', 'content', 'author', 'author_id', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_slug(self, value):
        """Ensure slug is unique."""
        if Article.objects.filter(slug=value).exists():
            raise serializers.ValidationError("Article with this slug already exists")
        return value

    def validate_content(self, value):
        """Validate content length."""
        if len(value) < 100:
            raise serializers.ValidationError("Article content too short (min 100 chars)")
        return value
