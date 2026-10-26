"""Tests for the manifest's ``frontend_resources`` section (SA320).

The section declares the API resource subpaths and payload types a module's
theme page may consume.  The generated ``frontend/src/quickscaleSeam.hooks.ts``
renders it, so the loader validates the declaration as a closed contract: a
malformed path, type name, or field type would reach the generated TypeScript
and fail there instead of at load time.
"""

from __future__ import annotations

import pytest

from quickscale_core.manifest.loader import load_manifest
from quickscale_core.manifest.loader_errors import ManifestError

_BASE = "name: mymod\nversion: '1.0.0'\n"


def _load(frontend_resources: str):
    return load_manifest(_BASE + frontend_resources, "mymod")


def test_absent_section_is_none() -> None:
    assert _load("").frontend_resources is None


def test_section_parses_paths_and_payload_types() -> None:
    manifest = _load(
        """
frontend_resources:
  paths:
    stats: stats/
    deals: deals/bulk-update-stage/
  payload_types:
    CrmStats:
      contacts: number
      label: string
      active: boolean
"""
    )

    assert manifest.frontend_resources is not None
    assert manifest.frontend_resources.paths == {
        "stats": "stats/",
        "deals": "deals/bulk-update-stage/",
    }
    assert manifest.frontend_resources.payload_types == {
        "CrmStats": {
            "contacts": "number",
            "label": "string",
            "active": "boolean",
        }
    }


def test_section_may_declare_only_paths() -> None:
    manifest = _load(
        """
frontend_resources:
  paths:
    stats: stats/
"""
    )

    assert manifest.frontend_resources is not None
    assert manifest.frontend_resources.paths == {"stats": "stats/"}
    assert manifest.frontend_resources.payload_types == {}


def test_section_allows_a_path_without_a_trailing_slash() -> None:
    manifest = _load(
        """
frontend_resources:
  paths:
    settings: settings
"""
    )

    assert manifest.frontend_resources is not None
    assert manifest.frontend_resources.paths == {"settings": "settings"}


def test_section_parses_a_parameterized_path() -> None:
    manifest = _load(
        """
frontend_resources:
  paths:
    memberRole: members/{membershipId}/role/
"""
    )

    assert manifest.frontend_resources is not None
    assert manifest.frontend_resources.paths == {
        "memberRole": "members/{membershipId}/role/"
    }


def test_section_parses_rich_payload_type_forms() -> None:
    manifest = _load(
        """
frontend_resources:
  payload_types:
    OrgRole: "'viewer' | 'member'"
    OrgSummary:
      id: string
      role?: OrgRole
      name: "OrgRole | null"
      tags: "string[]"
    OrgListResponse:
      organizations: "OrgSummary[]"
"""
    )

    assert manifest.frontend_resources is not None
    assert manifest.frontend_resources.payload_types == {
        "OrgRole": "'viewer' | 'member'",
        "OrgSummary": {
            "id": "string",
            "role?": "OrgRole",
            "name": "OrgRole | null",
            "tags": "string[]",
        },
        "OrgListResponse": {"organizations": "OrgSummary[]"},
    }


def test_section_refuses_an_undeclared_payload_type_reference() -> None:
    with pytest.raises(ManifestError, match="undeclared payload type"):
        _load(
            """
frontend_resources:
  payload_types:
    OrgSummary:
      role: OrgRole
"""
        )


def test_section_may_declare_only_payload_types() -> None:
    manifest = _load(
        """
frontend_resources:
  payload_types:
    CrmStats:
      contacts: number
"""
    )

    assert manifest.frontend_resources is not None
    assert manifest.frontend_resources.paths == {}
    assert manifest.frontend_resources.payload_types == {
        "CrmStats": {"contacts": "number"}
    }


@pytest.mark.parametrize(
    ("section", "message"),
    [
        ("frontend_resources: not_a_mapping\n", "must be a mapping"),
        (
            "frontend_resources:\n  routes: {}\n",
            "unknown key 'routes'",
        ),
        ("frontend_resources:\n  paths: {}\n", "at least one path"),
        (
            "frontend_resources:\n  paths:\n    1: stats/\n",
            "resource names",
        ),
        (
            "frontend_resources:\n  paths:\n    stats: /stats/\n",
            "module-relative",
        ),
        (
            "frontend_resources:\n  paths:\n    stats: stats/../admin/\n",
            "'.' or '..'",
        ),
        (
            "frontend_resources:\n  paths:\n    stats: stats/?page=1\n",
            "query string",
        ),
        (
            "frontend_resources:\n  paths:\n    stats: stats/<int:pk>/\n",
            "angle-bracket",
        ),
        (
            "frontend_resources:\n  paths:\n    stats: '{id}/stats/{id}/'\n",
            "placeholder once",
        ),
        (
            "frontend_resources:\n  paths:\n    detail: '{class}/'\n",
            "reserved word",
        ),
        (
            "frontend_resources:\n  payload_types:\n    crmstats:\n      contacts: number\n",
            "type names",
        ),
        (
            "frontend_resources:\n  payload_types:\n    CrmStats: {}\n",
            "non-empty mapping",
        ),
        (
            "frontend_resources:\n  payload_types:\n    CrmStats:\n      1contact: number\n",
            "field names",
        ),
        (
            "frontend_resources:\n  payload_types:\n    CrmStats:\n      contacts: int\n",
            "must be a scalar",
        ),
        (
            "frontend_resources:\n  payload_types:\n    CrmStats:\n      contacts: []\n",
            "must be a scalar",
        ),
        (
            "frontend_resources:\n  payload_types:\n    CrmStats:\n      contacts: {}\n",
            "must be a scalar",
        ),
    ],
)
def test_malformed_section_is_refused(section: str, message: str) -> None:
    with pytest.raises(ManifestError, match=message):
        _load(section)


def test_crm_manifest_declares_the_theme_contract() -> None:
    """The shipped CRM manifest declares the paths and type its page consumes."""
    from pathlib import Path

    manifest_path = (
        Path(__file__).resolve().parents[2]
        / "quickscale_modules"
        / "crm"
        / "module.yml"
    )
    from quickscale_core.manifest.loader import load_manifest_from_path

    manifest = load_manifest_from_path(manifest_path)

    assert manifest.frontend_resources is not None
    assert manifest.frontend_resources.paths == {
        "stats": "stats/",
        "contacts": "contacts/",
        "companies": "companies/",
        "deals": "deals/",
        "tags": "tags/",
    }
    assert manifest.frontend_resources.payload_types == {
        "CrmStats": {
            "contacts": "number",
            "companies": "number",
            "deals": "number",
            "tags": "number",
        }
    }
