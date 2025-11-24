"""Views for QuickScale blog module"""

from django.views.generic import DetailView, ListView

from .models import Category, Post, Tag


class PostListView(ListView):
    """Display paginated list of published blog posts"""

    model = Post
    template_name = "quickscale_modules_blog/blog/post_list.html"
    context_object_name = "posts"
    paginate_by = 10

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Return only published posts, ordered by publish date"""
        return (
            Post.objects.filter(status="published")
            .select_related("author", "category")
            .prefetch_related("tags")
        )


class PostDetailView(DetailView):
    """Display single blog post"""

    model = Post
    template_name = "quickscale_modules_blog/blog/post_detail.html"
    context_object_name = "post"

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Return only published posts"""
        return (
            Post.objects.filter(status="published")
            .select_related("author", "category")
            .prefetch_related("tags")
        )


class CategoryListView(ListView):
    """Display posts filtered by category"""

    model = Post
    template_name = "quickscale_modules_blog/blog/category_list.html"
    context_object_name = "posts"
    paginate_by = 10

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Return published posts in the specified category"""
        self.category = Category.objects.get(slug=self.kwargs["slug"])
        return (
            Post.objects.filter(status="published", category=self.category)
            .select_related("author", "category")
            .prefetch_related("tags")
        )

    def get_context_data(self, **kwargs):  # type: ignore[no-untyped-def]
        """Add category to context"""
        context = super().get_context_data(**kwargs)
        context["category"] = self.category
        return context


class TagListView(ListView):
    """Display posts filtered by tag"""

    model = Post
    template_name = "quickscale_modules_blog/blog/tag_list.html"
    context_object_name = "posts"
    paginate_by = 10

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Return published posts with the specified tag"""
        self.tag = Tag.objects.get(slug=self.kwargs["slug"])
        return (
            Post.objects.filter(status="published", tags=self.tag)
            .select_related("author", "category")
            .prefetch_related("tags")
        )

    def get_context_data(self, **kwargs):  # type: ignore[no-untyped-def]
        """Add tag to context"""
        context = super().get_context_data(**kwargs)
        context["tag"] = self.tag
        return context
