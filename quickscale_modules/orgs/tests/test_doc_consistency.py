"""SA15.3 — CI doc-consistency gate.

Verifies that the marker-based derived registry overview
(:func:`get_derived_registry_overview`) agrees with the literal
``TENANT_TABLE_REGISTRY`` for the installed concrete model set,
and that the documented ``TenantManager`` API surface is consistent
with the actual code in ``quickscale_modules_orgs.managers``.

The hand-maintained ``<!-- enrolled-models assertion: ... -->`` HTML
comments have been removed from the technical docs in favour of the
derived overview.  The literal ``TENANT_TABLE_REGISTRY`` remains in
place temporarily as a cross-check target so the CI gate can confirm
the marker-driven view matches the design-time registry for every
installed model — no registry fallback is used.

After the SA15.3 marker backfill, all excluded models carry explicit
``tenant_excluded`` class attributes, so the derived view is purely
marker-driven with no silent fallback to ``REGISTRY_LOOKUP``.
"""

from __future__ import annotations

import pathlib
from collections import Counter

from quickscale_modules_orgs.tenancy import (
    TENANT_TABLE_REGISTRY,
    TenantTableStatus,
    get_derived_registry_overview,
    is_project_app,
)

#: Repo root used by stale-manager-name doc-content checks.
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent

# ---------------------------------------------------------------------------
# Cross-check: derived marker-based registry vs literal registry
# ---------------------------------------------------------------------------
# The literal ``TENANT_TABLE_REGISTRY`` is the temporary SSOT.  The derived
# view uses marker-based detection.  This test asserts they agree on the
# ENROLLED model set for project-owned apps, so the derived view can
# eventually replace the hand-maintained literal.
# ---------------------------------------------------------------------------

#: App labels that host test-only models (excluded from ENROLLED cross-check
#: comparisons).  No longer strictly necessary after the SA15.3 marker backfill
#: (test models carry explicit ``tenant_excluded`` markers), but kept to
#: preserve the existing ENROLLED-only assertions as-is.
_TEST_APP_LABELS: frozenset[str] = frozenset({"quickscale_modules_orgs"})


def test_derived_registry_enrolled_matches_literal_registry() -> None:
    """The ENROLLED model set from the derived view must match the literal
    ``TENANT_TABLE_REGISTRY`` for all project-owned apps.

    Test-only models (those in ``quickscale_modules_orgs`` app label) are
    excluded from the comparison because they exist only in the test
    environment and do not represent real tenant tables.
    """
    derived = get_derived_registry_overview()
    derived_enrolled = {
        (e.app_label, e.model_name)
        for e in derived
        if e.status == TenantTableStatus.ENROLLED
        and e.app_label not in _TEST_APP_LABELS
    }
    literal_enrolled = {
        (e.app_label, e.model_name)
        for e in TENANT_TABLE_REGISTRY
        if e.status == TenantTableStatus.ENROLLED
    }

    assert derived_enrolled == literal_enrolled, (
        f"Derived ENROLLED set ({derived_enrolled}) differs from "
        f"literal TENANT_TABLE_REGISTRY ENROLLED set ({literal_enrolled}). "
        f"The derived view (marker-based) and literal registry must agree "
        f"on the ENROLLED model set.  If you added, removed, or changed "
        f"a tenant-scoped model, update the markers and/or the literal "
        f"registry entries accordingly."
    )


def test_derived_registry_enrolled_per_app_matches_literal() -> None:
    """Per-app ENROLLED breakdown from the derived view must match the
    literal ``TENANT_TABLE_REGISTRY`` for project-owned apps."""
    derived = get_derived_registry_overview()
    derived_enrolled = [
        e
        for e in derived
        if e.status == TenantTableStatus.ENROLLED
        and e.app_label not in _TEST_APP_LABELS
    ]
    literal_enrolled = [
        e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED
    ]

    derived_per_app: Counter[str] = Counter(e.app_label for e in derived_enrolled)
    literal_per_app: Counter[str] = Counter(e.app_label for e in literal_enrolled)

    assert derived_per_app == literal_per_app, (
        f"Per-app ENROLLED breakdown mismatch:\n"
        f"  Derived:  {dict(derived_per_app)}\n"
        f"  Literal:  {dict(literal_per_app)}\n"
        f"The derived view must produce the same per-app ENROLLED "
        f"counts as the literal registry."
    )


