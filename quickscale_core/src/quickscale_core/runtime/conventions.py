"""Shared runtime helpers every first-party module builds its conventions on.

This module is the one implementation of the three cross-module conventions:

* :func:`collect_capabilities` — Module Conventions rule 4's ``AppConfig``
  capability collector.  A module declares what it provides as an attribute
  on its own :class:`~django.apps.AppConfig` (a tuple, or a method returning
  one); a consumer asks this helper for every installed provider instead of
  knowing the provider's label, setting, or internals.
* :func:`register_module_checks` — rule 10's startup-check runner.  A module
  passes the functions from its ``checks.py`` from ``ready()``; the helper
  runs them in every process (so a WSGI server fails too, not only
  ``manage.py check``), aggregates every failure into one
  :class:`~django.core.exceptions.ImproperlyConfigured`, and registers the
  same functions as system checks tagged with the module's app label.
* :func:`exception_handler` — rule 9's single QuickScale HTTP error shape,
  installed as ``REST_FRAMEWORK["EXCEPTION_HANDLER"]`` by the generated
  settings.

The root ``quickscale_core.runtime`` facade exposes all three lazily, so
importing the facade in a process without Django (CLI ``plan``/``apply``)
never imports this module.  :func:`exception_handler` imports DRF inside the
call, so a project without a DRF-embedding module never imports
``rest_framework`` either.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Any, cast

from django.apps import AppConfig, apps
from django.core.checks import CheckMessage, register
from django.core.exceptions import ImproperlyConfigured

if TYPE_CHECKING:
    from rest_framework.response import Response

__all__ = [
    "collect_capabilities",
    "exception_handler",
    "register_module_checks",
]

#: The callable contract of a module check: Django's system-check signature,
#: returning every issue it found.  A check may also raise instead of
#: returning; :func:`register_module_checks` counts that as a failure too.
#: ``None`` is typed in so the eager run can reject it loudly rather than
#: registering a callable Django's own check framework would crash on.
CheckCallable = Callable[..., Sequence[CheckMessage] | None]

#: What Django's check registry accepts: the same call without the ``None``.
_RegisteredCheck = Callable[..., Sequence[CheckMessage]]

_VALIDATION_ERROR_CODE = "validation_error"
_VALIDATION_ERROR_MESSAGE = "Invalid input."
_NON_FIELD_ERRORS_KEY = "non_field_errors"


def collect_capabilities(capability: str) -> tuple[object, ...]:
    """Return every capability declared for *capability* by an installed app.

    An app declares a capability by exposing an attribute named *capability*
    on its :class:`~django.apps.AppConfig` — either the entries themselves or
    a method returning them.  An app that declares nothing for the name
    contributes nothing; a declaration that cannot be read fails loudly
    instead of being read as an app that provides nothing.

    Entries are collected in app-label order so the result is deterministic,
    and only from the apps installed right now.  Whether a switched-off
    provider contributes is the declaring module's decision: it returns an
    empty declaration when it is off, so a consumer never needs the
    provider's setting name.

    Args:
        capability: The attribute name a provider declares, for example
            ``"account_deletion_handlers"``.

    Returns:
        The declared entries, concatenated in app-label order.

    Raises:
        ValueError: when *capability* is not a non-empty string, or when an
            installed app declares it as ``None``, a string, a mapping, a
            one-shot iterator, or a non-iterable, or when reading a declared
            attribute raises ``AttributeError``.
    """
    if not isinstance(capability, str) or not capability:
        raise ValueError("collect_capabilities() requires a non-empty capability name.")
    collected: list[object] = []
    for app_config in sorted(apps.get_app_configs(), key=lambda config: config.label):
        collected.extend(_declared_capabilities(app_config, capability))
    return tuple(collected)


def _declares_attribute(app_config: AppConfig, capability: str) -> bool:
    """Return whether *app_config* declares the attribute at all."""
    if capability in vars(app_config):
        return True
    return any(capability in vars(klass) for klass in type(app_config).__mro__)


def _declared_capabilities(
    app_config: AppConfig, capability: str
) -> tuple[object, ...]:
    """Return one app's declaration, rejecting an unreadable one."""
    try:
        declaration = getattr(app_config, capability)
    except AttributeError as exc:
        if not _declares_attribute(app_config, capability):
            return ()
        raise ValueError(
            f"{app_config.label!r} declares {capability!r} but reading it raised "
            f"AttributeError: {exc}"
        ) from exc
    if callable(declaration):
        declaration = declaration()
    if declaration is None:
        raise ValueError(
            f"{app_config.label!r} declares {capability!r} as None; expected a "
            "tuple of capability entries or a method returning one."
        )
    if isinstance(declaration, (str, bytes, bytearray)):
        raise ValueError(
            f"{app_config.label!r} declares {capability!r} as a string; expected "
            "a tuple of capability entries or a method returning one."
        )
    if isinstance(declaration, Mapping):
        raise ValueError(
            f"{app_config.label!r} declares {capability!r} as a mapping; expected "
            "a tuple of capability entries or a method returning one."
        )
    if isinstance(declaration, Iterator):
        raise ValueError(
            f"{app_config.label!r} declares {capability!r} as a one-shot iterator; "
            "expected a repeatable tuple of capability entries or a method "
            "returning one."
        )
    try:
        return tuple(cast("Iterable[object]", declaration))
    except TypeError as exc:
        raise ValueError(
            f"{app_config.label!r} declares a non-iterable {capability!r}; expected "
            "a tuple of capability entries or a method returning one."
        ) from exc


