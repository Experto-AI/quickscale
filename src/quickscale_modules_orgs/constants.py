"""Shared constants for the QuickScale organizations module."""

PENDING_ORG_INVITATION_TOKEN_SESSION_KEY = (
    "quickscale_modules_orgs.pending_org_invitation_token"  # noqa: S105 - Django session key name, not a credential
)
ACTIVE_ORG_SESSION_KEY = "quickscale_modules_orgs.active_org_id"
DEBUG_AS_ORG_SESSION_KEY = "quickscale_modules_orgs.debug_as_org_id"
ORG_INVITATION_ACCEPT_URL_NAME = "quickscale_orgs:invitation_accept"

# Reserved slug and display name for the singleton System organization.
# D2 — System org owns published-public content.
SYSTEM_ORG_SLUG = "__system__"
SYSTEM_ORG_NAME = "System"

# Slugs the module's own URL space owns: the JSON API lives at ``orgs/api/``
# (Module Conventions rule 7), so no organization may take the ``api`` slug.
RESERVED_ORG_SLUGS: frozenset[str] = frozenset({"api"})
