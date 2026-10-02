"""Declared account-deletion handler plumbing for the auth views split.

Rule 4: an app that holds account-deletion state declares its operations
through the ``account_deletion_handlers`` capability; rule 5: the boundary
cannot import a provider's types, so the capability is duck-typed.  This
module owns the shape checks and the fail-closed handler invocation; the
``quickscale_modules_auth.views`` facade keeps the collection entry point
with its ``collect_capabilities`` and ``_installed_app_config`` patch seams.
"""

from __future__ import annotations

from typing import Any

from quickscale_modules_auth.exceptions import _AccountDeletionProviderBlocked


def _is_string_tuple(value: object) -> bool:
    """Return whether *value* is a tuple of non-empty strings."""
    return (
        isinstance(value, tuple)
        and bool(value)
        and all(isinstance(item, str) and item for item in value)
    )


def _is_exception_type_tuple(value: object) -> bool:
    """Return whether *value* is a non-empty tuple of exception types."""
    return (
        isinstance(value, tuple)
        and bool(value)
        and all(
            isinstance(item, type) and issubclass(item, BaseException) for item in value
        )
    )


def _handler_name(handler: object) -> str:
    """Name a declared handler in failure messages without importing its type."""
    label = getattr(handler, "label", None)
    if isinstance(label, str) and label:
        return f"{label!r}"
    return repr(handler)


def _provider_error_is_blocking(handler: Any, exc: Exception) -> bool:
    """Return whether *handler* declares *exc* as a fail-closed error."""
    return isinstance(exc, tuple(handler.account_deletion_fail_closed_errors()))


class _AccountDeletionHandlerPlumbingMixin:
    """Collect handler labels and invoke declared handler operations."""

    def _handled_app_labels(self, handlers: tuple[Any, ...]) -> frozenset[str]:
        """Return the app labels the declared handlers own."""
        labels: set[str] = set()
        for handler in handlers:
            labels.update(handler.account_deletion_handled_app_labels())
        return frozenset(labels)

    def _call_account_deletion_handler(
        self,
        handler: Any,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Call one declared handler operation, failing closed on its errors.

        A handler declares the provider-state errors that block account
        deletion; any other exception is unexpected and propagates, so a
        provider defect is never masked as a user-facing block.
        """
        try:
            return getattr(handler, method_name)(*args, **kwargs)
        except Exception as exc:
            if not _provider_error_is_blocking(handler, exc):
                raise
            raise _AccountDeletionProviderBlocked(str(exc)) from exc