def test_derived_registry_full_overview_matches_literal() -> None:
    """The full derived overview (every status) must match the literal
    ``TENANT_TABLE_REGISTRY`` when filtered to installed models.

    This proves the derived view is truly marker-driven: for every
    installed model that has a registry entry, the derived view must
    produce the same (status, app_label, model_name) triple.  Models
    that are only in the literal registry but not installed in the
    current test environment are excluded from the comparison.
    """
    from django.apps import apps

    derived = get_derived_registry_overview()
    derived_set = {(e.status, e.app_label, e.model_name) for e in derived}

    # Build a set of models actually installed in this environment.
    installed_model_keys: set[tuple[str, str]] = {
        (m._meta.app_label, m.__name__)
        for m in apps.get_models(include_auto_created=True)
    }

    literal_installed = {
        (e.status, e.app_label, e.model_name)
        for e in TENANT_TABLE_REGISTRY
        if (e.app_label, e.model_name) in installed_model_keys
    }

    missing_from_derived = literal_installed - derived_set
    extra_in_derived = derived_set - literal_installed

    assert not missing_from_derived and not extra_in_derived, (
        f"Full overview parity mismatch:\n"
        f"  In literal but missing from derived: {missing_from_derived}\n"
        f"  In derived but absent from literal: {extra_in_derived}\n"
        f"The derived view must be purely marker-driven and agree with "
        f"the literal registry for every installed model.  If you added "
        f"a model, ensure it carries the correct marker (tenant_excluded, "
        f"TenantManager/TenantModel, or implicit M2M through detection)."
    )


def test_derived_registry_no_fallback_reason() -> None:
    """No entry in the derived overview should use a registry-fallback reason.

    After the SA15.3 marker backfill, every excluded model carries an
    explicit ``tenant_excluded`` marker.  The derived overview must not
    contain any entry whose reason references registry-based fallback
    classification.
    """
    derived = get_derived_registry_overview()
    for entry in derived:
        assert "Classified by registry" not in entry.reason, (
            f"Model {entry.app_label}.{entry.model_name} has reason "
            f"{entry.reason!r} which references registry fallback. "
            f"After the SA15.3 marker backfill, every excluded model "
            f"should carry an explicit tenant_excluded marker."
        )


def test_derived_registry_covers_installed_exclusions() -> None:
    """Every installed concrete project model that is excluded from tenancy
    must appear as EXCLUDED_REVIEWED in the derived overview.

    This proves that all excluded models (orgs control-plane, billing
    system-wide metadata, blog user-profile, etc.) are detectable via
    markers rather than relying on the literal registry.
    """
    from quickscale_modules_orgs.tenancy import (
        get_concrete_project_models,
        has_tenant_excluded_marker,
    )

    derived = get_derived_registry_overview()
    derived_excluded = {
        (e.app_label, e.model_name)
        for e in derived
        if e.status == TenantTableStatus.EXCLUDED_REVIEWED
    }

    for model in get_concrete_project_models():
        if has_tenant_excluded_marker(model):
            key = (model._meta.app_label, model.__name__)
            assert key in derived_excluded, (
                f"Model {key[0]}.{key[1]} has tenant_excluded marker but "
                f"does not appear as EXCLUDED_REVIEWED in the derived "
                f"overview."
            )


def test_derived_registry_works_without_registry_lookup() -> None:
    """The derived registry overview must work when ``REGISTRY_LOOKUP`` is cleared.

    Monkeypatches ``REGISTRY_LOOKUP`` on the ``tenancy`` module to an empty
    dict and proves :func:`get_derived_registry_overview` still produces
    the same overview as the literal ``TENANT_TABLE_REGISTRY`` for all
    installed models.  This is a regression test: if any code path in
    the derived overview still consults ``REGISTRY_LOOKUP`` indirectly
    (via :func:`is_classified_in_registry` or
    :func:`_get_m2m_through_classification`), clearing the lookup would
    cause ENROLLED models or auto-created M2M through tables to vanish
    from the derived view.

    The derived view uses the new ``_is_classified_by_marker_only`` path
    which checks ``tenant_excluded`` markers, ``TenantManager`` /
    ``TenantModel`` detection, and marker-only M2M through inference —
    never ``REGISTRY_LOOKUP``.
    """
    # Use try/finally to restore REGISTRY_LOOKUP even on assertion failure.
    import quickscale_modules_orgs.tenancy as tenancy_mod

    original_lookup = tenancy_mod.REGISTRY_LOOKUP
    try:
        tenancy_mod.REGISTRY_LOOKUP = {}

        derived = get_derived_registry_overview()
        derived_set = {(e.status, e.app_label, e.model_name) for e in derived}

        from django.apps import apps

        installed_model_keys: set[tuple[str, str]] = {
            (m._meta.app_label, m.__name__)
            for m in apps.get_models(include_auto_created=True)
        }

        literal_installed = {
            (e.status, e.app_label, e.model_name)
            for e in TENANT_TABLE_REGISTRY
            if (e.app_label, e.model_name) in installed_model_keys
        }

        missing_from_derived = literal_installed - derived_set
        extra_in_derived = derived_set - literal_installed

        assert not missing_from_derived and not extra_in_derived, (
            f"With REGISTRY_LOOKUP cleared, parity mismatch:\n"
            f"  In literal but missing from derived: {missing_from_derived}\n"
            f"  In derived but absent from literal: {extra_in_derived}\n"
            f"The derived view must be purely marker-driven and work "
            f"without REGISTRY_LOOKUP."
        )
    finally:
        tenancy_mod.REGISTRY_LOOKUP = original_lookup