def register_module_checks(
    app_config: AppConfig,
    checks: Iterable[CheckCallable],
) -> None:
    """Run *checks* eagerly and register them as system checks for *app_config*.

    A module calls this from ``ready()`` with the functions defined in its
    ``checks.py``.  Every check is called with ``app_configs=None`` (Django's
    "all installed apps" convention); a check that raises counts as one
    failure, so raising validators and message-returning checks can sit side
    by side.  Every failure at or above Django's error level is aggregated
    into one :class:`~django.core.exceptions.ImproperlyConfigured`, which
    fails startup in every process, including a WSGI server that never runs
    Django system checks.

    After the eager run passes, the same callables are registered as system
    checks tagged with ``app_config.label``, so ``manage.py check`` reports
    them (including warning-level messages, which do not block startup).

    Args:
        app_config: The module's app config; its label is the system-check tag
            and the name failure messages carry.
        checks: The module's check callables.

    Raises:
        ValueError: when an entry is not callable, or returns anything other
            than a sequence of messages (Django's check protocol requires
            one).
        ImproperlyConfigured: when any check fails.
    """
    label = app_config.label
    check_functions = tuple(checks)
    failures: list[str] = []
    for check in check_functions:
        if not callable(check):
            raise ValueError(
                f"{label!r} passes {check!r} to register_module_checks(); expected "
                "a check callable."
            )
        try:
            result: object = check(app_configs=None)
        except Exception as exc:  # A raising check is one aggregated failure.
            failures.append(f"{exc.__class__.__name__}: {exc}")
            continue
        if (
            result is None
            or isinstance(result, (str, bytes, bytearray))
            or not isinstance(result, Iterable)
        ):
            raise ValueError(
                f"{label!r} passed {check!r} to register_module_checks(); a check "
                "must return a sequence of CheckMessage."
            )
        for message in result:
            if not isinstance(message, CheckMessage):
                raise ValueError(
                    f"{label!r} passed {check!r} to register_module_checks(); it "
                    f"returned {message!r} instead of CheckMessage entries."
                )
            if message.is_serious():
                identifier = f"{message.id}: " if message.id else ""
                failures.append(f"{identifier}{message.msg}")
    if failures:
        details = "\n".join(f"  - {failure}" for failure in failures)
        raise ImproperlyConfigured(
            f"QuickScale startup checks failed for {label!r}:\n{details}"
        )
    for check in check_functions:
        register(label)(cast("_RegisteredCheck", check))


