"""
Django admin configuration for realworld_project.

Test fixture for extract_django_admin() - covers ModelAdmin configurations,
list_display, list_filter, search_fields, readonly_fields, custom actions.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models.accounts import Account
from .models.article import Article
from .models.user import User


# 1. Basic ModelAdmin - minimal configuration
@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """Basic admin for Article model."""
    list_display = ['title', 'author', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'content']


# 2. ModelAdmin with readonly fields (security: prevent mass assignment)
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """User admin with readonly fields for security."""
    list_display = ['username', 'email', 'is_staff', 'is_active', 'date_joined']
    list_filter = ['is_staff', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    readonly_fields = ['date_joined', 'last_login', 'password']  # Prevent editing sensitive fields


# 3. ModelAdmin with custom actions
@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """Account admin with custom bulk actions."""
    list_display = ['account_id', 'user', 'balance', 'status', 'is_verified']
    list_filter = ['status', 'is_verified', 'created_at']
    search_fields = ['account_id', 'user__username', 'user__email']
    readonly_fields = ['account_id', 'created_at']

    @admin.action(description='Activate selected accounts')
    def activate_accounts(self, request, queryset):
        """Custom action: activate accounts in bulk."""
        queryset.update(status='active')

    @admin.action(description='Suspend selected accounts')
    def suspend_accounts(self, request, queryset):
        """Custom action: suspend accounts in bulk."""
        queryset.update(status='suspended')

    # Register custom actions
    actions = [activate_accounts, suspend_accounts]


# 4. ModelAdmin with extensive configuration (all fields)
class CommentAdmin(admin.ModelAdmin):
    """Comment admin with comprehensive configuration."""
    list_display = ['id', 'article', 'author', 'status', 'created_at', 'moderation_status']
    list_filter = ['status', 'moderation_status', 'created_at', 'is_spam']
    search_fields = ['content', 'author__username', 'article__title']
    readonly_fields = ['created_at', 'updated_at', 'ip_address', 'user_agent']

    @admin.action(description='Mark as spam')
    def mark_as_spam(self, request, queryset):
        """Custom action: mark comments as spam."""
        queryset.update(is_spam=True, moderation_status='rejected')

    @admin.action(description='Approve comments')
    def approve_comments(self, request, queryset):
        """Custom action: approve comments."""
        queryset.update(moderation_status='approved', is_spam=False)

    actions = [mark_as_spam, approve_comments]

    def get_queryset(self, request):
        """Custom queryset for admin."""
        qs = super().get_queryset(request)
        # Show all comments including soft-deleted ones for admins
        return qs.all()


# Note: CommentAdmin is NOT registered with @admin.register,
# so it won't be linked to a model via admin.site.register()


# 5. ModelAdmin without any configuration (minimal/insecure)
class TagAdmin(admin.ModelAdmin):
    """Minimal admin - no list_display, no readonly_fields (SECURITY RISK)."""
    pass  # No configuration - all fields editable, no search, no filters


# 6. Register Tag model separately (testing admin.site.register pattern)
admin.site.register(Tag, TagAdmin)
