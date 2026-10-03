"""Checked-in personal-data inventory for SA216's account anonymization (SA242).

SA216 disables and scrubs a user account instead of deleting the row, so its
scrub is only as complete as this list.  This inventory names every model field
that holds personal data about a user -- across the shipped modules, Django
contrib, and the installed third-party apps -- with the treatment SA216's
handlers apply to it.

``test_personal_data_inventory.py`` walks every installed model and fails when a
candidate field is neither inventoried here with its treatment nor explicitly
excluded here with a reason.  A candidate field is:

* a relation targeting ``AUTH_USER_MODEL``;
* an ``EmailField``;
* a ``GenericIPAddressField``;
* a file field (``FileField`` / ``ImageField``); or
* a ``TextField`` on a model that references the user.

Analytics (PostHog) events keyed by the user's ``distinct_id`` live outside the
database and are the operator's deletion step; no installed model field records
them.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class PersonalDataTreatment(enum.Enum):
    """The treatment SA216's anonymize handlers apply to an inventoried field."""

    SCRUB = "scrub"
    DELETE = "delete"
    DELETE_FILE = "delete-file"
    KEEP_LINK = "keep-link"


@dataclass(frozen=True)
class PersonalDataField:
    """One model field that holds personal data about a user."""

    app_label: str
    model_name: str
    field_name: str
    treatment: PersonalDataTreatment
    note: str

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the ``(app_label, model_name, field_name)`` lookup key."""
        return (self.app_label, self.model_name, self.field_name)


@dataclass(frozen=True)
class PersonalDataExclusion:
    """A candidate field reviewed and confirmed not to hold personal data."""

    app_label: str
    model_name: str
    field_name: str
    reason: str

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the ``(app_label, model_name, field_name)`` lookup key."""
        return (self.app_label, self.model_name, self.field_name)


