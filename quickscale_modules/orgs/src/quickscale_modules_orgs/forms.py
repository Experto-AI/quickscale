"""Forms for the QuickScale organizations module management views."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from typing import Any, cast

from django import forms
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from .crm_bootstrap import maybe_seed_crm_default_stages
from .models import (
    OrgRole,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)


_INVITATION_EXPIRY_DAYS = 7


def _generated_slug_candidates(name: str) -> Iterator[str]:
    """Yield slug candidates derived from the provided organization name."""

    base_slug = slugify(name.strip())
    if not base_slug:
        raise forms.ValidationError(
            "Enter a name that contains at least one letter or number."
        )

    slug_field = cast(Any, Organization._meta.get_field("slug"))
    max_length = cast(int | None, slug_field.max_length) or len(base_slug)
    truncated_base = base_slug[:max_length].strip("-")
    if not truncated_base:
        raise forms.ValidationError(
            "Enter a name that contains at least one letter or number."
        )

    yield truncated_base

    suffix = 2
    while True:
        suffix_text = f"-{suffix}"
        available_length = max_length - len(suffix_text)
        if available_length <= 0:
            raise RuntimeError("Organization slug max_length is too small.")
        suffixed_base = truncated_base[:available_length].rstrip("-")
        yield f"{suffixed_base}{suffix_text}"
        suffix += 1


def _normalize_unique_slug(
    value: str,
    *,
    exclude_org: Organization | None = None,
) -> str:
    """Return a normalized slug, raising a validation error when unavailable."""

    normalized = slugify(value.strip())
    if not normalized:
        raise forms.ValidationError(
            "Enter a slug that contains at least one letter or number."
        )

    queryset = Organization.objects.all()
    if exclude_org is not None and exclude_org.pk is not None:
        queryset = queryset.exclude(pk=exclude_org.pk)
    if queryset.filter(slug=normalized).exists():
        raise forms.ValidationError("This slug is already in use.")
    return normalized


class OrgCreateForm(forms.Form):
    """Create a new organization from a single display name input."""

    name = forms.CharField(max_length=255)

    def clean_name(self) -> str:
        """Validate and normalize the submitted organization name."""

        name = cast(str, self.cleaned_data["name"]).strip()
        if not name:
            raise forms.ValidationError("This field is required.")
        if not slugify(name):
            raise forms.ValidationError(
                "Enter a name that contains at least one letter or number."
            )
        return name

    def save(self, *, user: Any) -> Organization:
        """Persist the organization and owner membership for the acting user."""

        name = cast(str, self.cleaned_data["name"])
        slug_candidates = _generated_slug_candidates(name)
        with transaction.atomic():
            while True:
                slug = next(slug_candidates)
                try:
                    with transaction.atomic():
                        organization = Organization.objects.create(
                            name=name,
                            slug=slug,
                            is_personal=False,
                        )
                except IntegrityError:
                    continue

                OrganizationMembership.objects.create(
                    user=user,
                    organization=organization,
                    role=OrgRole.OWNER,
                )
                maybe_seed_crm_default_stages(organization)
                return organization


class OrgSettingsForm(forms.ModelForm):
    """Update an organization's display name and slug."""

    class Meta:
        model = Organization
        fields = ["name", "slug"]

    def clean_name(self) -> str:
        """Normalize the submitted organization name."""

        name = cast(str, self.cleaned_data["name"]).strip()
        if not name:
            raise forms.ValidationError("This field is required.")
        return name

    def clean_slug(self) -> str:
        """Normalize the submitted slug and enforce uniqueness."""

        slug = cast(str, self.cleaned_data["slug"])
        return _normalize_unique_slug(
            slug,
            exclude_org=self.instance,
        )


