"""Account-anonymization executor for blog's personal data.

``QuickscaleBlogConfig.anonymize_account`` delegates here.  The author profile
belongs to the person even though its posts belong to the organization, so the
profile row stays — attributed to the deleted account — and only the personal
fields are cleared.

The stored avatar file is deleted on commit (Module Conventions rule 21): a
rolled-back account deletion leaves the file in storage, and the profile row's
field is cleared in the same transaction as the rest of the scrub.  The
callback cannot raise once the transaction has committed — the account
deletion is already durable, so a storage error is reported for manual cleanup
instead of surfacing as a failed removal (which the account-deletion boundary
would otherwise compensate as if its transaction had rolled back).
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from quickscale_modules_blog.models import AuthorProfile

logger = logging.getLogger("quickscale_modules_blog.apps")


def anonymize_account(
    user: Any,
    original_email: str,
    original_name: str,
    original_username: str,
) -> None:
    """Clear the person's author profile and queue its avatar file deletion.

    The pre-scrub identity arguments are unused; the profile is reached by the
    user link.
    """
    del original_email, original_name, original_username
    profile = AuthorProfile.objects.filter(user=user).first()
    if profile is None:
        return

    avatar = profile.avatar
    avatar_name = (avatar.name or "") if avatar else ""
    if avatar_name:
        storage = avatar.storage
        transaction.on_commit(lambda: _delete_stored_file(storage, avatar_name))

    profile.bio = ""
    profile.avatar = None
    profile.save(update_fields=["bio", "avatar"])


def _delete_stored_file(storage: Any, name: str) -> None:
    """Delete one stored file, reporting a failure without raising.

    Runs on commit, after the deletion transaction is durable; an error must
    not escape because the caller cannot roll the removal back, and the
    account-deletion boundary would read the escaped error as a failed
    deletion and compensate provider state that was already cancelled.
    """
    try:
        storage.delete(name)
    except Exception:  # noqa: BLE001 - the committed removal cannot be rolled back
        logger.exception(
            "Failed to delete the anonymized author avatar %r; "
            "remove it from storage manually.",
            name,
        )
