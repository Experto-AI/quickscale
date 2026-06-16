"""
Reusable cross-tenant isolation assertion helpers.

Phase 14.1 of the roadmap extracts the 'Org A request cannot read Org B
rows' assertion from the CRM inline probe into a shared helper so that
every tenant module can express the same contract consistently.

These helpers validate the response-level assertion only (status code +
visible data names).  Fixture creation, authentication, and URL routing
remain module-specific because each module has different models and
URL patterns.
"""

from __future__ import annotations

from typing import Any


def assert_org_scoped_response(
    response: Any,
    *,
    expected_names: set[str],
    item_key: str = "name",
) -> None:
    """
    Assert that an org-scoped API response contains only the expected org's data.

    This is the reusable 'Org A request cannot read Org B rows' assertion
    extracted from the CRM inline probe (Phase 14.1).  It validates:

    1. The response status is 200 OK (request-path and auth are functional).
    2. The response JSON list contains only items whose ``item_key`` value
       is in ``expected_names`` — no cross-tenant rows are visible.

    Args:
        response: Django test-client response from an org-scoped endpoint.
        expected_names: The set of names that should be visible (the
            requesting org's own data).
        item_key: The JSON key to extract from each response item.
            Defaults to ``"name"``.

    Raises:
        AssertionError: If the status is not 200 or if the visible names
            do not match ``expected_names`` exactly.

    """
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}. Response: {response.content.decode()[:200]}"
    )

    data = response.json()
    visible_names = {item[item_key] for item in data}

    assert visible_names == expected_names, (
        f"Expected only {expected_names}, but got {visible_names}. "
        "This confirms the cross-tenant isolation gap (Finding 11)."
    )
