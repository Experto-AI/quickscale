"""Django-allauth adapter customizations"""

from collections.abc import Callable
from typing import Any, cast

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings

from quickscale_core.runtime import collect_capabilities


class QuickscaleAccountAdapter(DefaultAccountAdapter):
    """Custom account adapter for QuickScale authentication"""

    def is_open_for_signup(self, request: Any) -> bool:
        """Check if signup is allowed based on settings.

        Rule 3: the startup check has validated the declared setting, so the
        value is read directly — there is no silent default that enables
        open signup.
        """
        return settings.ACCOUNT_ALLOW_REGISTRATION

    def save_user(self, request: Any, user: Any, form: Any, commit: bool = True) -> Any:
        """Save user with custom logic"""
        user = super().save_user(request, user, form, commit=False)

        # Add custom user creation logic here if needed
        # For MVP, we use default django-allauth behavior

        if commit:
            user.save()

        return user

    def get_login_redirect_url(self, request: Any) -> str:
        """Return the first declared post-login redirect, else the default.

        An installed module declares organization-aware redirects through the
        rule 4 ``post_login_redirect_hooks`` capability; the first hook that
        returns a URL wins, and with no provider the adapter keeps Django's
        ``LOGIN_REDIRECT_URL``.
        """
        redirect_url = _first_declared_redirect("post_login_redirect_hooks", request)
        if redirect_url is not None:
            return redirect_url
        # LOGIN_REDIRECT_URL is Django's own setting; read it directly.
        return settings.LOGIN_REDIRECT_URL

    def get_signup_redirect_url(self, request: Any) -> str:
        """Return the first declared post-signup redirect, else allauth's default.

        An installed module declares organization-aware redirects through the
        rule 4 ``post_signup_redirect_hooks`` capability; the first hook that
        returns a URL wins, and otherwise allauth's own fallback applies.
        """
        redirect_url = _first_declared_redirect("post_signup_redirect_hooks", request)
        if redirect_url is not None:
            return redirect_url
        return super().get_signup_redirect_url(request)


def _first_declared_redirect(capability: str, request: Any) -> str | None:
    """Return the first URL the hooks declared for *capability* answer."""
    hooks = cast(
        "tuple[Callable[[Any], str | None], ...]",
        collect_capabilities(capability),
    )
    for hook in hooks:
        redirect_url = hook(request)
        if redirect_url is not None:
            return redirect_url
    return None
