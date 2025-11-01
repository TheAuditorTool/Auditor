"""
Django blog platform - Real-world signals, managers, and querysets.

Complete blog system showing:
- Signal chains for notifications and caching
- Custom managers for published/draft content  
- QuerySets for complex filtering
- Manager/QuerySet integration with as_manager()
"""
from django.db import models
from django.dispatch import Signal, receiver
from django.contrib.auth.models import User
from django.db.models import Manager, QuerySet, Q, Count

# Custom signals
post_published = Signal(providing_args=["post", "author"])
comment_approved = Signal(providing_args=["comment", "post"])  
user_activity = Signal(providing_args=["user", "action", "target"])

# QuerySets with business logic
class PostQuerySet(QuerySet):
    def published(self):
        return self.filter(status='published', published_at__isnull=False)
    
    def drafts(self):
        return self.filter(status='draft')
    
    def by_author(self, author):
        return self.filter(author=author)
    
    def with_comments(self):
        return self.annotate(comment_count=Count('comments')).filter(comment_count__gt=0)
    
    def popular(self, min_views=100):
        return self.filter(view_count__gte=min_views).order_by('-view_count')

class CommentQuerySet(QuerySet):
    def approved(self):
        return self.filter(is_approved=True, is_spam=False)
    
    def pending(self):
        return self.filter(is_approved=False, is_spam=False)
    
    def for_post(self, post):
        return self.filter(post=post)

# Custom managers
class PublishedManager(Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status='published')
    
    def recent(self, days=7):
        from datetime import timedelta
        from django.utils import timezone
        cutoff = timezone.now() - timedelta(days=days)
        return self.get_queryset().filter(published_at__gte=cutoff)

# Models using managers and querysets  
class Post(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField()
    status = models.CharField(max_length=20)
    published_at = models.DateTimeField(null=True)
    view_count = models.IntegerField(default=0)
    
    objects = PostQuerySet.as_manager()
    published = PublishedManager()

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    is_approved = models.BooleanField(default=False)
    is_spam = models.BooleanField(default=False)
    
    objects = CommentQuerySet.as_manager()

# Signal receivers with chains
@receiver(post_published)
def notify_subscribers(sender, post, author, **kwargs):
    """Send notifications when post is published."""
    subscribers = User.objects.filter(subscriptions__author=author)
    for user in subscribers:
        user_activity.send(sender=User, user=user, action='notified', target=post)

@receiver(post_published)  
def clear_cache(sender, post, **kwargs):
    """Clear cached post list when new post published."""
    from django.core.cache import cache
    cache.delete(f'posts_by_author_{post.author.id}')

@receiver(comment_approved)
def increment_comment_count(sender, comment, post, **kwargs):
    """Update post comment count."""
    post.comment_count = post.comments.approved().count()
    post.save()
    
@receiver(comment_approved)
def notify_post_author(sender, comment, post, **kwargs):
    """Notify post author of new comment."""
    user_activity.send(sender=User, user=post.author, action='comment', target=comment)

# Signal connections
post_published.connect(notify_subscribers, sender=Post)
comment_approved.connect(increment_comment_count, sender=Comment)

# Complex queryset chains
def get_trending_posts():
    return (Post.objects
            .published()
            .with_comments()
            .filter(view_count__gte=100)
            .order_by('-published_at')
            .select_related('author')
            .prefetch_related('comments'))

def get_author_stats(author):
    return (Post.objects
            .filter(author=author)
            .values('status')
            .annotate(count=Count('id'))
            .order_by('-count'))
