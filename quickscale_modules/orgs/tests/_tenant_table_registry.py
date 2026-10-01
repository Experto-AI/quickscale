"""Test-owned shipped-module tenant-table parity registry (Module Conventions rule 34).

This literal used to ship in ``quickscale_modules_orgs.tenancy``. It is a CI
parity oracle only — runtime classification is marker-derived and never
consults it — and rule 34 / D37 keep it in test code so shipped source names no
other module's tables.

``TenantTableEntry`` and ``TenantTableStatus`` stay in the shipped module
because the marker-derived
:func:`~quickscale_modules_orgs.tenancy.get_derived_registry_overview` builds
them at runtime. The conformance tests in this directory keep this literal in
step with the installed shipped models.
"""

from __future__ import annotations

from quickscale_modules_orgs.tenancy import TenantTableEntry, TenantTableStatus

# ---------------------------------------------------------------------------
# Central tenant-table registry — test-owned parity oracle
# ---------------------------------------------------------------------------
# Every shipped concrete model appears in exactly one of the three categories
# below. Runtime discovery is marker-derived and does not consult this literal.
# ---------------------------------------------------------------------------

TENANT_TABLE_REGISTRY: list[TenantTableEntry] = [
    # ====== ENROLLED =====================================================
    # Tenant-owned ``TenantModel`` subclasses with a direct
    # ``organization_id`` column, the inherited ``TenantManager`` pair,
    # and a live FORCE-RLS policy.
    # ======================================================================
    # -- CRM --
    TenantTableEntry(
        app_label="quickscale_crm",
        model_name="Tag",
        status=TenantTableStatus.ENROLLED,
        policy_name="crm_tag_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_crm",
        model_name="Company",
        status=TenantTableStatus.ENROLLED,
        policy_name="crm_company_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_crm",
        model_name="Contact",
        status=TenantTableStatus.ENROLLED,
        policy_name="crm_contact_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_crm",
        model_name="Stage",
        status=TenantTableStatus.ENROLLED,
        policy_name="crm_stage_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_crm",
        model_name="Deal",
        status=TenantTableStatus.ENROLLED,
        policy_name="crm_deal_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_crm",
        model_name="ContactNote",
        status=TenantTableStatus.ENROLLED,
        policy_name="crm_contactnote_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_crm",
        model_name="DealNote",
        status=TenantTableStatus.ENROLLED,
        policy_name="crm_dealnote_org_isolation",
    ),
    # -- Forms --
    TenantTableEntry(
        app_label="quickscale_forms",
        model_name="Form",
        status=TenantTableStatus.ENROLLED,
        policy_name="forms_form_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_forms",
        model_name="FormField",
        status=TenantTableStatus.ENROLLED,
        policy_name="forms_formfield_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_forms",
        model_name="FormSubmission",
        status=TenantTableStatus.ENROLLED,
        policy_name="forms_formsubmission_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_forms",
        model_name="FormFieldValue",
        status=TenantTableStatus.ENROLLED,
        policy_name="forms_formfieldvalue_org_isolation",
    ),
    # -- Billing --
    TenantTableEntry(
        app_label="quickscale_billing",
        model_name="CreditBalance",
        status=TenantTableStatus.ENROLLED,
        policy_name="billing_credit_balance_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_billing",
        model_name="CreditTransaction",
        status=TenantTableStatus.ENROLLED,
        policy_name="billing_credit_transaction_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_billing",
        model_name="PurchaseCheckout",
        status=TenantTableStatus.ENROLLED,
        policy_name="billing_purchase_checkout_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_billing",
        model_name="Subscription",
        status=TenantTableStatus.ENROLLED,
        policy_name="billing_subscription_org_isolation",
    ),
    # -- Blog --
    TenantTableEntry(
        app_label="quickscale_blog",
        model_name="Category",
        status=TenantTableStatus.ENROLLED,
        policy_name="blog_category_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_blog",
        model_name="Tag",
        status=TenantTableStatus.ENROLLED,
        policy_name="blog_tag_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_blog",
        model_name="BlogMediaAsset",
        status=TenantTableStatus.ENROLLED,
        policy_name="blog_media_asset_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_blog",
        model_name="Post",
        status=TenantTableStatus.ENROLLED,
        policy_name="blog_post_org_isolation",
    ),
    # -- Listings --
    TenantTableEntry(
        app_label="quickscale_listings",
        model_name="Listing",
        status=TenantTableStatus.ENROLLED,
        policy_name="listings_listing_org_isolation",
    ),
    # -- Social --
    TenantTableEntry(
        app_label="quickscale_social",
        model_name="SocialLink",
        status=TenantTableStatus.ENROLLED,
        policy_name="social_link_org_isolation",
    ),
    TenantTableEntry(
        app_label="quickscale_social",
        model_name="SocialEmbed",
        status=TenantTableStatus.ENROLLED,
        policy_name="social_embed_org_isolation",
    ),
    # ====== REVIEWED EXCLUSIONS ==========================================
    # Models intentionally excluded from the tenant-isolation contract.
    # ======================================================================
    # -- Orgs (control-plane — the tenancy infrastructure itself) --
    TenantTableEntry(
        app_label="quickscale_orgs",
        model_name="Organization",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Control-plane model: tenant definition table, not tenant-scoped.",
    ),
    TenantTableEntry(
        app_label="quickscale_orgs",
        model_name="OrganizationMembership",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Control-plane model: membership tracks the user-org "
        "relationship; it is not tenant-scoped data.",
    ),
    TenantTableEntry(
        app_label="quickscale_orgs",
        model_name="OrganizationInvitation",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Control-plane model: pending invitations are "
        "tenancy-infrastructure records.",
    ),
    TenantTableEntry(
        app_label="quickscale_orgs",
        model_name="OrganizationTombstone",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Control-plane model: purge-tracking records are "
        "tenancy-infrastructure, not tenant-owned data.",
    ),
    TenantTableEntry(
        app_label="quickscale_orgs",
        model_name="TenantModel",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Abstract base model — not concrete.",
    ),
    # -- Billing (system-wide, not tenant-scoped) --
    TenantTableEntry(
        app_label="quickscale_billing",
        model_name="Plan",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="System-wide plan definition, not tenant-owned.",
    ),
    TenantTableEntry(
        app_label="quickscale_billing",
        model_name="WebhookEvent",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="System-wide webhook idempotency record, not tenant-owned.",
    ),
    # -- Blog (user-profile, not tenant-scoped) --
    TenantTableEntry(
        app_label="quickscale_blog",
        model_name="AuthorProfile",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="User-profile extension linked to auth.User, not tenant-scoped.",
    ),
    # -- Auto-created ManyToMany through tables --
    TenantTableEntry(
        app_label="quickscale_crm",
        model_name="Contact_tags",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Auto-created ManyToMany through table — no tenant-scoped data.",
    ),
    TenantTableEntry(
        app_label="quickscale_crm",
        model_name="Deal_tags",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Auto-created ManyToMany through table — no tenant-scoped data.",
    ),
    TenantTableEntry(
        app_label="quickscale_blog",
        model_name="Post_tags",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Auto-created ManyToMany through table — no tenant-scoped data.",
    ),
    # -- Auth (system-wide user model, not tenant-scoped) --
    TenantTableEntry(
        app_label="quickscale_auth",
        model_name="User",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="System-wide user model: identities are cross-tenant, not tenant-scoped.",
    ),
    TenantTableEntry(
        app_label="quickscale_auth",
        model_name="User_groups",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Auto-created ManyToMany through table for auth.User.groups — "
        "no tenant-scoped data.",
    ),
    TenantTableEntry(
        app_label="quickscale_auth",
        model_name="User_user_permissions",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Auto-created ManyToMany through table for auth.User.user_permissions "
        "-- no tenant-scoped data.",
    ),
    # -- Backups (operational/DR records, not tenant-scoped) --
    TenantTableEntry(
        app_label="quickscale_backups",
        model_name="BackupPolicy",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Operational backup policy — singleton config, not tenant-scoped.",
    ),
    TenantTableEntry(
        app_label="quickscale_backups",
        model_name="BackupArtifact",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Operational backup artifact metadata — not tenant-scoped.",
    ),
    TenantTableEntry(
        app_label="quickscale_backups",
        model_name="BackupSnapshot",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Internal DR snapshot metadata — not tenant-scoped.",
    ),
    # -- Notifications (system-wide operational records, not tenant-scoped) --
    TenantTableEntry(
        app_label="quickscale_notifications",
        model_name="NotificationSettings",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Operational notification configuration — not tenant-scoped.",
    ),
    TenantTableEntry(
        app_label="quickscale_notifications",
        model_name="NotificationMessage",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="System-wide notification send-request — not tenant-scoped.",
    ),
    TenantTableEntry(
        app_label="quickscale_notifications",
        model_name="NotificationDelivery",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Recipient delivery tracking — not tenant-scoped.",
    ),
    TenantTableEntry(
        app_label="quickscale_notifications",
        model_name="NotificationDeliveryEvent",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Provider delivery event history — not tenant-scoped.",
    ),
    # -- Abstract base models --
    # -- Test-only models --
    TenantTableEntry(
        app_label="quickscale_orgs",
        model_name="ConcreteTenantResource",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Test-only model defined in test_models.py for "
        "TenantManager behaviour tests; not a real tenant table.",
    ),
    TenantTableEntry(
        app_label="quickscale_orgs",
        model_name="ForwardFKChild",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Test-only model defined in test_models.py for "
        "forward-FK traversal regression tests; "
        "not a real tenant table.",
    ),
    TenantTableEntry(
        app_label="quickscale_orgs",
        model_name="TenantExcludedModel",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Test-only model defined in test_management_commands.py for "
        "tenant_excluded marker classification tests; "
        "not a real tenant table.",
    ),
    # ====== PENDING REMEDIATION ==========================================
    # Known child/detail tables that lack direct ``organization_id``
    # and FORCE-RLS.  Tracked with equality-footprint metadata naming
    # the parent seam.  These will be promoted to ENROLLED in a later
    # phase after the schema migration lands.
    # ======================================================================
]

REGISTRY_LOOKUP: dict[tuple[str, str], TenantTableEntry] = {
    (entry.app_label, entry.model_name): entry for entry in TENANT_TABLE_REGISTRY
}
