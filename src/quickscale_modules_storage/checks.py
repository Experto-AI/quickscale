"""Startup checks for the QuickScale storage module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime.register_module_checks``, so a failure refuses
``runserver``, ``migrate``, and ``manage.py check`` alike.  Rule 35: a
secret a switched-on feature needs must not be empty.
"""

from __future__ import annotations

from django.conf import settings
from django.core.checks import CheckMessage, Error
from django.core.exceptions import ImproperlyConfigured

from quickscale_modules_storage.helpers import select_storage_backend


def check_vendor_secrets(
    app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup when an s3-compatible backend lacks its credentials.

    The selection is read with the module's own helper, so the check and the
    storage wiring agree on the backend and on the credential settings.
    Local storage needs no credentials, and an s3-compatible backend with both
    credentials empty may resolve them from boto3's default credential chain;
    only a half-configured static pair is invalid.
    """
    try:
        selection = select_storage_backend(settings)
    except ImproperlyConfigured as exc:
        return [Error(str(exc), id="quickscale_storage.E001")]

    if not selection.use_s3_compatible:
        return []

    access_key_id = str(selection.options.get("access_key_id", "")).strip()
    secret_access_key = str(selection.options.get("secret_access_key", "")).strip()
    if not access_key_id and not secret_access_key:
        # boto3's default credential chain (instance role, shared config) is
        # the supported non-static path; the storage kwargs omit empty keys so
        # the chain can supply them.  A half-configured pair is an error.
        return []

    messages: list[CheckMessage] = []
    if not access_key_id:
        messages.append(
            Error(
                "QUICKSCALE_STORAGE_BACKEND is "
                f"{selection.backend!r} and AWS_SECRET_ACCESS_KEY is set, but "
                "AWS_ACCESS_KEY_ID is empty. Set both credentials or neither.",
                id="quickscale_storage.E002",
            )
        )
    if not secret_access_key:
        messages.append(
            Error(
                "QUICKSCALE_STORAGE_BACKEND is "
                f"{selection.backend!r} and AWS_ACCESS_KEY_ID is set, but "
                "AWS_SECRET_ACCESS_KEY is empty. Set both credentials or neither.",
                id="quickscale_storage.E003",
            )
        )
    return messages
