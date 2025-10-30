"""
Django ORM Models Fixture

Tests extraction of:
- Django Model classes (python_orm_models table)
- Model fields with types and constraints (python_orm_fields table)
- ForeignKey, OneToOneField, ManyToManyField relationships (orm_relationships table)
- Through tables for ManyToMany relationships
- GenericForeignKey for polymorphic relationships
- on_delete cascade behavior

This fixture validates that Django ORM extraction has parity with SQLAlchemy extraction.
"""

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType


# ==============================================================================
# Core Models - Basic Relationships
# ==============================================================================

class Organization(models.Model):
    """Organization model - top-level entity."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'organizations'
        ordering = ['-created_at']


class Profile(models.Model):
    """User profile - for OneToOne relationship testing."""
    bio = models.TextField(blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = 'profiles'


class User(models.Model):
    """
    User model demonstrating ForeignKey and OneToOneField.

    Relationships:
    - ForeignKey to Organization (many-to-one)
    - OneToOneField to Profile (one-to-one)
    """
    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)

    # ForeignKey relationship (many users belong to one organization)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='users'
    )

    # OneToOne relationship (one user has one profile)
    profile = models.OneToOneField(
        Profile,
        on_delete=models.CASCADE,
        related_name='user'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['email']),
        ]


# ==============================================================================
# Tag System - ManyToMany Without Through Table
# ==============================================================================

class Tag(models.Model):
    """Tag model for categorization."""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'tags'
        ordering = ['name']


# ==============================================================================
# Post System - ManyToMany With Through Table
# ==============================================================================

class Post(models.Model):
    """
    Post model demonstrating ManyToManyField with and without through tables.

    Relationships:
    - ForeignKey to User (author)
    - ManyToManyField to Tag (with custom through table PostTag)
    - ManyToManyField to User (simple, for likes)
    """
    title = models.CharField(max_length=200)
    content = models.TextField()
    slug = models.SlugField(max_length=200, unique=True)

    # ForeignKey to author
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='posts'
    )

    # ManyToMany with custom through table (explicit join table)
    tags = models.ManyToManyField(
        Tag,
        through='PostTag',
        related_name='posts'
    )

    # ManyToMany without through table (simple relationship)
    liked_by = models.ManyToManyField(
        User,
        related_name='liked_posts',
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published = models.BooleanField(default=False)
    view_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'posts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['published', '-created_at']),
        ]


class PostTag(models.Model):
    """
    Explicit through table for Post-Tag ManyToMany relationship.

    This tests extraction of through= tables with additional fields.
    """
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE
    )
    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE
    )

    # Additional fields on the through table
    created_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='tagged_posts'
    )

    class Meta:
        db_table = 'post_tags'
        unique_together = [['post', 'tag']]
        ordering = ['-created_at']


# ==============================================================================
# Comment System - Self-Referential and Cascade Behavior
# ==============================================================================

class Comment(models.Model):
    """
    Comment model demonstrating:
    - ForeignKey to Post
    - Self-referential ForeignKey (nested comments)
    - Different on_delete behaviors
    """
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='comments'
    )

    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='comments'
    )

    # Self-referential ForeignKey for nested comments
    parent_comment = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )

    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'comments'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post', '-created_at']),
        ]


# ==============================================================================
# Polymorphic Relationships - GenericForeignKey
# ==============================================================================

class Notification(models.Model):
    """
    Notification model using GenericForeignKey for polymorphic relationships.

    Can reference ANY model (Post, Comment, User, etc.) as the target.
    Tests extraction of contenttypes framework integration.
    """
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    # GenericForeignKey fields
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey('content_type', 'object_id')

    notification_type = models.CharField(
        max_length=50,
        choices=[
            ('like', 'Like'),
            ('comment', 'Comment'),
            ('mention', 'Mention'),
            ('follow', 'Follow'),
        ]
    )

    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['content_type', 'object_id']),
        ]


class ActivityLog(models.Model):
    """
    Activity log using GenericForeignKey to track actions on any model.

    Tests multiple GenericForeignKey fields in the same model.
    """
    actor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activities'
    )

    action = models.CharField(
        max_length=50,
        choices=[
            ('create', 'Created'),
            ('update', 'Updated'),
            ('delete', 'Deleted'),
            ('view', 'Viewed'),
        ]
    )

    # GenericForeignKey for the target object
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name='target_activities'
    )
    target_object_id = models.PositiveIntegerField()
    target = GenericForeignKey('target_content_type', 'target_object_id')

    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'activity_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['actor', '-timestamp']),
            models.Index(fields=['target_content_type', 'target_object_id']),
        ]


# ==============================================================================
# Complex Cascade Scenarios
# ==============================================================================

class Team(models.Model):
    """Team model for testing complex relationship cascades."""
    name = models.CharField(max_length=100)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='teams'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'teams'


class TeamMembership(models.Model):
    """
    Through table for User-Team relationship with role.

    Tests extraction of:
    - Multiple ForeignKeys in through table
    - Additional metadata fields (role, joined_at)
    - Unique constraints on relationships
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='team_memberships'
    )

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='memberships'
    )

    role = models.CharField(
        max_length=50,
        choices=[
            ('owner', 'Owner'),
            ('admin', 'Admin'),
            ('member', 'Member'),
        ],
        default='member'
    )

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'team_memberships'
        unique_together = [['user', 'team']]
        indexes = [
            models.Index(fields=['user', 'team']),
        ]


class Project(models.Model):
    """
    Project model demonstrating SET_NULL and PROTECT on_delete behaviors.
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # SET_NULL - if owner deleted, set to null
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='owned_projects'
    )

    # PROTECT - cannot delete team if it has projects
    team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        related_name='projects'
    )

    # CASCADE - delete project when organization deleted
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='projects'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        db_table = 'projects'
        ordering = ['-created_at']


# ==============================================================================
# Field Type Coverage
# ==============================================================================

class FieldTypeCoverage(models.Model):
    """
    Model demonstrating all common Django field types.
    Tests that extractor correctly identifies field types.
    """
    # String fields
    char_field = models.CharField(max_length=100)
    text_field = models.TextField()
    email_field = models.EmailField()
    slug_field = models.SlugField()
    url_field = models.URLField()

    # Numeric fields
    integer_field = models.IntegerField()
    positive_integer_field = models.PositiveIntegerField()
    big_integer_field = models.BigIntegerField()
    decimal_field = models.DecimalField(max_digits=10, decimal_places=2)
    float_field = models.FloatField()

    # Date/Time fields
    date_field = models.DateField()
    time_field = models.TimeField()
    datetime_field = models.DateTimeField()
    duration_field = models.DurationField()

    # Boolean
    boolean_field = models.BooleanField()
    null_boolean_field = models.BooleanField(null=True)

    # Binary
    binary_field = models.BinaryField()

    # JSON
    json_field = models.JSONField(default=dict)

    # File fields
    file_field = models.FileField(upload_to='uploads/')
    image_field = models.ImageField(upload_to='images/')

    # UUID
    uuid_field = models.UUIDField()

    class Meta:
        db_table = 'field_types'