class InviteForm(forms.Form):
    """Create a pending organization invitation with deterministic validation."""

    _CURRENT_MEMBER_ERROR = "This email already belongs to a current member."
    _PENDING_INVITATION_ERROR = "This email already has a pending invitation."

    email = forms.EmailField()
    role = forms.ChoiceField(choices=OrgRole.choices)

    def __init__(
        self,
        *args: Any,
        organization: Organization,
        invited_by: Any,
        owner_like: bool,
        **kwargs: Any,
    ) -> None:
        self.organization = organization
        self.invited_by = invited_by
        super().__init__(*args, **kwargs)
        role_field = cast(forms.ChoiceField, self.fields["role"])
        role_field.choices = self.available_role_choices(owner_like=owner_like)
        self.initial.setdefault("role", OrgRole.MEMBER)

    @staticmethod
    def available_role_choices(*, owner_like: bool) -> list[tuple[str, str]]:
        """Return inviteable roles while keeping owner assignment out of the UI."""

        return [
            (str(value), str(label))
            for value, label in RoleChangeForm.available_role_choices(
                owner_like=owner_like
            )
            if value != OrgRole.OWNER
        ]

    def clean_email(self) -> str:
        """Reject current members and active duplicate invitations deterministically."""

        email = self._normalize_email(self.cleaned_data["email"])
        error_message = self._get_email_availability_error(email)
        if error_message is not None:
            raise forms.ValidationError(error_message)

        return email

    def clean_role(self) -> str:
        """Reject unsupported owner invitations even for tampered submissions."""

        role = cast(str, self.cleaned_data["role"])
        if role == OrgRole.OWNER:
            raise forms.ValidationError(
                "Ownership transfer is not available until a transfer flow exists."
            )
        return role

    def save(self) -> OrganizationInvitation:
        """Persist a normalized pending invitation for the target organization."""

        email = self._normalize_email(self.cleaned_data["email"])

        with transaction.atomic():
            organization = Organization.objects.select_for_update().get(
                pk=self.organization.pk
            )
            error_message = self._get_email_availability_error(
                email,
                organization=organization,
            )
            if error_message is not None:
                raise forms.ValidationError({"email": error_message})

            return OrganizationInvitation.objects.create(
                organization=organization,
                email=email,
                role=cast(str, self.cleaned_data["role"]),
                invited_by=self.invited_by,
                expires_at=timezone.now() + timedelta(days=_INVITATION_EXPIRY_DAYS),
            )

    @staticmethod
    def _normalize_email(value: Any) -> str:
        return str(value).strip().lower()

    def _get_email_availability_error(
        self,
        email: str,
        *,
        organization: Organization | None = None,
    ) -> str | None:
        target_organization = organization or self.organization

        if OrganizationMembership.objects.filter(
            organization=target_organization,
            user__email__iexact=email,
        ).exists():
            return self._CURRENT_MEMBER_ERROR

        if OrganizationInvitation.objects.filter(
            organization=target_organization,
            email__iexact=email,
            accepted_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists():
            return self._PENDING_INVITATION_ERROR

        return None


class RoleChangeForm(forms.Form):
    """Change an existing member's role while enforcing ownership guardrails."""

    role = forms.ChoiceField(choices=OrgRole.choices)

    def __init__(
        self,
        *args: Any,
        target_membership: OrganizationMembership,
        acting_membership: OrganizationMembership | None,
        acting_user_is_superuser: bool = False,
        **kwargs: Any,
    ) -> None:
        self.target_membership = target_membership
        self.owner_like = acting_user_is_superuser or (
            acting_membership is not None and acting_membership.role == OrgRole.OWNER
        )
        super().__init__(*args, **kwargs)
        role_field = cast(forms.ChoiceField, self.fields["role"])
        role_field.choices = self.available_role_choices(owner_like=self.owner_like)
        self.initial.setdefault("role", target_membership.role)

    @staticmethod
    def available_role_choices(*, owner_like: bool) -> list[tuple[str, str]]:
        """Return the role options visible to the acting user."""

        if owner_like:
            return [(str(value), str(label)) for value, label in OrgRole.choices]
        return [
            (str(value), str(label))
            for value, label in OrgRole.choices
            if value != OrgRole.OWNER
        ]

    def clean_role(self) -> str:
        """Validate ownership transfer, demotion, and last-owner constraints."""

        role = cast(str, self.cleaned_data["role"])
        owner_count = self._owner_count()

        if role == OrgRole.OWNER and not self.owner_like:
            raise forms.ValidationError("Only an owner can transfer ownership.")

        if (
            role == OrgRole.OWNER
            and self.target_membership.role != OrgRole.OWNER
            and OrganizationMembership.objects.filter(
                organization=self.target_membership.organization,
                role=OrgRole.OWNER,
            )
            .exclude(pk=self.target_membership.pk)
            .exists()
        ):
            raise forms.ValidationError(
                "Ownership transfer is not available until a transfer flow exists."
            )

        if (
            self.target_membership.role == OrgRole.OWNER
            and role != OrgRole.OWNER
            and owner_count <= 1
        ):
            raise forms.ValidationError("You cannot demote the last owner.")

        return role

    def save(self) -> OrganizationMembership:
        """Persist the validated role change."""

        self.target_membership.role = cast(str, self.cleaned_data["role"])
        self.target_membership.save(update_fields=["role"])
        return self.target_membership

    def _owner_count(self) -> int:
        return cast(
            int,
            OrganizationMembership.objects.filter(
                organization=self.target_membership.organization,
                role=OrgRole.OWNER,
            ).count(),
        )
