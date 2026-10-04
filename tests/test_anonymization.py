"""Tests for blog's account-anonymization executor."""

from __future__ import annotations

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from PIL import Image

from quickscale_modules_blog._anonymization import anonymize_account
from quickscale_modules_blog.models import AuthorProfile


def _avatar_upload(name: str = "avatar.png") -> SimpleUploadedFile:
    """Return a small in-memory PNG for the profile's avatar field."""
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color="teal").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@pytest.mark.django_db
def test_anonymize_clears_the_profile_fields(user) -> None:
    """The profile row stays; its personal fields are cleared."""
    profile = AuthorProfile.objects.create(user=user, bio="Personal bio")

    anonymize_account(user, "test@example.com", "Test User", user.get_username())

    profile.refresh_from_db()
    assert profile.bio == ""
    assert not profile.avatar


@pytest.mark.django_db
def test_anonymize_without_a_profile_is_a_no_op(user) -> None:
    """A person who never authored keeps no profile row to clear."""
    anonymize_account(user, "test@example.com", "Test User", user.get_username())

    assert not AuthorProfile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_anonymize_deletes_the_avatar_file_on_commit(
    user, django_capture_on_commit_callbacks
) -> None:
    """The stored file is deleted on commit, not inside the transaction."""
    profile = AuthorProfile.objects.create(
        user=user, bio="Bio", avatar=_avatar_upload()
    )
    storage = profile.avatar.storage
    name = profile.avatar.name
    assert storage.exists(name)

    with django_capture_on_commit_callbacks(execute=True):
        anonymize_account(user, "test@example.com", "Test User", user.get_username())

    profile.refresh_from_db()
    assert profile.bio == ""
    assert not profile.avatar
    assert not storage.exists(name)


@pytest.mark.django_db
def test_anonymize_reports_a_failed_avatar_deletion_without_raising(
    user, django_capture_on_commit_callbacks, monkeypatch, caplog
) -> None:
    """The committed deletion cannot roll back, so a storage error is logged."""
    import logging

    profile = AuthorProfile.objects.create(
        user=user, bio="Bio", avatar=_avatar_upload()
    )
    storage = profile.avatar.storage

    def failing_delete(name: str) -> None:
        raise OSError("storage unavailable")

    monkeypatch.setattr(storage, "delete", failing_delete)

    with caplog.at_level(logging.ERROR, logger="quickscale_modules_blog.apps"):
        with django_capture_on_commit_callbacks(execute=True):
            anonymize_account(
                user, "test@example.com", "Test User", user.get_username()
            )

    assert "remove it from storage manually" in caplog.text
    profile.refresh_from_db()
    assert not profile.avatar


@pytest.mark.django_db
def test_rolled_back_anonymization_keeps_the_avatar_file(user) -> None:
    """A rolled-back scrub leaves the file and the profile untouched."""
    profile = AuthorProfile.objects.create(
        user=user, bio="Bio", avatar=_avatar_upload()
    )
    storage = profile.avatar.storage
    name = profile.avatar.name

    class _Rollback(Exception):
        pass

    with pytest.raises(_Rollback):
        with transaction.atomic():
            anonymize_account(
                user, "test@example.com", "Test User", user.get_username()
            )
            raise _Rollback

    profile.refresh_from_db()
    assert profile.bio == "Bio"
    assert storage.exists(name)
