"""Tests for the managed social views template (render_social_managed_views_module).

T1.9 review-driven follow-up (CR-T1-9-002, CR-T1-9-003): the generated views
code must:
- Drop the removed ``organization_id`` kwarg
- Establish the ambient tenant context before calling social services
- Resolve System org for anonymous/public requests per D2
- Preserve prior ambient context and restore it in a try/finally block,
  exception-safe (CR-T1-9-003)
"""

from __future__ import annotations

from quickscale_core.manifest.social_manifest import (
    render_social_managed_views_module,
)


def _render() -> str:
    """Render the managed views template with standard defaults."""
    return render_social_managed_views_module(
        provider_allowlist=["youtube", "tiktok"],
        embed_provider_allowlist=["youtube", "tiktok"],
        layout_variant="list",
        cache_ttl_seconds=300,
        links_per_page=24,
        embeds_per_page=12,
    )


def test_generated_social_link_tree_view_drops_organization_id_kwarg() -> None:
    """The managed social views template must not pass organization_id to services."""
    content = _render()
    assert "organization_id" not in content, (
        "The organization_id kwarg was removed from services in T1.9. "
        "The generated view must not pass it."
    )


def test_generated_social_embeds_view_drops_organization_id_kwarg() -> None:
    """The managed embeds view must also drop the removed kwarg."""
    content = _render()
    assert "organization_id" not in content, (
        "The organization_id kwarg was removed from services in T1.9. "
        "The generated view must not pass it."
    )


def test_generated_views_use_tenant_context() -> None:
    """The generated views must activate tenant context via tenant_context()."""
    content = _render()
    assert "tenant_context" in content


def test_generated_views_preserve_and_restore_prior_context() -> None:
    """The generated views delegate context save/restore to tenant_context().

    Phase 3: tenant_context() handles prior-context capture, ContextVar set,
    DB SET LOCAL, and prior-context restore internally — no manual
    try/finally is needed in the generated view code.
    """
    content = _render()

    # tenant_context is the unified activation helper.
    assert "tenant_context(resolved_org_id)" in content

    # Manual prior-context management should be absent since tenant_context
    # owns the save/restore contract.
    assert "_prior_org_id" not in content, (
        "Phase 3: tenant_context() handles prior-context save/restore "
        "internally. Manual _prior_org_id management is no longer needed."
    )
    assert "get_current_org_id()" not in content, (
        "Phase 3: get_current_org_id() is not needed in the generated "
        "views — tenant_context() manages the ContextVar lifecycle."
    )

    # No bare reset_current_org_id remains.
    assert "reset_current_org_id" not in content, (
        "reset_current_org_id() is not needed — tenant_context() handles "
        "context lifecycle."
    )


def test_generated_views_resolve_system_org_for_anonymous() -> None:
    """The generated views must resolve System org for anonymous/public requests."""
    content = _render()
    assert "get_system_org()" in content, (
        "Anonymous/public requests must resolve the System org per D2."
    )
    assert "Organization.objects.get_system_org()" in content


def test_generated_views_conditionally_resolve_org_context() -> None:
    """The generated views must conditionally resolve org context (auth vs anonymous).

    T1.15: the resolved_org_id ternary replaces the old inline if/else
    so the org id is established before the transaction.atomic() block,
    making it reusable for both ContextVar and SET LOCAL.
    """
    content = _render()
    assert "resolved_org_id" in content
    assert "org.id if org is not None" in content
    assert "get_system_org().id" in content
    assert "build_social_link_tree_payload()" in content
    assert "build_social_embeds_payload()" in content


# ---------------------------------------------------------------------------
# T1.15 Phase 1 — shared org activation seam for non-middleware callers
# ---------------------------------------------------------------------------


def test_generated_views_import_transaction() -> None:
    """The generated views must import django.db.transaction for SET LOCAL scope."""
    content = _render()
    assert "from django.db import transaction" in content


def test_generated_views_import_tenant_context() -> None:
    """The generated views must import tenant_context for the unified activation."""
    content = _render()
    assert "from quickscale_modules_orgs.current_org import tenant_context" in content


def test_generated_views_use_transaction_atomic() -> None:
    """The generated views must wrap org activation in transaction.atomic()."""
    content = _render()
    assert "transaction.atomic()" in content


def test_generated_views_call_tenant_context() -> None:
    """The generated views must call tenant_context(resolved_org_id) for unified activation.

    Phase 3: tenant_context() sets both the ContextVar and DB app.current_org_id
    (via SET LOCAL) inside the caller's transaction.atomic() block.
    """
    content = _render()
    assert "tenant_context(resolved_org_id)" in content


def test_generated_views_set_both_contextvar_and_db() -> None:
    """The generated views use tenant_context() which sets both ContextVar and DB.

    Phase 3: tenant_context(resolved_org_id) is the unified seam that
    handles both Python-level ContextVar and DB-level SET LOCAL
    app.current_org_id — no manual set_current_org_id/set_db_current_org_id
    calls are needed in generated view code.
    """
    content = _render()
    assert "tenant_context(resolved_org_id)" in content
    # Manual calls should not appear — tenant_context() handles both.
    assert "set_current_org_id(resolved_org_id)" not in content, (
        "Phase 3: tenant_context() handles ContextVar internally; "
        "manual set_current_org_id is no longer needed."
    )
    assert "set_db_current_org_id(resolved_org_id)" not in content, (
        "Phase 3: tenant_context() handles DB SET LOCAL internally; "
        "manual set_db_current_org_id is no longer needed."
    )
