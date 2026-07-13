"""Tests for blog views (single flat URL tree, T1.6)"""

import contextlib

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from quickscale_modules_blog.models import Category, Post, Tag
from quickscale_modules_blog.views import _sanitize_href
from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY


def _create_published_posts(
    author_user,
    org,
    *,
    count: int,
    category: Category | None = None,
    tag: Tag | None = None,
    title_prefix: str = "Post",
    blog_org_scope=None,
) -> list[Post]:
    posts: list[Post] = []
    scoper = blog_org_scope(org) if blog_org_scope else _null_context()
    with scoper:
        for index in range(count):
            post = Post.objects.create(
                title=f"{title_prefix} {index}",
                author=author_user,
                content="Content",
                status="published",
                category=category,
                organization=org,
            )
            if tag is not None:
                post.tags.add(tag)
            posts.append(post)
    return posts


@contextlib.contextmanager
def _null_context():
    """No-op context manager for callers that do not pass blog_org_scope."""
    yield


@pytest.mark.django_db
class TestPostListView:
    """Tests for PostListView"""

    def test_post_list_view(self, client, author_user, system_org, blog_org_scope):
        """Test post list displays published posts"""
        with blog_org_scope(system_org):
            Post.objects.create(
                title="Published Post",
                author=author_user,
                content="Content",
                status="published",
                organization=system_org,
            )
            Post.objects.create(
                title="Draft Post",
                author=author_user,
                content="Content",
                status="draft",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(reverse("quickscale_blog:post_list"))
        assert response.status_code == 200
        assert "Published Post" in str(response.content)
        assert "Draft Post" not in str(response.content)

    def test_post_list_uses_runtime_posts_per_page_setting(
        self,
        client,
        author_user,
        system_org,
        settings,
        blog_org_scope,
    ):
        """Test post list pagination reads BLOG_POSTS_PER_PAGE at runtime."""
        settings.BLOG_POSTS_PER_PAGE = 2
        _create_published_posts(
            author_user, system_org, count=3, blog_org_scope=blog_org_scope
        )

        with blog_org_scope(None):
            response = client.get(reverse("quickscale_blog:post_list"))

        assert response.status_code == 200
        assert response.context["paginator"].per_page == 2
        assert len(response.context["page_obj"].object_list) == 2
        assert response.context["is_paginated"] is True

    def test_post_list_invalid_posts_per_page_falls_back_to_default(
        self,
        client,
        author_user,
        system_org,
        settings,
        blog_org_scope,
    ):
        """Test invalid BLOG_POSTS_PER_PAGE values fall back to the default."""
        settings.BLOG_POSTS_PER_PAGE = "invalid"
        _create_published_posts(
            author_user, system_org, count=11, blog_org_scope=blog_org_scope
        )

        with blog_org_scope(None):
            response = client.get(reverse("quickscale_blog:post_list"))

        assert response.status_code == 200
        assert response.context["paginator"].per_page == 10


@pytest.mark.django_db
class TestPostDetailView:
    """Tests for PostDetailView"""

    def test_post_detail_view(self, client, author_user, system_org, blog_org_scope):
        """Test post detail view"""
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Test Post",
                author=author_user,
                content="Test content",
                status="published",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )
        assert response.status_code == 200
        assert "Test Post" in str(response.content)

    def test_post_detail_draft_not_found(
        self, client, author_user, system_org, blog_org_scope
    ):
        """Test that draft posts return 404"""
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Draft Post",
                author=author_user,
                content="Draft content",
                status="draft",
                organization=system_org,
            )
        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )
        assert response.status_code == 404

    def test_post_detail_styling_hooks_present_when_rendered(
        self, client, author_user, system_org, blog_org_scope
    ):
        """Test post detail includes markdown wrapper and module stylesheet"""
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Styled Post",
                author=author_user,
                content="# Heading\n\nStyled content",
                status="published",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )

        assert response.status_code == 200
        html = response.content.decode()
        assert 'class="blog-markdown-content"' in html
        assert "quickscale_modules_blog/blog.css" in html

    def test_post_detail_escapes_inline_html_in_markdown(
        self, client, author_user, system_org, blog_org_scope
    ):
        """Test markdown rendering escapes raw HTML from post content"""
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Unsafe Post",
                author=author_user,
                content="# Heading\n\n<script>alert('xss')</script>",
                status="published",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )

        assert response.status_code == 200
        html = response.content.decode()
        assert "<script>alert('xss')</script>" not in html
        assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html

    def test_post_detail_renders_markdown_image_links(
        self, client, author_user, system_org, blog_org_scope
    ):
        """Test markdown image syntax renders inline images from uploaded URLs."""
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Image Markdown Post",
                author=author_user,
                content="![Diagram](https://cdn.example.com/blog/diagram.png)",
                status="published",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )

        assert response.status_code == 200
        html = response.content.decode()
        assert (
            '<img alt="Diagram" src="https://cdn.example.com/blog/diagram.png"' in html
        )

    def test_post_detail_renders_featured_image(
        self,
        client,
        author_user,
        system_org,
        tmp_path,
        settings,
        blog_org_scope,
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

        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Featured Image Post",
                author=author_user,
                content="Body",
                status="published",
                featured_image=uploaded_file,
                featured_image_alt="Featured diagram",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )

        assert response.status_code == 200
        html = response.content.decode()
        assert "Featured diagram" in html
        assert post.get_featured_image_url() in html

    def test_post_detail_uses_helper_backed_featured_image_url(
        self,
        client,
        author_user,
        system_org,
        tmp_path,
        settings,
        blog_org_scope,
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

        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Featured CDN Post",
                author=author_user,
                content="Body",
                status="published",
                featured_image=uploaded_file,
                featured_image_alt="Featured CDN diagram",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )

        assert response.status_code == 200
        html = response.content.decode()
        assert f'src="{post.get_featured_image_url()}"' in html
        assert f'src="{post.featured_image.url}"' not in html

    # ------------------------------------------------------------------
    # SA26 — Markdown URI scheme sanitization
    # ------------------------------------------------------------------

    def test_post_detail_sanitizes_javascript_markdown_links(
        self, client, author_user, system_org, blog_org_scope
    ):
        """Test markdown []() javascript: links are neutralized in rendered output."""
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="JS Link Post",
                author=author_user,
                content="[Click](javascript:alert(1))",
                status="published",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )

        assert response.status_code == 200
        html = response.content.decode()
        # The href must not contain javascript: — it should be neutralized to ""
        assert 'href="javascript:alert(1)"' not in html
        assert 'href=""' in html
        # Link text should still be present
        assert "Click" in html

    def test_post_detail_sanitizes_tab_obfuscated_javascript(
        self, client, author_user, system_org, blog_org_scope
    ):
        """Test markdown []() links with tab-obfuscated javascript: scheme are neutralized.

        Note: the markdown parser converts control characters in URLs to
        spaces before the sanitizer sees them, so ``java\\tscript:``
        renders as ``java    script:alert(1)`` in the href.  Browsers do
        NOT strip interior spaces from URLs, so this is not an executable
        ``javascript:`` scheme — the tab-obfuscation attack is blocked by
        the markdown parser itself.  The ``_sanitize_href`` control-char
        normalisation handles the general case when a tab reaches the
        sanitizer via a non-markdown path.
        """
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Tab JS Link Post",
                author=author_user,
                content="[Click](java\tscript:alert(1))",
                status="published",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )

        assert response.status_code == 200
        html = response.content.decode()
        assert 'href="javascript:' not in html
        assert "javascript:alert(1)" not in html
        assert "Click" in html

    def test_post_detail_sanitizes_newline_obfuscated_javascript(
        self, client, author_user, system_org, blog_org_scope
    ):
        """Test markdown []() links with newline-obfuscated javascript: scheme are neutralized."""
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="NL JS Link Post",
                author=author_user,
                content="[Click](java\nscript:alert(1))",
                status="published",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )

        assert response.status_code == 200
        html = response.content.decode()
        assert 'href="java' not in html
        assert "javascript:alert(1)" not in html
        assert "Click" in html

    def test_post_detail_sanitizes_case_variant_javascript(
        self, client, author_user, system_org, blog_org_scope
    ):
        """Test markdown []() links with case-variant javascript: scheme are neutralized."""
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Case JS Link Post",
                author=author_user,
                content="[Click](JaVaScRiPt:alert(1))",
                status="published",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )

        assert response.status_code == 200
        html = response.content.decode()
        assert 'href="JaVaScRiPt:alert(1)"' not in html
        assert "javascript:alert(1)" not in html
        assert "Click" in html

    def test_post_detail_sanitizes_data_scheme(
        self, client, author_user, system_org, blog_org_scope
    ):
        """Test markdown []() data: links are neutralized in rendered output."""
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Data Link Post",
                author=author_user,
                content="[Payload](data:text/html,test)",
                status="published",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )

        assert response.status_code == 200
        html = response.content.decode()
        assert 'href="data:' not in html
        assert "Payload" in html

    def test_post_detail_sanitizes_vbscript_scheme(
        self, client, author_user, system_org, blog_org_scope
    ):
        """Test markdown []() vbscript: links are neutralized in rendered output."""
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="VB Link Post",
                author=author_user,
                content="[VB](vbscript:msgbox(1))",
                status="published",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )

        assert response.status_code == 200
        html = response.content.decode()
        assert 'href="vbscript:' not in html
        assert "VB" in html

    def test_post_detail_preserves_https_markdown_links(
        self, client, author_user, system_org, blog_org_scope
    ):
        """Test legitimate https: markdown links remain clickable."""
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Safe Link Post",
                author=author_user,
                content="[Example](https://example.com/page)",
                status="published",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )

        assert response.status_code == 200
        html = response.content.decode()
        assert 'href="https://example.com/page"' in html

    def test_post_detail_preserves_mailto_markdown_links(
        self, client, author_user, system_org, blog_org_scope
    ):
        """Test legitimate mailto: markdown links remain clickable."""
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Mailto Link Post",
                author=author_user,
                content="[Email](mailto:user@example.com)",
                status="published",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )

        assert response.status_code == 200
        html = response.content.decode()
        assert 'href="mailto:user@example.com"' in html


