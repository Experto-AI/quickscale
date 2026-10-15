"""Theme-to-API contract test for the CRM workspace's stat cards.

The theme's ``useCrmStats`` hook expects one response shape from the CRM count
endpoint (``crm/api/stats/``).  This test reads the shipped theme source and
checks that expectation against the endpoint's rendered DRF response, so a
renamed or re-wrapped key on either side fails here — the contract check whose
absence let the stat cards read ``.count`` / ``.results`` from a bare list.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.urls import reverse
from rest_framework import status

import quickscale_core

THEME_CRM_PAGE = (
    Path(quickscale_core.__file__).resolve().parent
    / "generator"
    / "templates"
    / "themes"
    / "showcase_react"
    / "src"
    / "pages"
    / "CrmPage.tsx"
)

#: The stats response binds the theme's four stat cards; the CRM README records
#: the same four keys for ``crm/api/stats/``.
EXPECTED_STATS_KEYS = {"contacts", "companies", "deals", "tags"}

_STATS_INTERFACE = re.compile(r"interface CrmStats \{(?P<body>[^}]*)\}", re.DOTALL)
_INTERFACE_FIELD = re.compile(
    r"^\s*(?P<name>\w+): (?P<declared_type>\w+)\s*$", re.MULTILINE
)


def _theme_source() -> str:
    """Return the shipped showcase_react CrmPage.tsx source."""
    assert THEME_CRM_PAGE.is_file(), f"theme source not found: {THEME_CRM_PAGE}"
    return THEME_CRM_PAGE.read_text(encoding="utf-8")


def _declared_stats_fields(source: str) -> dict[str, str]:
    """Return the stats fields the theme's interface declares, with their types."""
    match = _STATS_INTERFACE.search(source)
    assert match is not None, "CrmPage.tsx must declare interface CrmStats"
    fields = dict(_INTERFACE_FIELD.findall(match.group("body")))
    assert fields, "interface CrmStats must declare its fields"
    return fields


@pytest.mark.django_db
class TestCrmStatsThemeContract:
    """The theme's stat hook and the rendered stats response agree on one shape."""

    def test_theme_reads_the_stats_endpoint(self) -> None:
        """The stat hook fetches the endpoint this module mounts."""
        source = _theme_source()

        assert "`${crmApiBase}stats/`" in source
        assert reverse("quickscale_crm:stats") == "/crm/api/stats/"

    def test_theme_shape_matches_the_rendered_response(self, viewer_client) -> None:
        """The declared interface, the hook reads, and the response agree."""
        source = _theme_source()
        fields = _declared_stats_fields(source)

        assert set(fields) == EXPECTED_STATS_KEYS
        assert set(fields.values()) == {"number"}
        for key in fields:
            assert f"stats.data?.{key} ?? 0" in source, (
                f"CrmPage.tsx's stats hook must read {key!r} from the response"
            )

        # The rendered response carries exactly that shape: the four
        # organization totals as JSON numbers.
        response = viewer_client.get(reverse("quickscale_crm:stats"))

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert set(body) == set(fields)
        assert all(type(value) is int for value in body.values())
