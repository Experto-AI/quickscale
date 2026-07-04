"""Django app configuration for QuickScale blog module"""

from django.apps import AppConfig


class QuickscaleBlogConfig(AppConfig):
    """Configuration for QuickScale blog module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_blog"
    label = "quickscale_modules_blog"
    verbose_name = "QuickScale Blog"

    def ready(self) -> None:
        """Startup validation for required blog module settings (SA17.5)."""
        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured

        # -- BLOG_ENABLE_RSS must be explicitly set (no default True) --
        blog_enable_rss = getattr(settings, "BLOG_ENABLE_RSS", None)
        if blog_enable_rss is None:
            raise ImproperlyConfigured(
                "BLOG_ENABLE_RSS must be explicitly set to True or False"
            )

        # -- MEDIA_URL must be explicitly configured (no fallback to '/media/') --
        # Note: Django always defines MEDIA_URL (default "") and normalizes
        # empty values to "/", so we reject that trivial sentinel.
        media_url = getattr(settings, "MEDIA_URL", "")
        media_url_value = str(media_url).strip()
        if not media_url_value or media_url_value == "/":
            raise ImproperlyConfigured(
                "MEDIA_URL must be explicitly configured for the blog module"
            )

        # -- BLOG_API_TOKENS entries must be well-formed --
        tokens = getattr(settings, "BLOG_API_TOKENS", None)
        if tokens is not None:
            if not isinstance(tokens, list):
                raise ImproperlyConfigured(
                    f"BLOG_API_TOKENS must be a list, got {type(tokens).__name__}"
                )
            for i, entry in enumerate(tokens):
                if not isinstance(entry, dict):
                    raise ImproperlyConfigured(
                        f"BLOG_API_TOKENS[{i}] is not a dict: {entry!r}"
                    )
                raw_token = entry.get("token")
                username = entry.get("username")
                if not isinstance(raw_token, str) or not raw_token.strip():
                    raise ImproperlyConfigured(
                        f"BLOG_API_TOKENS[{i}] has missing or empty 'token': {entry!r}"
                    )
                if not isinstance(username, str) or not username.strip():
                    raise ImproperlyConfigured(
                        f"BLOG_API_TOKENS[{i}] has missing or empty 'username': {entry!r}"
                    )
