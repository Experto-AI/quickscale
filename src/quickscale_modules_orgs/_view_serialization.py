"""Serialization helpers shared by the org HTML and JSON views.

``views.py`` resolves these private helpers from this module (Module
Conventions rule 28).
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from django.core.exceptions import ValidationError

from quickscale_modules_orgs.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    OrgRole,
)


def _normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def _get_inviter_display_name(user: Any) -> str:
    get_full_name = getattr(user, "get_full_name", None)
    full_name = str(get_full_name()).strip() if callable(get_full_name) else ""
    if full_name:
        return full_name

    get_username = getattr(user, "get_username", None)
    username = str(get_username()).strip() if callable(get_username) else ""
    if username:
        return username

    email = str(getattr(user, "email", "")).strip()
    return email or "QuickScale"


def _serialize_organization(
    organization: Organization,
    *,
    role: str | None = None,
    member_count: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(organization.id),
        "name": organization.name,
        "slug": organization.slug,
        "is_personal": organization.is_personal,
    }
    if role is not None:
        payload["role"] = role
        payload["role_label"] = str(OrgRole(role).label)
    if member_count is not None:
        payload["member_count"] = member_count
    return payload


def _serialize_membership(membership: OrganizationMembership) -> dict[str, Any]:
    return {
        "id": membership.pk,
        "role": membership.role,
        "role_label": str(OrgRole(membership.role).label),
        "joined_at": membership.joined_at.astimezone(UTC).isoformat(),
        "user": {
            "id": str(membership.user.pk),
            "username": str(membership.user.get_username()),
            "email": str(getattr(membership.user, "email", "")),
            "display_name": _get_inviter_display_name(membership.user),
        },
    }


def _serialize_invitation(invitation: OrganizationInvitation) -> dict[str, Any]:
    return {
        "id": str(invitation.pk),
        "email": invitation.email,
        "role": invitation.role,
        "role_label": str(OrgRole(invitation.role).label),
        "expires_at": invitation.expires_at.astimezone(UTC).isoformat(),
    }


def _serialize_role_choices(
    role_choices: list[tuple[str, str]],
) -> list[dict[str, str]]:
    return [{"value": str(value), "label": str(label)} for value, label in role_choices]


def _form_error_data(form: Any) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    for field, messages in form.errors.items():
        error_key = "non_field_errors" if field == "__all__" else str(field)
        errors[error_key] = [str(message) for message in messages]
    return errors


def _validation_error_data(error: ValidationError) -> dict[str, list[str]]:
    if hasattr(error, "message_dict"):
        return {
            ("non_field_errors" if field == "__all__" else str(field)): [
                str(message) for message in messages
            ]
            for field, messages in error.message_dict.items()
        }
    return {"non_field_errors": [str(message) for message in error.messages]}


def _first_error_message(
    error: ValidationError,
    *,
    fallback: str,
) -> str:
    for messages in _validation_error_data(error).values():
        if messages:
            return messages[0]
    return fallback
