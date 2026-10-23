"""Rule 9's error-shape helpers for the shared exception handler.

Split out of :mod:`quickscale_core.runtime.conventions` — which stays the one
public home of
:func:`~quickscale_core.runtime.conventions.exception_handler` — so the facade
module stays within the repository's file-size budget.  The handler is the
only caller: it renders DRF-handled errors and module errors that declare
``status_code``/``default_code`` (rule 10) in the one QuickScale shape.
"""

from __future__ import annotations

from collections.abc import Mapping

_VALIDATION_ERROR_CODE = "validation_error"
_VALIDATION_ERROR_MESSAGE = "Invalid input."
_NON_FIELD_ERRORS_KEY = "non_field_errors"


def _declared_error(exc: Exception) -> tuple[int, str] | None:
    """Return the ``(status_code, default_code)`` a non-DRF error declares.

    Rule 10 lets a module's error carry the status and stable code an API
    caller sees without deriving from DRF's ``APIException``.  An exception
    opts in by declaring both attributes on its class; anything else keeps
    Django's own error handling.  A malformed declaration (a boolean, a
    non-integer status, an out-of-range status, an empty code) is not
    rendered, so a broken class cannot crash the handler itself.
    """
    status_code = getattr(exc, "status_code", None)
    default_code = getattr(exc, "default_code", None)
    if isinstance(status_code, bool) or not isinstance(status_code, int):
        return None
    if not isinstance(default_code, str) or not default_code:
        return None
    if not 100 <= status_code <= 599:
        return None
    return status_code, default_code


def _declared_error_message(exc: Exception, code: str) -> str:
    """Return the human-readable message for a declared non-DRF error.

    The raised message is used when present; a class-level
    ``default_detail`` stands in when the error was raised bare, and the
    code-derived text is the last resort, matching the DRF path's fallback.
    """
    text = str(exc)
    if text:
        return text
    default_detail = getattr(exc, "default_detail", None)
    if isinstance(default_detail, str) and default_detail:
        return default_detail
    return f"{code.replace('_', ' ').capitalize()}."


def _validation_fields(detail: object, prefix: str = "") -> dict[str, list[str]]:
    """Normalize a validation detail into a field-to-messages mapping.

    A nested serializer error becomes a dotted field path — ``{"address":
    {"city": ["Required."]}}`` normalizes to ``{"address.city": ["Required."]}``
    — and a nested ``many=True`` serializer adds the item position. DRF emits
    that position as a list on older releases and as an index-keyed mapping on
    3.18+; both ``{"addresses": [{}, {"city": ["Required."]}]}`` and
    ``{"addresses": {1: {"city": ["Required."]}}}`` normalize to
    ``{"addresses[1].city": ["Required."]}`` — so every entry stays a plain
    list of human-readable strings that names the offending field.
    """
    if isinstance(detail, Mapping):
        fields: dict[str, list[str]] = {}
        indexed = bool(prefix) and all(_is_index_key(key) for key in detail)
        for key, value in detail.items():
            if indexed:
                field = f"{prefix}[{key}]"
            else:
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


def _is_index_key(key: object) -> bool:
    """Return whether *key* is a serializer item position, not a field name."""
    return isinstance(key, int) or (isinstance(key, str) and key.isdecimal())


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
