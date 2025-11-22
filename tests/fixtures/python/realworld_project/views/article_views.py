"""
Django Class-Based Views for article management.

Test fixture for extract_django_cbvs() - covers all CBV types, permission checks,
queryset overrides, http_method_names restrictions, and template associations.
"""

from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView,
    FormView, TemplateView, RedirectView
)
from django.contrib.auth.decorators import login_required, permission_required
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404

from ..models.article import Article
from ..models.user import User
from ..forms.article_forms import ArticleForm, ArticleSearchForm


# 1. Basic ListView - no auth, no custom queryset
class ArticleListView(ListView):
    """List all published articles."""
    model = Article
    template_name = "articles/list.html"
    context_object_name = "articles"
    paginate_by = 20


# 2. DetailView - no auth, standard behavior
class ArticleDetailView(DetailView):
    """Display a single article."""
    model = Article
    template_name = "articles/detail.html"


# 3. CreateView with permission check on dispatch()
@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('articles.add_article'), name='dispatch')
class ArticleCreateView(CreateView):
    """Create a new article (requires authentication and permission)."""
    model = Article
    form_class = ArticleForm
    template_name = "articles/create.html"
    success_url = reverse_lazy('article-list')

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)


# 4. UpdateView with get_queryset() override (SQL injection surface)
class ArticleUpdateView(UpdateView):
    """Update an existing article with custom queryset filtering."""
    model = Article
    form_class = ArticleForm
    template_name = "articles/update.html"

    def get_queryset(self):
        """Override to filter by author - potential SQL injection if user input used."""
        base_qs = super().get_queryset()
        # This is a security-relevant override - could be vulnerable if author_id from request
        return base_qs.filter(author=self.request.user)


# 5. DeleteView with permission check
class ArticleDeleteView(DeleteView):
    """Delete an article (requires login)."""
    model = Article
    template_name = "articles/delete_confirm.html"
    success_url = reverse_lazy('article-list')

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        """Protect with login_required decorator."""
        return super().dispatch(*args, **kwargs)


# 6. ListView with http_method_names restriction
class ArticleSearchView(ListView):
    """Search articles - only allow GET requests."""
    model = Article
    template_name = "articles/search.html"
    http_method_names = ['get']  # Explicitly restrict to GET only

    def get_queryset(self):
        """Filter by search query from GET params."""
        queryset = super().get_queryset()
        query = self.request.GET.get('q', '')
        if query:
            queryset = queryset.filter(title__icontains=query)
        return queryset


# 7. ListView with multiple permission decorators
@method_decorator([login_required, permission_required('articles.view_article')], name='dispatch')
class ArticleDraftListView(ListView):
    """List draft articles (requires auth + permission)."""
    model = Article
    template_name = "articles/drafts.html"
    http_method_names = ['get', 'head']

    def get_queryset(self):
        """Only show drafts belonging to current user."""
        return Article.objects.filter(status='draft', author=self.request.user)


# 8. FormView without model association
class ArticleSearchFormView(FormView):
    """Form-only view for article search."""
    form_class = ArticleSearchForm
    template_name = "articles/search_form.html"
    success_url = reverse_lazy('article-search')


# 9. TemplateView - no model, just template rendering
class ArticleAboutView(TemplateView):
    """About page for articles section."""
    template_name = "articles/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_articles'] = Article.objects.count()
        return context


# 10. RedirectView - redirect to article list
class ArticleHomeRedirectView(RedirectView):
    """Redirect /articles/ to /articles/list/."""
    permanent = False
    url = reverse_lazy('article-list')


# 11. DetailView with complex permission check on dispatch
class ArticleAdminDetailView(DetailView):
    """Admin-only article detail view."""
    model = Article
    template_name = "articles/admin_detail.html"

    @method_decorator(login_required)
    @method_decorator(permission_required('articles.view_article'))
    @method_decorator(permission_required('articles.change_article'))
    def dispatch(self, *args, **kwargs):
        """Require multiple permissions."""
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        """Admin can see all articles, including deleted ones."""
        return Article.all_objects.all()  # Include soft-deleted


# 12. UpdateView with both permission check AND get_queryset override
class ArticleModerateView(UpdateView):
    """Moderate an article (admin only, custom queryset)."""
    model = Article
    template_name = "articles/moderate.html"
    fields = ['status', 'featured']
    http_method_names = ['get', 'post']

    @method_decorator(login_required)
    @method_decorator(permission_required('articles.moderate_article'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        """Only show articles pending moderation."""
        return Article.objects.filter(status='pending_review')