PERSONAL_DATA_FIELDS: tuple[PersonalDataField, ...] = (
    # -- auth: the account is disabled and scrubbed, never deleted --
    PersonalDataField(
        app_label="quickscale_auth",
        model_name="User",
        field_name="username",
        treatment=PersonalDataTreatment.SCRUB,
        note="Replaced with 'deleted-<id>'.",
    ),
    PersonalDataField(
        app_label="quickscale_auth",
        model_name="User",
        field_name="email",
        treatment=PersonalDataTreatment.SCRUB,
        note="Replaced with 'deleted-<id>@invalid' so the address can register again.",
    ),
    PersonalDataField(
        app_label="quickscale_auth",
        model_name="User",
        field_name="first_name",
        treatment=PersonalDataTreatment.SCRUB,
        note="Blanked.",
    ),
    PersonalDataField(
        app_label="quickscale_auth",
        model_name="User",
        field_name="last_name",
        treatment=PersonalDataTreatment.SCRUB,
        note="Blanked.",
    ),
    PersonalDataField(
        app_label="quickscale_auth",
        model_name="User",
        field_name="password",
        treatment=PersonalDataTreatment.SCRUB,
        note="Set unusable; the same handler turns is_active off.",
    ),
    PersonalDataField(
        app_label="quickscale_auth",
        model_name="User",
        field_name="last_login",
        treatment=PersonalDataTreatment.SCRUB,
        note="Cleared.",
    ),
    # -- allauth: login addresses exist only for sign-in --
    PersonalDataField(
        app_label="account",
        model_name="EmailAddress",
        field_name="user",
        treatment=PersonalDataTreatment.DELETE,
        note="Row deleted; verified and primary state go with it.",
    ),
    PersonalDataField(
        app_label="account",
        model_name="EmailAddress",
        field_name="email",
        treatment=PersonalDataTreatment.DELETE,
        note="Row deleted.",
    ),
    # -- sessions: active logins --
    PersonalDataField(
        app_label="sessions",
        model_name="Session",
        field_name="session_data",
        treatment=PersonalDataTreatment.DELETE,
        note="The person's session rows are deleted (session_key with them).",
    ),
    # -- orgs: membership and invitations --
    PersonalDataField(
        app_label="quickscale_orgs",
        model_name="OrganizationMembership",
        field_name="user",
        treatment=PersonalDataTreatment.DELETE,
        note="The person leaves every organization; the last-owner guard still applies.",
    ),
    PersonalDataField(
        app_label="quickscale_orgs",
        model_name="OrganizationMembership",
        field_name="invited_by",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Surviving memberships keep the inviter as deleted-user provenance.",
    ),
    PersonalDataField(
        app_label="quickscale_orgs",
        model_name="OrganizationInvitation",
        field_name="email",
        treatment=PersonalDataTreatment.SCRUB,
        note="Pending invitations are withdrawn; accepted and expired rows keep "
        "the record with the address scrubbed.",
    ),
    PersonalDataField(
        app_label="quickscale_orgs",
        model_name="OrganizationInvitation",
        field_name="invited_by",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Pending invitations are withdrawn; accepted rows keep the sender link.",
    ),
    # -- blog: profile and authored content --
    PersonalDataField(
        app_label="quickscale_blog",
        model_name="AuthorProfile",
        field_name="user",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Profile row stays; its bio and avatar are cleared.",
    ),
    PersonalDataField(
        app_label="quickscale_blog",
        model_name="AuthorProfile",
        field_name="bio",
        treatment=PersonalDataTreatment.SCRUB,
        note="Blanked.",
    ),
    PersonalDataField(
        app_label="quickscale_blog",
        model_name="AuthorProfile",
        field_name="avatar",
        treatment=PersonalDataTreatment.DELETE_FILE,
        note="Stored file deleted on commit and the field cleared.",
    ),
    PersonalDataField(
        app_label="quickscale_blog",
        model_name="Post",
        field_name="author",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Post stays attributed to the deleted user.",
    ),
    PersonalDataField(
        app_label="quickscale_blog",
        model_name="BlogMediaAsset",
        field_name="uploaded_by",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Media stays attributed to the deleted user.",
    ),
    # -- notifications: rendered content sent to the person --
    PersonalDataField(
        app_label="quickscale_notifications",
        model_name="NotificationMessage",
        field_name="subject",
        treatment=PersonalDataTreatment.SCRUB,
        note="Rendered subject replaced with a redacted placeholder.",
    ),
    PersonalDataField(
        app_label="quickscale_notifications",
        model_name="NotificationMessage",
        field_name="rendered_text",
        treatment=PersonalDataTreatment.SCRUB,
        note="Rendered body replaced with a redacted placeholder.",
    ),
    PersonalDataField(
        app_label="quickscale_notifications",
        model_name="NotificationMessage",
        field_name="rendered_html",
        treatment=PersonalDataTreatment.SCRUB,
        note="Rendered body replaced with a redacted placeholder.",
    ),
    PersonalDataField(
        app_label="quickscale_notifications",
        model_name="NotificationMessage",
        field_name="context_json",
        treatment=PersonalDataTreatment.SCRUB,
        note="Rendered context replaced with a redacted placeholder.",
    ),
    PersonalDataField(
        app_label="quickscale_notifications",
        model_name="NotificationMessage",
        field_name="last_error",
        treatment=PersonalDataTreatment.SCRUB,
        note="Provider error text can echo the address; redacted.",
    ),
    PersonalDataField(
        app_label="quickscale_notifications",
        model_name="NotificationDelivery",
        field_name="failure_reason",
        treatment=PersonalDataTreatment.SCRUB,
        note="Provider error text can echo the address; redacted.",
    ),
    PersonalDataField(
        app_label="quickscale_notifications",
        model_name="NotificationDelivery",
        field_name="recipient_email",
        treatment=PersonalDataTreatment.SCRUB,
        note="Address scrubbed; status is kept for delivery statistics.",
    ),
    PersonalDataField(
        app_label="quickscale_notifications",
        model_name="NotificationDeliveryEvent",
        field_name="payload_json",
        treatment=PersonalDataTreatment.SCRUB,
        note="Stored provider payload carries the recipient; the address is redacted.",
    ),
    # -- billing: the user as actor on rows that stay --
    PersonalDataField(
        app_label="quickscale_billing",
        model_name="Subscription",
        field_name="user",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Subscription stays attributed to the deleted user.",
    ),
    PersonalDataField(
        app_label="quickscale_billing",
        model_name="CreditBalance",
        field_name="user",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Balance stays attributed to the deleted user.",
    ),
    PersonalDataField(
        app_label="quickscale_billing",
        model_name="CreditTransaction",
        field_name="user",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Ledger row stays attributed to the deleted user.",
    ),
    PersonalDataField(
        app_label="quickscale_billing",
        model_name="PurchaseCheckout",
        field_name="user",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Checkout record stays attributed to the deleted user.",
    ),
    PersonalDataField(
        app_label="quickscale_billing",
        model_name="WebhookEvent",
        field_name="payload",
        treatment=PersonalDataTreatment.SCRUB,
        note="Customer email and name redacted from the stored Stripe event payload.",
    ),
    # -- crm: the user as actor on rows that stay --
    PersonalDataField(
        app_label="quickscale_crm",
        model_name="ContactNote",
        field_name="created_by",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Note stays attributed to the deleted user.",
    ),
    PersonalDataField(
        app_label="quickscale_crm",
        model_name="DealNote",
        field_name="created_by",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Note stays attributed to the deleted user.",
    ),
    PersonalDataField(
        app_label="quickscale_crm",
        model_name="Deal",
        field_name="owner",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Deal stays attributed to the deleted user.",
    ),
    # -- forms: the user as actor on rows that stay --
    PersonalDataField(
        app_label="quickscale_forms",
        model_name="Form",
        field_name="created_by",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Form stays attributed to the deleted user.",
    ),
    # -- backups: the user as actor on rows that stay --
    PersonalDataField(
        app_label="quickscale_backups",
        model_name="BackupArtifact",
        field_name="initiated_by",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Backup record stays attributed to the deleted user.",
    ),
)

