"""Startup checks for the QuickScale storage module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime.register_module_checks``, so a failure refuses
``runserver``, ``migrate``, and ``manage.py check`` alike.  Rule 35: a
secret a switched-on feature needs must not be empty.

Rule 12: the declared options (presence, type, choices, the cross-option
credential rules) are validated by the generic settings check registered
alongside this one.  This check covers the credential pair's runtime shape:
both credentials empty may fall back to boto3's default credential chain,
while a half-configured static pair is refused.
"""

from __future__ import annotations

from django.conf import settings
from django.core.checks import CheckMessage, Error
from django.core.exceptions import ImproperlyConfigured

from quickscale_modules_storage._helpers import select_storage_backend

#: The declared settings the backend selection reads.  While any is absent
#: the check stays silent: the generic settings check reports the missing
#: declared setting, and the applied settings arrive together through
#: ``quickscale apply``.
_DECLARED_SETTINGS = (
    "QUICKSCALE_STORAGE_BACKEND",
    "AWS_STORAGE_BUCKET_NAME",
    "AWS_S3_ENDPOINT_URL",
    "AWS_S3_REGION_NAME",
    "AWS_DEFAULT_ACL",
    "AWS_QUERYSTRING_AUTH",
)


def check_vendor_secrets(
    _app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup when an s3-compatible backend lacks its credentials.

    Local storage needs no credentials, and an s3-compatible backend with both
    credentials empty may resolve them from boto3's default credential chain;
    only a half-configured static pair is invalid.  The projected credential
    settings (``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``) are not
    manifest options — ``apply`` writes them alongside the declared settings —
    so a missing one is reported here rather than silently skipped.
    """
    if not hasattr(settings, "QUICKSCALE_STORAGE_ENABLED"):
        # Pre-apply: the generic settings check reports the missing declared
        # setting, and the credential pair is not evaluated yet.
        return []
    if not bool(settings.QUICKSCALE_STORAGE_ENABLED):
        # Rule 1 (D3): a module switched off has no switched-on feature, so
        # its credential requirement does not apply while it is off.
        return []
    if any(not hasattr(settings, name) for name in _DECLARED_SETTINGS):
        return []

    try:
        selection = select_storage_backend(settings)
    except ImproperlyConfigured as exc:
        # A missing projected credential, or a backend value the generic
        # settings check also refuses; report it here so neither stays silent.
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