class TestSanitizeHrefUnit:
    """Direct unit tests for the ``_sanitize_href`` security primitive.

    Locks the C0 control-char normalization (CR-SA26-001) so the fix cannot
    be silently reverted.  These reach ``_sanitize_href`` directly — not
    through ``markdownify``, which pre-converts tabs to spaces in rendered
    hrefs and would therefore not fail if the normalization were removed.
    """

    def test_neutralizes_tab_obfuscated_javascript(self):
        assert _sanitize_href("java\tscript:alert(1)") == ""

    def test_neutralizes_newline_obfuscated_javascript(self):
        assert _sanitize_href("java\nscript:alert(1)") == ""

    def test_neutralizes_carriage_return_obfuscated_javascript(self):
        assert _sanitize_href("java\rscript:alert(1)") == ""

    def test_neutralizes_leading_whitespace_javascript(self):
        assert _sanitize_href("\t  javascript:alert(1)") == ""

    def test_preserves_https_through_normalization(self):
        assert _sanitize_href("https://example.com/page") == "https://example.com/page"


@pytest.mark.django_db
class TestCategoryListView:
    """Tests for CategoryListView"""

    def test_category_list_view(self, client, author_user, system_org, blog_org_scope):
        """Test category list displays published posts in category"""
        with blog_org_scope(system_org):
            category = Category.objects.create(name="Tech", organization=system_org)
            Post.objects.create(
                title="Tech Post",
                author=author_user,
                content="Content",
                status="published",
                category=category,
                organization=system_org,
            )
            Post.objects.create(
                title="Draft Tech Post",
                author=author_user,
                content="Content",
                status="draft",
                category=category,
                organization=system_org,
            )

        with blog_org_scope(None):
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
        system_org,
        settings,
        blog_org_scope,
    ):
        """Test category list pagination reads BLOG_POSTS_PER_PAGE at runtime."""
        settings.BLOG_POSTS_PER_PAGE = 2
        with blog_org_scope(system_org):
            category = Category.objects.create(
                name="Paginated Tech", organization=system_org
            )
        _create_published_posts(
            author_user,
            system_org,
            count=3,
            category=category,
            title_prefix="Category Post",
            blog_org_scope=blog_org_scope,
        )

        with blog_org_scope(None):
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

    def test_tag_list_view(self, client, author_user, system_org, blog_org_scope):
        """Test tag list displays published posts with tag"""
        with blog_org_scope(system_org):
            tag = Tag.objects.create(name="Python", organization=system_org)
            post = Post.objects.create(
                title="Python Post",
                author=author_user,
                content="Content",
                status="published",
                organization=system_org,
            )
            post.tags.add(tag)

            draft = Post.objects.create(
                title="Draft Python",
                author=author_user,
                content="Content",
                status="draft",
                organization=system_org,
            )
            draft.tags.add(tag)

        with blog_org_scope(None):
            response = client.get(reverse("quickscale_blog:tag_list", args=[tag.slug]))
        assert response.status_code == 200
        assert "Python Post" in str(response.content)
        assert "Draft Python" not in str(response.content)
        assert response.context["tag"] == tag

    def test_tag_list_uses_runtime_posts_per_page_setting(
        self,
        client,
        author_user,
        system_org,
        settings,
        blog_org_scope,
    ):
        """Test tag list pagination reads BLOG_POSTS_PER_PAGE at runtime."""
        settings.BLOG_POSTS_PER_PAGE = 2
        with blog_org_scope(system_org):
            tag = Tag.objects.create(name="Paginated Python", organization=system_org)
        _create_published_posts(
            author_user,
            system_org,
            count=3,
            tag=tag,
            title_prefix="Tag Post",
            blog_org_scope=blog_org_scope,
        )

        with blog_org_scope(None):
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

    def test_authorless_post_omits_author_label_on_all_pages(
        self, client, system_org, blog_org_scope
    ):
        """Test authorless post omits fallback label across list/detail/category/tag pages"""
        with blog_org_scope(system_org):
            category = Category.objects.create(
                name="Authorless Category", organization=system_org
            )
            tag = Tag.objects.create(name="Authorless Tag", organization=system_org)
            post = Post.objects.create(
                title="Authorless Post",
                author=None,
                content="Authorless content",
                status="published",
                category=category,
                organization=system_org,
            )
            post.tags.add(tag)

        page_urls = [
            reverse("quickscale_blog:post_list"),
            reverse("quickscale_blog:post_detail", args=[post.slug]),
            reverse("quickscale_blog:category_list", args=[category.slug]),
            reverse("quickscale_blog:tag_list", args=[tag.slug]),
        ]

        with blog_org_scope(None):
            for url in page_urls:
                response = client.get(url)
                assert response.status_code == 200
                assert "Unknown author" not in response.content.decode()


