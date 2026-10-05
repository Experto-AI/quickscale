"""Tests for CRM's declared personal-data treatments (rule 49)."""

from __future__ import annotations

import pytest
from django.apps import apps

from quickscale_core.runtime import (
    PersonalDataField,
    PersonalDataTreatment,
    collect_capabilities,
)


def _declared_fields() -> dict[tuple[str, str], PersonalDataTreatment]:
    config = apps.get_app_config("quickscale_crm")
    return {
        (entry.model_name, entry.field_name): entry.treatment
        for entry in config.personal_data_declarations()
        if isinstance(entry, PersonalDataField)
    }


@pytest.mark.django_db
def test_declared_keep_link_treatments_hold_on_a_populated_user(user, deal) -> None:
    """CRM's rows are keep-link: no handler executes, so the links survive."""
    assert _declared_fields() == {
        ("ContactNote", "created_by"): PersonalDataTreatment.KEEP_LINK,
        ("DealNote", "created_by"): PersonalDataTreatment.KEEP_LINK,
        ("Deal", "owner"): PersonalDataTreatment.KEEP_LINK,
    }

    assert deal.owner_id == user.pk
    handlers = {
        getattr(handler, "label", None)
        for handler in collect_capabilities("anonymize_handlers")
    }
    assert "quickscale_crm" not in handlers
