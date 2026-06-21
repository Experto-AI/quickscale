"""Tests for blog views"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from quickscale_modules_blog.models import Category, Post, Tag


def _create_published_posts(
    author_user,
    *,
    count: int,
    category: Category | None = None,
    tag: Tag | None = None,
    title_prefix: str = "Post",
) -> list[Post]:
    posts: list[Post] = []
    for index in range(count):
        post = Post.objects.create(
            title=f"{title_prefix} {index}",
            author=author_user,
            content="Content",
            status="published",
            category=category,
        )
        if tag is not None:
            post.tags.add(tag)
        posts.append(post)
    return posts


@pytest.mark.django_db
class TestPostListView:
    """Tests for PostListView"""

    def test_post_list_view(self, client, author_user):
        """Test post list displays published posts"""
        Post.objects.create(
            title="Published Post",
            author=author_user,
            content="Content",
            status="published",
        )
        Post.objects.create(
            title="Draft Post",
            author=author_user,
            content="Content",
            status="draft",
        )

        response = client.get(reverse("quickscale_blog:post_list"))
        assert response.status_code == 200
        assert "Published Post" in str(response.content)
        assert "Draft Post" not in str(response.content)

    def test_post_list_uses_runtime_posts_per_page_setting(
        self,
        client,
        author_user,
        settings,
    ):
        """Test post list pagination reads BLOG_POSTS_PER_PAGE at runtime."""
        settings.BLOG_POSTS_PER_PAGE = 2
        _create_published_posts(author_user, count=3)

        response = client.get(reverse("quickscale_blog:post_list"))

        assert response.status_code == 200
        assert response.context["paginator"].per_page == 2
        assert len(response.context["page_obj"].object_list) == 2
        assert response.context["is_paginated"] is True

    def test_post_list_invalid_posts_per_page_falls_back_to_default(
        self,
        client,
        author_user,
        settings,
    ):
        """Test invalid BLOG_POSTS_PER_PAGE values fall back to the default."""
        settings.BLOG_POSTS_PER_PAGE = "invalid"
        _create_published_posts(author_user, count=11)

        response = client.get(reverse("quickscale_blog:post_list"))

        assert response.status_code == 200
        assert response.context["paginator"].per_page == 10


@pytest.mark.django_db
class TestPostDetailView:
    """Tests for PostDetailView"""

    def test_post_detail_view(self, client, author_user):
        """Test post detail view"""
        post = Post.objects.create(
            title="Test Post",
            author=author_user,
            content="Test content",
            status="published",
        )

        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))
        assert response.status_code == 200
        assert "Test Post" in str(response.content)

    def test_post_detail_draft_not_found(self, client, author_user):
        """Test that draft posts return 404"""
        post = Post.objects.create(
            title="Draft Post",
            author=author_user,
            content="Draft content",
            status="draft",
        )
        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))
        assert response.status_code == 404

    def test_post_detail_styling_hooks_present_when_rendered(self, client, author_user):
        """Test post detail includes markdown wrapper and module stylesheet"""
        post = Post.objects.create(
            title="Styled Post",
            author=author_user,
            content="# Heading\n\nStyled content",
            status="published",
        )

        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert 'class="blog-markdown-content"' in html
        assert "quickscale_modules_blog/blog.css" in html

    def test_post_detail_escapes_inline_html_in_markdown(self, client, author_user):
        """Test markdown rendering escapes raw HTML from post content"""
        post = Post.objects.create(
            title="Unsafe Post",
            author=author_user,
            content="# Heading\n\n<script>alert('xss')</script>",
            status="published",
        )

        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert "<script>alert('xss')</script>" not in html
        assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html

    def test_post_detail_renders_markdown_image_links(self, client, author_user):
        """Test markdown image syntax renders inline images from uploaded URLs."""
        post = Post.objects.create(
            title="Image Markdown Post",
            author=author_user,
            content="![Diagram](https://cdn.example.com/blog/diagram.png)",
            status="published",
        )

        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert (
            '<img alt="Diagram" src="https://cdn.example.com/blog/diagram.png"' in html
        )

    def test_post_detail_renders_featured_image(
        self,
        client,
        author_user,
        tmp_path,
        settings,
    ):
        """Test post detail renders the featured image uploaded via the model field."""
        settings.MEDIA_ROOT = str(tmp_path)

        image = Image.new("RGB", (800, 450), color="purple")
        image_path = tmp_path / "featured.png"
        image.save(str(image_path), format="PNG")

        with open(image_path, "rb") as image_handle:
            uploaded_file = SimpleUploadedFile(
                "featured.png",
                image_handle.read(),
                content_type="image/png",
            )

        post = Post.objects.create(
            title="Featured Image Post",
            author=author_user,
            content="Body",
            status="published",
            featured_image=uploaded_file,
            featured_image_alt="Featured diagram",
        )

        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert "Featured diagram" in html
        assert post.get_featured_image_url() in html

    def test_post_detail_uses_helper_backed_featured_image_url(
        self,
        client,
        author_user,
        tmp_path,
        settings,
    ):
        """Post detail should render helper-backed public URLs instead of direct `.url`."""
        settings.MEDIA_ROOT = str(tmp_path)
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = "https://cdn.example.com/media"

        image = Image.new("RGB", (800, 450), color="purple")
        image_path = tmp_path / "featured-cdn.png"
        image.save(str(image_path), format="PNG")

        with open(image_path, "rb") as image_handle:
            uploaded_file = SimpleUploadedFile(
                "featured-cdn.png",
                image_handle.read(),
                content_type="image/png",
            )

        post = Post.objects.create(
            title="Featured CDN Post",
            author=author_user,
            content="Body",
            status="published",
            featured_image=uploaded_file,
            featured_image_alt="Featured CDN diagram",
        )

        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert f'src="{post.get_featured_image_url()}"' in html
        assert f'src="{post.featured_image.url}"' not in html


@pytest.mark.django_db
class TestCategoryListView:
    """Tests for CategoryListView"""

    def test_category_list_view(self, client, author_user):
        """Test category list displays published posts in category"""
        category = Category.objects.create(name="Tech")
        Post.objects.create(
            title="Tech Post",
            author=author_user,
            content="Content",
            status="published",
            category=category,
        )
        Post.objects.create(
            title="Draft Tech Post",
            author=author_user,
            content="Content",
            status="draft",
            category=category,
        )

        response = client.get(
            reverse("quickscale_blog:category_list", args=[category.slug])
        )
        assert response.status_code == 200
        assert "Tech Post" in str(response.content)
        assert "Draft Tech Post" not in str(response.content)
        assert response.context["category"] == category

    def test_category_list_uses_runtime_posts_per_page_setting(
        self,
        client,
        author_user,
        settings,
    ):
        """Test category list pagination reads BLOG_POSTS_PER_PAGE at runtime."""
        settings.BLOG_POSTS_PER_PAGE = 2
        category = Category.objects.create(name="Paginated Tech")
        _create_published_posts(
            author_user,
            count=3,
            category=category,
            title_prefix="Category Post",
        )

        response = client.get(
            reverse("quickscale_blog:category_list", args=[category.slug])
        )

        assert response.status_code == 200
        assert response.context["paginator"].per_page == 2
        assert len(response.context["page_obj"].object_list) == 2

    def test_category_list_view_nonexistent(self, client):
        """Test category list with nonexistent slug returns 404"""
        response = client.get(
            reverse("quickscale_blog:category_list", args=["nonexistent"])
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestTagListView:
    """Tests for TagListView"""

    def test_tag_list_view(self, client, author_user):
        """Test tag list displays published posts with tag"""
        tag = Tag.objects.create(name="Python")
        post = Post.objects.create(
            title="Python Post",
            author=author_user,
            content="Content",
            status="published",
        )
        post.tags.add(tag)

        draft = Post.objects.create(
            title="Draft Python",
            author=author_user,
            content="Content",
            status="draft",
        )
        draft.tags.add(tag)

        response = client.get(reverse("quickscale_blog:tag_list", args=[tag.slug]))
        assert response.status_code == 200
        assert "Python Post" in str(response.content)
        assert "Draft Python" not in str(response.content)
        assert response.context["tag"] == tag

    def test_tag_list_uses_runtime_posts_per_page_setting(
        self,
        client,
        author_user,
        settings,
    ):
        """Test tag list pagination reads BLOG_POSTS_PER_PAGE at runtime."""
        settings.BLOG_POSTS_PER_PAGE = 2
        tag = Tag.objects.create(name="Paginated Python")
        _create_published_posts(
            author_user,
            count=3,
            tag=tag,
            title_prefix="Tag Post",
        )

        response = client.get(reverse("quickscale_blog:tag_list", args=[tag.slug]))

        assert response.status_code == 200
        assert response.context["paginator"].per_page == 2
        assert len(response.context["page_obj"].object_list) == 2

    def test_tag_list_view_nonexistent(self, client):
        """Test tag list with nonexistent slug returns 404"""
        response = client.get(reverse("quickscale_blog:tag_list", args=["nonexistent"]))

        assert response.status_code == 404


@pytest.mark.django_db
class TestAuthorlessPostRendering:
    """Tests for rendering pages with authorless posts"""

    def test_authorless_post_omits_author_label_on_all_pages(self, client):
        """Test authorless post omits fallback label across list/detail/category/tag pages"""
        category = Category.objects.create(name="Authorless Category")
        tag = Tag.objects.create(name="Authorless Tag")
        post = Post.objects.create(
            title="Authorless Post",
            author=None,
            content="Authorless content",
            status="published",
            category=category,
        )
        post.tags.add(tag)

        page_urls = [
            reverse("quickscale_blog:post_list"),
            reverse("quickscale_blog:post_detail", args=[post.slug]),
            reverse("quickscale_blog:category_list", args=[category.slug]),
            reverse("quickscale_blog:tag_list", args=[tag.slug]),
        ]

        for url in page_urls:
            response = client.get(url)
            assert response.status_code == 200
            assert "Unknown author" not in response.content.decode()


# ---------------------------------------------------------------------------
# Phase 3 (F11.11) — org-scoped view route assertions (HTML views)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOrgScopedPostListView:
    """Tests for org-scoped PostListView (Phase 2/3, F11.11)"""

    def test_org_post_list_returns_only_same_org_posts(
        self,
        client,
        org_a,
        org_b,
        org_a_admin,
    ):
        """Org-scoped post list should return only the active org's posts."""
        Post.objects.create(
            title="Org A Visible",
            author=org_a_admin,
            content="Content",
            status="published",
            organization=org_a,
        )
        Post.objects.create(
            title="Org B Hidden",
            author=org_a_admin,
            content="Content",
            status="published",
            organization=org_b,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/blog/")

        assert response.status_code == 200
        html = response.content.decode()
        assert "Org A Visible" in html
        assert "Org B Hidden" not in html

    def test_org_post_list_hides_drafts(
        self,
        client,
        org_a,
        org_a_admin,
    ):
        """Org-scoped post list should only show published posts."""
        Post.objects.create(
            title="Published Post",
            author=org_a_admin,
            content="Content",
            status="published",
            organization=org_a,
        )
        Post.objects.create(
            title="Draft Post",
            author=org_a_admin,
            content="Content",
            status="draft",
            organization=org_a,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/blog/")

        assert response.status_code == 200
        html = response.content.decode()
        assert "Published Post" in html
        assert "Draft Post" not in html

    def test_org_post_list_pagination(
        self,
        client,
        org_a,
        org_a_admin,
        settings,
    ):
        """Org-scoped post list should respect BLOG_POSTS_PER_PAGE."""
        settings.BLOG_POSTS_PER_PAGE = 2
        for i in range(3):
            Post.objects.create(
                title=f"Org Post {i}",
                author=org_a_admin,
                content="Content",
                status="published",
                organization=org_a,
            )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/blog/")

        assert response.status_code == 200
        assert response.context["paginator"].per_page == 2
        assert len(response.context["page_obj"].object_list) == 2
        assert response.context["is_paginated"] is True


@pytest.mark.django_db
class TestOrgScopedPostDetailView:
    """Tests for org-scoped PostDetailView (Phase 2/3, F11.11)"""

    def test_org_post_detail_returns_same_org_post(
        self,
        client,
        org_a,
        org_a_admin,
    ):
        """Org-scoped post detail should return a same-org published post."""
        post = Post.objects.create(
            title="Org A Detail",
            author=org_a_admin,
            content="Content",
            status="published",
            organization=org_a,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/blog/post/{post.slug}/")

        assert response.status_code == 200
        assert "Org A Detail" in response.content.decode()

    def test_org_post_detail_hides_draft(
        self,
        client,
        org_a,
        org_a_admin,
    ):
        """Org-scoped post detail should return 404 for draft posts."""
        post = Post.objects.create(
            title="Draft Detail",
            author=org_a_admin,
            content="Content",
            status="draft",
            organization=org_a,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/blog/post/{post.slug}/")

        assert response.status_code == 404

    def test_org_post_detail_includes_styling_hooks(
        self,
        client,
        org_a,
        org_a_admin,
    ):
        """Org-scoped post detail should include markdown/blog CSS hooks."""
        post = Post.objects.create(
            title="Styled",
            author=org_a_admin,
            content="# Heading\n\nContent",
            status="published",
            organization=org_a,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/blog/post/{post.slug}/")

        assert response.status_code == 200
        html = response.content.decode()
        assert 'class="blog-markdown-content"' in html
        assert "quickscale_modules_blog/blog.css" in html

    def test_org_post_detail_with_featured_image(
        self,
        client,
        org_a,
        org_a_admin,
        tmp_path,
        settings,
    ):
        """Org-scoped post detail should render featured image."""
        settings.MEDIA_ROOT = str(tmp_path)
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        image = Image.new("RGB", (800, 450), color="purple")
        image_path = tmp_path / "featured-org.png"
        image.save(str(image_path), format="PNG")
        with open(image_path, "rb") as f:
            uploaded = SimpleUploadedFile(
                "featured-org.png", f.read(), content_type="image/png"
            )

        post = Post.objects.create(
            title="Featured Org Post",
            author=org_a_admin,
            content="Body",
            status="published",
            featured_image=uploaded,
            featured_image_alt="Org featured diagram",
            organization=org_a,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/blog/post/{post.slug}/")

        assert response.status_code == 200
        html = response.content.decode()
        assert "Org featured diagram" in html
        assert post.get_featured_image_url() in html


@pytest.mark.django_db
class TestOrgScopedCategoryListView:
    """Tests for org-scoped CategoryListView (Phase 2/3, F11.11)"""

    def test_org_category_list_returns_only_same_org_posts(
        self,
        client,
        org_a,
        org_b,
        org_a_admin,
    ):
        """Org-scoped category list should return only same-org posts in that category."""
        cat_a = Category.objects.create(
            name="Org A Cat",
            slug="org-a-cat",
            organization=org_a,
        )
        Post.objects.create(
            title="Org A Category Post",
            author=org_a_admin,
            content="Content",
            status="published",
            category=cat_a,
            organization=org_a,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/blog/category/{cat_a.slug}/")

        assert response.status_code == 200
        html = response.content.decode()
        assert "Org A Category Post" in html

    def test_org_category_list_cross_org_category_returns_404(
        self,
        client,
        org_a,
        org_b,
        org_a_admin,
    ):
        """Cross-org category slug should return 404 on org-scoped route."""
        cat_b = Category.objects.create(
            name="Org B Cat",
            slug="org-b-cat",
            organization=org_b,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/blog/category/{cat_b.slug}/")

        assert response.status_code == 404

    def test_org_category_list_nonexistent_returns_404(
        self,
        client,
        org_a,
        org_a_admin,
    ):
        """Nonexistent category slug should return 404 on org-scoped route."""
        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/blog/category/nonexistent/")

        assert response.status_code == 404


@pytest.mark.django_db
class TestOrgScopedTagListView:
    """Tests for org-scoped TagListView (Phase 2/3, F11.11)"""

    def test_org_tag_list_returns_only_same_org_posts(
        self,
        client,
        org_a,
        org_b,
        org_a_admin,
    ):
        """Org-scoped tag list should return only same-org posts with that tag."""
        tag_a = Tag.objects.create(
            name="Org A Tag",
            slug="org-a-tag",
            organization=org_a,
        )
        post = Post.objects.create(
            title="Org A Tag Post",
            author=org_a_admin,
            content="Content",
            status="published",
            organization=org_a,
        )
        post.tags.add(tag_a)

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/blog/tag/{tag_a.slug}/")

        assert response.status_code == 200
        html = response.content.decode()
        assert "Org A Tag Post" in html

    def test_org_tag_list_cross_org_tag_returns_404(
        self,
        client,
        org_a,
        org_b,
        org_a_admin,
    ):
        """Cross-org tag slug should return 404 on org-scoped route."""
        tag_b = Tag.objects.create(
            name="Org B Tag",
            slug="org-b-tag",
            organization=org_b,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/blog/tag/{tag_b.slug}/")

        assert response.status_code == 404

    def test_org_tag_list_nonexistent_returns_404(
        self,
        client,
        org_a,
        org_a_admin,
    ):
        """Nonexistent tag slug should return 404 on org-scoped route."""
        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/blog/tag/nonexistent/")

        assert response.status_code == 404