# ---------------------------------------------------------------------------
# Documented TenantManager API surface vs. actual code
# ---------------------------------------------------------------------------
# Both authoritative docs describe the same manager contract:
#   ``objects = TenantManager()``
#   ``all_objects = TenantManager(super_scope=True)``
#
# organisations.md also states that the authoritative tenant-facing API is
# **ambient scoping**, not ``.for_org(...)`` chaining.
# ---------------------------------------------------------------------------


def test_tenantmanager_class_exists() -> None:
    """``TenantManager`` must exist in the managers module.

    Both docs document ``TenantManager`` as the default tenant-scoped
    manager class.  A rename or deletion without updating the docs would
    make this test fail.
    """
    from quickscale_modules_orgs.managers import TenantManager

    assert TenantManager is not None
    assert callable(TenantManager)


def test_tenantmanager_accepts_super_scope_param() -> None:
    """``TenantManager.__init__`` must accept ``super_scope: bool = False``.

    This matches the ``TenantManager(super_scope=True)`` form documented
    in both authoritative docs.
    """
    from quickscale_modules_orgs.managers import TenantManager

    mgr_default = TenantManager()
    mgr_super = TenantManager(super_scope=True)
    assert mgr_default._super_scope is False
    assert mgr_super._super_scope is True


def test_tenantmanager_has_get_queryset() -> None:
    """``TenantManager`` must have a ``get_queryset`` method."""
    from quickscale_modules_orgs.managers import TenantManager

    assert hasattr(TenantManager, "get_queryset")
    assert callable(TenantManager.get_queryset)


def test_no_for_org_on_tenantmanager() -> None:
    """``TenantManager`` must NOT expose a ``for_org`` method.

    Both docs state that the authoritative tenant-facing API is ambient
    scoping via the ContextVar, not ``.for_org(...)`` chaining — the old
    pattern was explicitly removed in SA3.1.
    """
    from quickscale_modules_orgs.managers import TenantManager

    assert not hasattr(TenantManager, "for_org"), (
        "TenantManager should not expose a .for_org() method. "
        "The authoritative tenant-facing API is ambient scoping, "
        "not .for_org() chaining — as documented in both "
        "organizations.md and decisions.md."
    )


# ---------------------------------------------------------------------------
# Stale-manager-name guard
# ---------------------------------------------------------------------------
# SA3.1 removed the old ``TenantScopedManager`` / ``OperatorManager`` names
# from the codebase and the docs.  This guard prevents them from reappearing
# in the managers module or in the authoritative decision docs.
# ---------------------------------------------------------------------------

_STALE_MANAGER_NAMES = frozenset({"TenantScopedManager", "OperatorManager"})


def test_no_stale_manager_names_in_managers_module() -> None:
    """The managers module must not define stale manager classes.

    ``TenantScopedManager`` and ``OperatorManager`` were removed in SA3.1.
    Re-adding one without updating the docs would silently widen the API
    surface beyond what the docs describe.
    """
    import quickscale_modules_orgs.managers as mgrs

    for name in _STALE_MANAGER_NAMES:
        assert not hasattr(mgrs, name), (
            f"Stale manager name '{name}' found in managers module. "
            f"SA3.1 removed this class.  Remove it again and update "
            f"the docs."
        )


def test_no_stale_manager_names_in_decisions_doc() -> None:
    """decisions.md must not reference stale manager names.

    SA3.1 replaced all mentions of ``TenantScopedManager`` and
    ``OperatorManager`` with the current ``TenantManager`` API.
    """
    path = _REPO_ROOT / "docs/technical/decisions.md"
    content = path.read_text(encoding="utf-8")

    for name in _STALE_MANAGER_NAMES:
        assert name not in content, (
            f"Stale manager name '{name}' found in decisions.md. "
            f"SA3.1 removed this reference.  Update decisions.md to "
            f"use the current TenantManager API."
        )


