"""Shared constants for the QuickScale organizations module."""

PENDING_ORG_INVITATION_TOKEN_SESSION_KEY = (
    "quickscale_modules_orgs.pending_org_invitation_token"
)
ACTIVE_ORG_SESSION_KEY = "quickscale_modules_orgs.active_org_id"
ORG_INVITATION_ACCEPT_URL_NAME = "org-invitation-accept"

# Reserved slug and display name for the singleton System organization.
# D2 — System org owns published-public content.
SYSTEM_ORG_SLUG = "__system__"
SYSTEM_ORG_NAME = "System"