PERSONAL_DATA_EXCLUSIONS: tuple[PersonalDataExclusion, ...] = (
    # -- Django admin: operator audit log, kept as written --
    PersonalDataExclusion(
        app_label="admin",
        model_name="LogEntry",
        field_name="user",
        reason="Operator audit log; rows keep the link to the disabled account.",
    ),
    PersonalDataExclusion(
        app_label="admin",
        model_name="LogEntry",
        field_name="object_id",
        reason="Operator audit record content; retained unchanged.",
    ),
    PersonalDataExclusion(
        app_label="admin",
        model_name="LogEntry",
        field_name="change_message",
        reason="Operator audit record content; retained unchanged.",
    ),
    PersonalDataExclusion(
        app_label="admin",
        model_name="LogEntry",
        field_name="object_repr",
        reason="Operator audit record content (the acted-on object's display name); "
        "retained unchanged.",
    ),
    # -- auth: auto-created permission through tables --
    PersonalDataExclusion(
        app_label="quickscale_auth",
        model_name="User_groups",
        field_name="user",
        reason="Auto-created M2M through table for User.groups; holds the FK pair only.",
    ),
    PersonalDataExclusion(
        app_label="quickscale_auth",
        model_name="User_user_permissions",
        field_name="user",
        reason="Auto-created M2M through table for User.user_permissions; FK pair only.",
    ),
    # -- backups: operational diagnostics about the backup, not the operator --
    PersonalDataExclusion(
        app_label="quickscale_backups",
        model_name="BackupArtifact",
        field_name="validation_notes",
        reason="Operational backup notes, not personal data about the initiator.",
    ),
    PersonalDataExclusion(
        app_label="quickscale_backups",
        model_name="BackupArtifact",
        field_name="restore_error",
        reason="Operational restore diagnostics, not personal data about the initiator.",
    ),
    # -- billing: provider-derived transaction text --
    PersonalDataExclusion(
        app_label="quickscale_billing",
        model_name="CreditTransaction",
        field_name="description",
        reason="Derived from the plan name and provider IDs, not personal data.",
    ),
    # -- blog: organization-owned editorial content --
    PersonalDataExclusion(
        app_label="quickscale_blog",
        model_name="Post",
        field_name="content",
        reason="Organization editorial content authored by the user; retained as-is.",
    ),
    PersonalDataExclusion(
        app_label="quickscale_blog",
        model_name="Post",
        field_name="excerpt",
        reason="Organization editorial content authored by the user; retained as-is.",
    ),
    PersonalDataExclusion(
        app_label="quickscale_blog",
        model_name="Post",
        field_name="featured_image",
        reason="Organization-owned post image; retained as-is.",
    ),
    PersonalDataExclusion(
        app_label="quickscale_blog",
        model_name="BlogMediaAsset",
        field_name="file",
        reason="Organization-owned media file; retained as-is.",
    ),
    # -- crm: data about contacts, who are not users --
    PersonalDataExclusion(
        app_label="quickscale_crm",
        model_name="Contact",
        field_name="email",
        reason="Contact is not a user; the address belongs to the organization.",
    ),
    PersonalDataExclusion(
        app_label="quickscale_crm",
        model_name="ContactNote",
        field_name="text",
        reason="Organization content about a contact, not about the user.",
    ),
    PersonalDataExclusion(
        app_label="quickscale_crm",
        model_name="DealNote",
        field_name="text",
        reason="Organization content about a deal, not about the user.",
    ),
    # -- forms: organization-owned form configuration and submissions --
    PersonalDataExclusion(
        app_label="quickscale_forms",
        model_name="Form",
        field_name="description",
        reason="Form configuration owned by the organization; retained as-is.",
    ),
    PersonalDataExclusion(
        app_label="quickscale_forms",
        model_name="Form",
        field_name="success_message",
        reason="Form configuration owned by the organization; retained as-is.",
    ),
    PersonalDataExclusion(
        app_label="quickscale_forms",
        model_name="Form",
        field_name="notify_emails",
        reason="Organization recipient addresses, not the user's address.",
    ),
    PersonalDataExclusion(
        app_label="quickscale_forms",
        model_name="FormSubmission",
        field_name="ip_address",
        reason="Submission data about a non-user; belongs to the organization.",
    ),
    # -- listings: organization-owned listing image --
    PersonalDataExclusion(
        app_label="quickscale_listings",
        model_name="Listing",
        field_name="featured_image",
        reason="Organization-owned listing image; retained as-is.",
    ),
    # -- notifications: organization sender configuration --
    PersonalDataExclusion(
        app_label="quickscale_notifications",
        model_name="NotificationSettings",
        field_name="sender_email",
        reason="Organization sender configuration, not the user's address.",
    ),
    PersonalDataExclusion(
        app_label="quickscale_notifications",
        model_name="NotificationSettings",
        field_name="reply_to_email",
        reason="Organization reply-to configuration, not the user's address.",
    ),
)