def exception_handler(
    exc: Exception,
    context: Mapping[str, Any],
) -> Response | None:
    """Return DRF's response carrying the one QuickScale error shape.

    Produces ``{"error": {"code", "message", "fields"}}``: ``code`` is a
    stable snake_case string, ``message`` is human-readable, and ``fields``
    appears only for validation errors, where it maps a field name to its
    messages.  The HTTP status carries the class of error.

    An exception DRF's own handler does not translate returns ``None``, so an
    unexpected server error keeps Django's error handling instead of being
    answered as if it were a known API error.

    Args:
        exc: The exception DRF caught.
        context: DRF's exception-handler context (unused; part of the
            ``EXCEPTION_HANDLER`` call contract).

    Returns:
        A DRF response with the QuickScale error body, or ``None`` for an
        exception outside DRF's handled classes.
    """
    from rest_framework.views import exception_handler as drf_exception_handler

    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    from rest_framework.exceptions import ValidationError

    if isinstance(exc, ValidationError):
        fields = _validation_fields(exc.detail)
        error: dict[str, object] = {
            "code": _VALIDATION_ERROR_CODE,
            "message": _VALIDATION_ERROR_MESSAGE,
            "fields": fields,
        }
    else:
        code = _error_code(exc)
        error = {"code": code, "message": _error_message(exc, code)}
    response.data = {"error": error}
    return response


def _validation_fields(detail: object, prefix: str = "") -> dict[str, list[str]]:
    """Normalize a validation detail into a field-to-messages mapping.

    A nested serializer error becomes a dotted field path — ``{"address":
    {"city": ["Required."]}}`` normalizes to ``{"address.city": ["Required."]}``
    — and a nested ``many=True`` serializer adds the item position —
    ``{"addresses": [{}, {"city": ["Required."]}]}`` normalizes to
    ``{"addresses[1].city": ["Required."]}`` — so every entry stays a plain
    list of human-readable strings that names the offending field.
    """
    if isinstance(detail, Mapping):
        fields: dict[str, list[str]] = {}
        for key, value in detail.items():
            field = f"{prefix}.{key}" if prefix else str(key)
            _collect_field_messages(fields, field, value)
        return fields
    if isinstance(detail, (list, tuple)) and any(
        isinstance(item, Mapping) for item in detail
    ):
        fields = {}
        _collect_field_messages(fields, prefix or _NON_FIELD_ERRORS_KEY, detail)
        return fields
    return {prefix or _NON_FIELD_ERRORS_KEY: _message_list(detail)}


def _collect_field_messages(
    fields: dict[str, list[str]], field: str, value: object
) -> None:
    """Place *value*'s messages under *field*, indexing nested many serializers."""
    if isinstance(value, Mapping):
        for nested_field, messages in _validation_fields(value, field).items():
            fields.setdefault(nested_field, []).extend(messages)
        return
    if isinstance(value, (list, tuple)):
        nested_errors = [item for item in value if isinstance(item, Mapping)]
        if nested_errors:
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    if item:
                        _collect_field_messages(fields, f"{field}[{index}]", item)
                else:
                    fields.setdefault(field, []).append(_message_text(item))
            return
        if value:
            fields.setdefault(field, []).extend(_message_list(value))
        return
    fields.setdefault(field, []).append(_message_text(value))


def _message_list(value: object) -> list[str]:
    """Return one field's messages as plain strings."""
    if isinstance(value, (list, tuple)):
        return [_message_text(message) for message in value]
    return [_message_text(value)]


def _message_text(value: object) -> str:
    """Render one message, flattening any structure a custom error carries."""
    if isinstance(value, Mapping):
        return "; ".join(f"{key}: {_message_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return "; ".join(_message_text(item) for item in value)
    return str(value)


def _error_code(exc: Exception) -> str:
    """Return the stable snake_case code for *exc*."""
    from django.core.exceptions import PermissionDenied
    from django.http import Http404
    from rest_framework.exceptions import APIException

    if isinstance(exc, APIException):
        codes = exc.get_codes()
        if isinstance(codes, str) and codes:
            return codes
        default_code = getattr(exc, "default_code", "")
        return str(default_code) if default_code else "error"
    if isinstance(exc, Http404):
        return "not_found"
    if isinstance(exc, PermissionDenied):
        return "permission_denied"
    return "error"


def _error_message(exc: Exception, code: str) -> str:
    """Return the human-readable message for *exc*."""
    detail = getattr(exc, "detail", None)
    if isinstance(detail, str) and detail:
        return str(detail)
    return f"{code.replace('_', ' ').capitalize()}."
