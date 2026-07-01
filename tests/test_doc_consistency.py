"""SA3.2 — CI doc-consistency gate.

Verifies that the enrolled-model counts asserted in **both** authoritative
technical docs (``docs/technical/organizations.md`` and
``docs/technical/decisions.md``) match the SSOT maintained in
``TENANT_TABLE_REGISTRY`` (``quickscale_modules_orgs.tenancy``), and that
the documented ``TenantManager`` API surface is consistent with the
actual code in ``quickscale_modules_orgs.managers``.

Each enrolled-model assertion is read at runtime from a
``<!-- enrolled-models assertion: ... -->`` HTML comment in the doc so
that a doc-only edit changes the test outcome — hardcoded constants are
no longer used.

Editing the registry without updating **both** doc assertions (or
vice-versa) fails CI.
"""

from __future__ import annotations

import pathlib
import re
from collections import Counter

from quickscale_modules_orgs.tenancy import (
    TENANT_TABLE_REGISTRY,
    TenantTableStatus,
)

# ---------------------------------------------------------------------------
# Doc assertions — parsed from the authoritative technical docs at runtime.
#
# Sources:
#   - docs/technical/organizations.md
#   - docs/technical/decisions.md
#
# The test reads the assertion from each doc's markdown source so that
# any edit to a doc changes the test outcome.  There is no intermediate
# copy of the expected numbers in this test file.
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent

_DOC_ASSERTION_RE = re.compile(
    r"<!--\s*enrolled-models assertion:\s*(.+?)\s*-->",
    re.DOTALL,
)


def _parse_assertions_from_doc(doc_relpath: str) -> dict[str, int]:
    """Parse the enrolled-models assertion from a doc at *doc_relpath*.

    Args:
        doc_relpath: Path relative to the repo root
            (e.g. ``docs/technical/organizations.md``).

    Returns:
        A dict mapping ``"total"`` and each app label to its enrolled-model
        count.

    Raises:
        AssertionError: If the assertion block is missing or unparseable.
    """
    path = _REPO_ROOT / doc_relpath
    content = path.read_text(encoding="utf-8")
    match = _DOC_ASSERTION_RE.search(content)
    if not match:
        raise AssertionError(
            f"enrolled-models assertion not found in {path}. "
            f"The test requires an HTML comment matching "
            r"'<!-- enrolled-models assertion: ... -->' in the doc."
        )
    pairs_str = match.group(1)
    result: dict[str, int] = {}
    for pair in pairs_str.split(","):
        pair = pair.strip()
        if not pair:
            continue
        key, val = pair.split("=", 1)
        result[key.strip()] = int(val.strip())
    return result


# --- Assertions from organizations.md ---

_ORGS_ASSERTIONS = _parse_assertions_from_doc(
    "docs/technical/organizations.md",
)

#: Total ENROLLED models asserted in organizations.md.
DOC_TOTAL_ENROLLED: int = _ORGS_ASSERTIONS["total"]

#: Per-app ENROLLED breakdown asserted in organizations.md.
DOC_ENROLLED_PER_APP: dict[str, int] = {
    k: v for k, v in _ORGS_ASSERTIONS.items() if k != "total"
}

# --- Assertions from decisions.md ---

_DECISIONS_ASSERTIONS = _parse_assertions_from_doc(
    "docs/technical/decisions.md",
)

#: Total ENROLLED models asserted in decisions.md.
DOC_TOTAL_ENROLLED_DECISIONS: int = _DECISIONS_ASSERTIONS["total"]

#: Per-app ENROLLED breakdown asserted in decisions.md.
DOC_ENROLLED_PER_APP_DECISIONS: dict[str, int] = {
    k: v for k, v in _DECISIONS_ASSERTIONS.items() if k != "total"
}


# ---------------------------------------------------------------------------
# Total enrolled-model count
# ---------------------------------------------------------------------------


def test_doc_enrolled_total_matches_registry() -> None:
    """Total ENROLLED model count must match the documented assertion.

    ``organizations.md`` asserts a specific total.  Adding or removing an
    ENROLLED entry in ``TENANT_TABLE_REGISTRY`` without updating the doc
    assertion fails this test.
    """
    enrolled = [
        e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED
    ]
    assert len(enrolled) == DOC_TOTAL_ENROLLED, (
        f"TENANT_TABLE_REGISTRY has {len(enrolled)} ENROLLED models, "
        f"but organizations.md asserts {DOC_TOTAL_ENROLLED}. "
        f"Update the registry in tenancy.py and update the "
        f"enrolled-models assertion in organizations.md."
    )


# ---------------------------------------------------------------------------
# Per-app enrolled-model breakdown
# ---------------------------------------------------------------------------


