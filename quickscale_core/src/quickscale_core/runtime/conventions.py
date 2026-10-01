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
* :func:`register_module_settings_check` — rule 3's generic settings check.
  A module calls it from ``ready()`` with its own module name; the check
  validates every setting declared in the project's ``MODULE_SETTINGS_SCHEMA``
  (written by ``quickscale apply``) against the manifest's type and validation
  vocabulary, without coercion, and fails startup naming the setting and the
  fix.  Core holds no per-module names; the schema comes from the project.
* :func:`exception_handler` — rule 9's single QuickScale HTTP error shape,
  installed as ``REST_FRAMEWORK["EXCEPTION_HANDLER"]`` by the generated
  settings.

The root ``quickscale_core.runtime`` facade exposes all four lazily, so
importing the facade in a process without Django (CLI ``plan``/``apply``)
never imports this module.  :func:`exception_handler` imports DRF inside the
call, so a project without a DRF-embedding module never imports
``rest_framework`` either.
"""

from __future__ import annotations

import os
import sys

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Any, cast

from django.apps import AppConfig, apps
from django.conf import settings
from django.core.checks import CheckMessage, Error, register
from django.core.exceptions import ImproperlyConfigured

from quickscale_core.manifest.settings_schema import collect_setting_issues

if TYPE_CHECKING:
    from rest_framework.response import Response

__all__ = [
    "collect_capabilities",
    "exception_handler",
    "register_module_checks",
    "register_module_settings_check",
]

#: The callable contract of a module check: Django's system-check signature,
#: returning every issue it found.  A check may also raise instead of
#: returning; :func:`register_module_checks` counts that as a failure too.
#: ``None`` is typed in so the eager run can reject it loudly rather than
#: registering a callable Django's own check framework would crash on.
CheckCallable = Callable[..., Sequence[CheckMessage] | None]

#: What Django's check registry accepts: the same call without the ``None``.
_RegisteredCheck = Callable[..., Sequence[CheckMessage]]

#: One-shot escape hatch naming modules (comma-separated labels, or ``all``)
#: whose eager startup run is skipped.  The generated image build sets it so
#: ``collectstatic`` can run without runtime credentials; registration still
#: happens, and it is effective only in a ``collectstatic`` invocation, so a
#: value left in a serving environment (a Compose ``.env``, a platform
#: variable) never bypasses the checks.  The launcher never sets it.
_SKIP_EAGER_CHECKS_ENV_VAR = "QUICKSCALE_SKIP_MODULE_CHECKS"

#: The one Django command the skip is effective for.
_SKIP_EAGER_CHECKS_COMMAND = "collectstatic"

#: The argv[0] basenames that identify Django's management entry points, so a
#: serving executable whose first argument merely reads ``collectstatic``
#: (for example ``gunicorn collectstatic`` serving a module of that name)
#: never matches.
_MANAGEMENT_ENTRY_POINTS = frozenset({"manage.py", "django-admin", "django-admin.py"})

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


def _eager_run_is_skipped(label: str) -> bool:
    """Return whether the one-shot skip names *label* (or ``all``).

    Effective only in a genuine Django management invocation of the
    ``collectstatic`` command — ``sys.argv[0]`` basenamed to ``manage.py`` or
    ``django-admin`` and ``sys.argv[1]`` equal to ``collectstatic`` — the
    generated image build's credential-free step.  A skip value that survives
    into a serving process, or a serving executable whose argument merely
    reads ``collectstatic``, cannot disable the checks there.
    """
    if os.path.basename(sys.argv[0]) not in _MANAGEMENT_ENTRY_POINTS:
        return False
    if len(sys.argv) < 2 or sys.argv[1] != _SKIP_EAGER_CHECKS_COMMAND:
        return False
    declared = os.environ.get(_SKIP_EAGER_CHECKS_ENV_VAR, "").strip()
    if not declared:
        return False
    entries = {entry.strip() for entry in declared.split(",") if entry.strip()}
    return "all" in entries or label in entries


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

    A one-shot ``QUICKSCALE_SKIP_MODULE_CHECKS`` naming this label (or
    ``all``) skips the eager run and only registers the callables, and only
    while the invoked command is ``collectstatic``.  The generated image build
    uses it for its credential-free ``collectstatic`` step; a skip value that
    survives into a serving process (a platform variable, a loaded ``.env``)
    therefore cannot disable the checks there.

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
    for check in check_functions:
        if not callable(check):
            raise ValueError(
                f"{label!r} passes {check!r} to register_module_checks(); expected "
                "a check callable."
            )
    if _eager_run_is_skipped(label):
        for check in check_functions:
            register(label)(cast("_RegisteredCheck", check))
        return
    failures: list[str] = []
    for check in check_functions:
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


#: The managed-settings block ``quickscale apply`` writes and this check reads.
_SETTINGS_SCHEMA_ATTRIBUTE = "MODULE_SETTINGS_SCHEMA"

#: System-check ids for the failures the generic settings check reports.
_SETTINGS_SCHEMA_MISSING_ID = "quickscale_settings.E001"
_SETTINGS_MISSING_ID = "quickscale_settings.E002"
_SETTINGS_INVALID_ID = "quickscale_settings.E003"
_SETTINGS_RETIRED_ID = "quickscale_settings.E004"

#: The operator fix every settings failure names.
_SETTINGS_APPLY_HINT = "Run `quickscale apply` to regenerate the managed settings."


def register_module_settings_check(
    app_config: AppConfig,
    module_name: str,
    *,
    retired_settings: Mapping[str, str] | None = None,
) -> None:
    """Run and register rule 3's generic settings check for *module_name*.

    A module calls this from ``ready()`` for its own name.  The check reads
    the project's ``settings.MODULE_SETTINGS_SCHEMA`` — written by
    ``quickscale apply`` — and validates every declared setting of
    *module_name*: the setting must exist, and its value must satisfy the
    declared type and validation block.  Validation never coerces, so a
    string where an integer is declared is refused rather than converted.
    Every failure names the setting, the rule, and the ``quickscale apply``
    fix.

    A module whose settings were renamed hands in *retired_settings* — a
    mapping of each retired setting name to the message naming its
    replacement.  A retired name still defined in the project's settings is
    refused with that message (rule 6), independently of the managed schema:
    a dead setting left in a project's configuration must fail loudly rather
    than disappear silently.

    Args:
        app_config: The module's app config; its label tags the registered
            system check and names the module in aggregated failures.
        module_name: The module's name — the key its schema is stored under
            in ``MODULE_SETTINGS_SCHEMA``.
        retired_settings: Optional mapping of retired setting names to the
            messages naming their replacements.

    Raises:
        ValueError: when *module_name* is not a non-empty string, or when
            *retired_settings* is not a mapping of non-empty names to
            non-empty messages.
        ImproperlyConfigured: when the project's schema or any declared
            setting is missing or invalid, or a retired setting is present.
    """
    if not isinstance(module_name, str) or not module_name:
        raise ValueError(
            "register_module_settings_check() requires a non-empty module name."
        )
    if retired_settings is not None:
        if not isinstance(retired_settings, Mapping):
            raise ValueError(
                "register_module_settings_check() requires retired_settings to "
                "be a mapping of retired setting names to replacement messages."
            )
        for retired_name, message in retired_settings.items():
            if not isinstance(retired_name, str) or not retired_name:
                raise ValueError(
                    "register_module_settings_check() requires non-empty retired "
                    "setting names."
                )
            if not isinstance(message, str) or not message:
                raise ValueError(
                    "register_module_settings_check() requires a non-empty "
                    f"replacement message for retired setting {retired_name!r}."
                )
    register_module_checks(
        app_config, [_module_settings_check(module_name, retired_settings)]
    )


def _module_settings_check(
    module_name: str,
    retired_settings: Mapping[str, str] | None = None,
) -> CheckCallable:
    """Return the generic settings check bound to *module_name*."""

    def check(app_configs: object = None, **kwargs: object) -> list[CheckMessage]:
        return _module_settings_issues(module_name, retired_settings)

    return check


def _declared_setting_is_supplied(setting_name: str) -> bool:
    """Return whether the managed wiring supplied *setting_name*.

    In a generated project ``settings/modules.py`` contributes both the
    ``MODULE_SETTINGS`` mapping and the schema, and ``settings/base.py``
    applies the mapping; a declared setting absent from that mapping was not
    written by ``apply``, even when a base template default or a library
    default happens to define the name.  Without the managed mapping (module
    test settings, standalone configurations) the configured settings must
    explicitly set the name; Django's ``is_overridden`` distinguishes that
    from a global or third-party default.
    """
    managed = getattr(settings, "MODULE_SETTINGS", None)
    if isinstance(managed, Mapping):
        return setting_name in managed and hasattr(settings, setting_name)
    is_overridden = getattr(settings, "is_overridden", None)
    if not callable(is_overridden):
        return hasattr(settings, setting_name)
    return bool(hasattr(settings, setting_name) and is_overridden(setting_name))


def _retired_setting_issues(
    retired_settings: Mapping[str, str] | None,
) -> list[CheckMessage]:
    """Refuse every retired setting name the project's settings still define.

    The map is the module's own declaration, so the refusal works before the
    project is re-applied: the settings a previous release wrote are exactly
    the ones that must disappear.
    """
    if not retired_settings:
        return []
    return [
        Error(message, id=_SETTINGS_RETIRED_ID)
        for retired_name, message in sorted(retired_settings.items())
        if hasattr(settings, retired_name)
    ]


def _module_settings_issues(
    module_name: str,
    retired_settings: Mapping[str, str] | None = None,
) -> list[CheckMessage]:
    """Validate the project's declared settings for *module_name*."""
    issues: list[CheckMessage] = _retired_setting_issues(retired_settings)
    schema_all = getattr(settings, _SETTINGS_SCHEMA_ATTRIBUTE, None)
    if not isinstance(schema_all, Mapping):
        issues.append(
            Error(
                f"settings.{_SETTINGS_SCHEMA_ATTRIBUTE} is missing or malformed; "
                f"the managed module settings wiring is out of date. "
                f"{_SETTINGS_APPLY_HINT}",
                id=_SETTINGS_SCHEMA_MISSING_ID,
            )
        )
        return issues
    module_schema = schema_all.get(module_name)
    if not isinstance(module_schema, Mapping) or not module_schema:
        issues.append(
            Error(
                f"No settings schema for module {module_name!r}; the module is "
                f"installed but the managed module settings wiring does not "
                f"declare it. {_SETTINGS_APPLY_HINT}",
                id=_SETTINGS_SCHEMA_MISSING_ID,
            )
        )
        return issues

    values: dict[str, object] = {}
    for option_name, entry in sorted(module_schema.items()):
        if not isinstance(entry, Mapping):
            raise ValueError(
                f"Malformed schema entry for option {option_name!r} of module "
                f"{module_name!r}; expected a mapping."
            )
        setting_name = entry.get("setting")
        if not isinstance(setting_name, str) or not setting_name:
            raise ValueError(
                f"Malformed schema entry for option {option_name!r} of module "
                f"{module_name!r}; expected a 'setting' name."
            )
        if not _declared_setting_is_supplied(setting_name):
            issues.append(
                Error(
                    f"{setting_name} is not set. {_SETTINGS_APPLY_HINT}",
                    id=_SETTINGS_MISSING_ID,
                )
            )
            continue
        values[option_name] = getattr(settings, setting_name)

    for issue in collect_setting_issues(module_name, module_schema, values):
        issues.append(
            Error(
                f"{issue.message}. {_SETTINGS_APPLY_HINT}",
                id=_SETTINGS_INVALID_ID,
            )
        )
    return issues


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