def test_no_stale_manager_names_in_organizations_doc() -> None:
    """organizations.md must not reference stale manager names.

    SA3.1 replaced all mentions of ``TenantScopedManager`` and
    ``OperatorManager`` with the current ``TenantManager`` API.
    """
    path = _REPO_ROOT / "docs/technical/organizations.md"
    content = path.read_text(encoding="utf-8")

    for name in _STALE_MANAGER_NAMES:
        assert name not in content, (
            f"Stale manager name '{name}' found in organizations.md. "
            f"SA3.1 removed this reference.  Update organizations.md to "
            f"use the current TenantManager API."
        )


# ---------------------------------------------------------------------------
# SA15.3 — Marker-only M2M through classification with non-project endpoints
# ---------------------------------------------------------------------------
# The marker-only M2M through classification must handle the case where
# one endpoint is not a project-owned model.  For example,
# ``quickscale_modules_auth.User`` (project-owned, marker-excluded) has
# M2M fields through ``auth.Group`` / ``auth.Permission`` (Django contrib
# — not project-owned).  The auto-created through tables ``User_groups``
# and ``User_user_permissions`` must still be classifiable by the
# marker-only path without ``REGISTRY_LOOKUP``.
#
# This test simulates the scenario by temporarily making a project-owned
# through model's target appear non-project-owned via mock, proving that
# non-project endpoints are accepted without marker classification.
# ---------------------------------------------------------------------------


def test_m2m_through_marker_only_with_non_project_target() -> None:
    """Prove the marker-only M2M through classification tolerates non-project
    endpoints (regression test for auth User -> contrib Group scenario).

    Finds a project-owned through model where both endpoints are currently
    project-owned and classified, then simulates the auth scenario by
    making the target appear non-project.  With the SA15.3 fix, the through
    model must remain classifiable via markers alone — non-project endpoints
    are treated as externally classified.
    """
    from unittest.mock import patch

    from django.apps import apps

    from quickscale_modules_orgs.tenancy import (
        _get_m2m_through_classification_marker_only,
        _is_classified_by_marker_only,
        _is_implicit_m2m_through,
    )

    # Find a project-owned through model with both endpoints project-owned,
    # so we can simulate the non-project target scenario.
    through_model = None
    source_model = None
    target_model = None

    for model in apps.get_models(include_auto_created=True):
        if not _is_implicit_m2m_through(model):
            continue
        if not is_project_app(model._meta.app_label):
            continue

        for candidate in apps.get_models():
            for field in candidate._meta.many_to_many:
                if field.remote_field.through is model:
                    src = candidate
                    tgt = field.remote_field.model
                    if (
                        is_project_app(src._meta.app_label)
                        and is_project_app(tgt._meta.app_label)
                        and _is_classified_by_marker_only(src)
                        and _is_classified_by_marker_only(tgt)
                    ):
                        through_model = model
                        source_model = src
                        target_model = tgt
                        break
            if through_model:
                break
        if through_model:
            break

    assert through_model is not None, (
        "No suitable project-owned through model found. "
        "At least one ManyToMany through table (e.g. Contact_tags) "
        "should exist in the test environment."
    )
    assert source_model is not None, (
        "Source model should have been set alongside through_model."
    )
    assert target_model is not None, (
        "Target model should have been set alongside through_model."
    )

    # Baseline: classifiable when both endpoints are project-owned.
    assert _get_m2m_through_classification_marker_only(through_model), (
        f"Baseline: through {through_model.__name__} should be "
        f"marker-classifiable when both {source_model.__name__} and "
        f"{target_model.__name__} are project-owned and classified."
    )

    # Simulate the auth scenario: make the target appear non-project-owned.
    # With the fix, non-project endpoints are accepted without requiring
    # marker classification.  The through model should remain classifiable.
    target_label = target_model._meta.app_label

    def _mock_is_project_app(label: str) -> bool:
        if label == target_label:
            return False
        return is_project_app(label)

    with patch(
        "quickscale_modules_orgs.tenancy.is_project_app",
        side_effect=_mock_is_project_app,
    ):
        assert _get_m2m_through_classification_marker_only(through_model), (
            f"SA15.3 regression: through {through_model.__name__} should "
            f"remain marker-classifiable when target {target_model.__name__} "
            f"appears as non-project (simulating auth.User -> auth.Group)."
        )