def test_doc_enrolled_per_app_matches_registry() -> None:
    """Per-app ENROLLED breakdown must match the documented assertion.

    ``organizations.md`` asserts a specific per-app breakdown.  Moving an
    ENROLLED model between apps or adding a model to an unexpected app
    without updating the doc assertion fails this test.
    """
    enrolled = [
        e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED
    ]
    actual_per_app: Counter[str] = Counter(e.app_label for e in enrolled)

    # Every doc-asserted app must have the expected count.
    for app_label, expected_count in DOC_ENROLLED_PER_APP.items():
        actual_count = actual_per_app.get(app_label, 0)
        assert actual_count == expected_count, (
            f"App {app_label} has {actual_count} ENROLLED model(s) "
            f"in the registry, but organizations.md asserts "
            f"{expected_count}. "
            f"Update the registry (tenancy.py) and the enrolled-models "
            f"assertion in organizations.md."
        )

    # No unexpected apps should have ENROLLED models.
    unexpected_apps = set(actual_per_app.keys()) - set(DOC_ENROLLED_PER_APP.keys())
    assert not unexpected_apps, (
        f"ENROLLED models found in unexpected app(s): "
        f"{sorted(unexpected_apps)}. "
        f"Add doc assertions for these apps or mark them as "
        f"EXCLUDED_REVIEWED in TENANT_TABLE_REGISTRY."
    )


# ---------------------------------------------------------------------------
# decisions.md enrolled-model assertions
# ---------------------------------------------------------------------------
# ``docs/technical/decisions.md`` is the repository-wide policy authority
# and also asserts enrolled-model counts in its ``§Isolation architecture
# rules`` section.  The same runtime assertion-parsing approach is used so
# that a doc-only edit changes the test outcome.
# ---------------------------------------------------------------------------


def test_decisions_doc_enrolled_total_matches_registry() -> None:
    """Total ENROLLED model count asserted in decisions.md must match.

    ``decisions.md`` asserts a specific total.  Adding or removing an
    ENROLLED entry in ``TENANT_TABLE_REGISTRY`` without updating the doc
    assertion fails this test.
    """
    enrolled = [
        e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED
    ]
    assert len(enrolled) == DOC_TOTAL_ENROLLED_DECISIONS, (
        f"TENANT_TABLE_REGISTRY has {len(enrolled)} ENROLLED models, "
        f"but decisions.md asserts {DOC_TOTAL_ENROLLED_DECISIONS}. "
        f"Update the registry in tenancy.py and update the "
        f"enrolled-models assertion in decisions.md."
    )


def test_decisions_doc_enrolled_per_app_matches_registry() -> None:
    """Per-app ENROLLED breakdown asserted in decisions.md must match.

    ``decisions.md`` asserts a specific per-app breakdown.  Moving an
    ENROLLED model between apps without updating the doc assertion fails
    this test.
    """
    enrolled = [
        e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED
    ]
    actual_per_app: Counter[str] = Counter(e.app_label for e in enrolled)

    for app_label, expected_count in DOC_ENROLLED_PER_APP_DECISIONS.items():
        actual_count = actual_per_app.get(app_label, 0)
        assert actual_count == expected_count, (
            f"App {app_label} has {actual_count} ENROLLED model(s) "
            f"in the registry, but decisions.md asserts "
            f"{expected_count}. "
            f"Update the registry (tenancy.py) and the enrolled-models "
            f"assertion in decisions.md."
        )

    unexpected_apps = set(actual_per_app.keys()) - set(
        DOC_ENROLLED_PER_APP_DECISIONS.keys()
    )
    assert not unexpected_apps, (
        f"ENROLLED models found in unexpected app(s): "
        f"{sorted(unexpected_apps)}. "
        f"Add doc assertions for these apps or mark them as "
        f"EXCLUDED_REVIEWED in TENANT_TABLE_REGISTRY."
    )


# ---------------------------------------------------------------------------
# Cross-doc agreement
# ---------------------------------------------------------------------------
# Both authoritative docs must assert the same enrolled-model counts.
# A mismatch between the two docs is a sign of incomplete doc maintenance.
# ---------------------------------------------------------------------------


def test_enrolled_assertions_agree_across_both_docs() -> None:
    """The enrolled-model assertion in both docs must match exactly.

    ``organizations.md`` and ``decisions.md`` both carry an ``enrolled-models
    assertion`` comment.  If they disagree, one doc was updated without the
    other — this test catches that drift.
    """
    assert _ORGS_ASSERTIONS == _DECISIONS_ASSERTIONS, (
        f"enrolled-models assertion mismatch between docs:\n"
        f"  organizations.md: {_ORGS_ASSERTIONS}\n"
        f"  decisions.md:     {_DECISIONS_ASSERTIONS}\n"
        f"Both docs must carry the same enrolled-models assertion."
    )


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