# ---------------------------------------------------------------------------
# Authenticated flat-route view coverage (CR-T16-003)
# ---------------------------------------------------------------------------


def _activate_org_in_session(client, organization):
    """Set the active org in the client session for TenantMiddleware."""
    session = client.session
    session[ACTIVE_ORG_SESSION_KEY] = str(organization.id)
    session.save()


@pytest.mark.django_db
class TestAuthenticatedOrgScopedViews:
    """Authenticated users see only their active org's content on flat routes."""

    def test_authenticated_user_sees_own_org_posts_on_list(
        self, client, org_a, org_a_admin, blog_org_scope
    ):
        """Logged-in user scoped to Org A sees Org A posts on /blog/."""
        with blog_org_scope(org_a):
            Post.objects.create(
                title="Org A Post",
                author=org_a_admin,
                content="Org A content",
                status="published",
                organization=org_a,
            )
        client.force_login(org_a_admin)
        _activate_org_in_session(client, org_a)
        with blog_org_scope(None):
            response = client.get(reverse("quickscale_blog:post_list"))
        assert response.status_code == 200
        assert "Org A Post" in response.content.decode()

    def test_authenticated_user_omits_other_org_posts_on_list(
        self, client, org_a, org_a_admin, org_b, blog_org_scope
    ):
        """User scoped to Org A does not see Org B posts on /blog/."""
        with blog_org_scope(org_a):
            Post.objects.create(
                title="Org A Post",
                author=org_a_admin,
                content="Org A content",
                status="published",
                organization=org_a,
            )
        with blog_org_scope(org_b):
            Post.objects.create(
                title="Org B Post",
                author=org_a_admin,
                content="Org B content",
                status="published",
                organization=org_b,
            )
        client.force_login(org_a_admin)
        _activate_org_in_session(client, org_a)
        with blog_org_scope(None):
            response = client.get(reverse("quickscale_blog:post_list"))
        assert response.status_code == 200
        assert "Org A Post" in response.content.decode()
        assert "Org B Post" not in response.content.decode()

    def test_authenticated_user_sees_own_org_post_detail(
        self, client, org_a, org_a_admin, blog_org_scope
    ):
        """Logged-in user scoped to Org A sees that org's post on detail view."""
        with blog_org_scope(org_a):
            post = Post.objects.create(
                title="Org A Detail",
                author=org_a_admin,
                content="Detail content",
                status="published",
                organization=org_a,
            )
        client.force_login(org_a_admin)
        _activate_org_in_session(client, org_a)
        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[post.slug])
            )
        assert response.status_code == 200
        assert "Org A Detail" in response.content.decode()

    def test_authenticated_user_cannot_see_other_org_post_detail(
        self, client, org_a, org_a_admin, org_b, blog_org_scope
    ):
        """User scoped to Org A gets 404 for Org B posts on detail view."""
        with blog_org_scope(org_a):
            Post.objects.create(
                title="Org A Detail",
                author=org_a_admin,
                content="Detail content",
                status="published",
                organization=org_a,
            )
        with blog_org_scope(org_b):
            b_post = Post.objects.create(
                title="Org B Detail",
                author=org_a_admin,
                content="Detail content",
                status="published",
                organization=org_b,
            )
        client.force_login(org_a_admin)
        _activate_org_in_session(client, org_a)
        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:post_detail", args=[b_post.slug])
            )
        assert response.status_code == 404

    def test_authenticated_user_sees_org_scoped_category(
        self, client, org_a, org_a_admin, blog_org_scope
    ):
        """User scoped to Org A sees that org's category posts."""
        with blog_org_scope(org_a):
            category = Category.objects.create(name="Org A Cat", organization=org_a)
            Post.objects.create(
                title="Org A Cat Post",
                author=org_a_admin,
                content="Content",
                status="published",
                category=category,
                organization=org_a,
            )
        client.force_login(org_a_admin)
        _activate_org_in_session(client, org_a)
        with blog_org_scope(None):
            response = client.get(
                reverse("quickscale_blog:category_list", args=[category.slug])
            )
        assert response.status_code == 200
        assert "Org A Cat Post" in response.content.decode()

    def test_authenticated_user_sees_org_scoped_tag(
        self, client, org_a, org_a_admin, blog_org_scope
    ):
        """User scoped to Org A sees that org's tag posts."""
        with blog_org_scope(org_a):
            tag = Tag.objects.create(name="Org A Tag", organization=org_a)
            post = Post.objects.create(
                title="Org A Tag Post",
                author=org_a_admin,
                content="Content",
                status="published",
                organization=org_a,
            )
            post.tags.add(tag)
        client.force_login(org_a_admin)
        _activate_org_in_session(client, org_a)
        with blog_org_scope(None):
            response = client.get(reverse("quickscale_blog:tag_list", args=[tag.slug]))
        assert response.status_code == 200
        assert "Org A Tag Post" in response.content.decode()
