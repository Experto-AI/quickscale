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


def test_generated_views_use_set_current_org_id() -> None:
    """The generated views must set the ambient org context via set_current_org_id."""
    content = _render()
    assert "set_current_org_id" in content


def test_generated_views_preserve_and_restore_prior_context() -> None:
    """The generated views must capture prior context and restore in try/finally.

    CR-T1-9-003: the views must use get_current_org_id() to capture the
    prior org context before overriding it, and must restore it in a
    finally block so the restoration is exception-safe.
    """
    content = _render()

    # The prior context is captured before the override.
    assert "get_current_org_id()" in content
    assert "_prior_org_id" in content

    # The override + restore must be in a try/finally.
    assert "try:" in content
    assert "finally:" in content

    # The restore must reference the captured prior value, not a blind None.
    assert "_prior_org_id is not None" in content
    assert "set_current_org_id(_prior_org_id)" in content

    # The old bare reset_current_org_id() must not appear.
    assert "reset_current_org_id" not in content, (
        "The bare reset_current_org_id() has been replaced by the "
        "preserve-and-restore pattern in CR-T1-9-003."
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


def test_generated_views_import_set_db_current_org_id() -> None:
    """The generated views must import the shared DB activation helper."""
    content = _render()
    assert "set_db_current_org_id" in content


def test_generated_views_use_transaction_atomic() -> None:
    """The generated views must wrap org activation in transaction.atomic()."""
    content = _render()
    assert "transaction.atomic()" in content


def test_generated_views_call_set_db_current_org_id() -> None:
    """The generated views must call set_db_current_org_id for PostgreSQL SET LOCAL."""
    content = _render()
    assert "set_db_current_org_id(resolved_org_id)" in content


def test_generated_views_set_both_contextvar_and_db() -> None:
    """The generated views must set both ContextVar and DB org id in the same scope.

    Inside the transaction.atomic() block, both set_current_org_id and
    set_db_current_org_id must be called with the same resolved_org_id.
    """
    content = _render()
    assert "set_current_org_id(resolved_org_id)" in content
    assert "set_db_current_org_id(resolved_org_id)" in content
