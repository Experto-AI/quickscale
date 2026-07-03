"""Seam tests for SA11.6 — warm-on-read bootstrap removed.

The old ``test_crm_api_read_calls_bootstrap_helper`` and
``test_crm_dashboard_read_calls_bootstrap_helper`` tested the warm-on-read
``ensure_org_default_stages`` side effect in ``_resolve_active_org``.
SA11.6 removes that side effect entirely — stages are seeded once at
org-creation time via the ``organization_created`` signal, not on every
org resolution.  The warm-on-read seam tests are therefore deleted.
This module is kept as a placeholder should future bootstrap-wiring tests
be needed.
"""

from __future__ import annotations
