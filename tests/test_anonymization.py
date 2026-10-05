"""Tests for forms' declared personal-data treatments (rule 49)."""

from __future__ import annotations

import pytest
from django.apps import apps

from quickscale_core.runtime import (
    PersonalDataField,
    PersonalDataTreatment,
    collect_capabilities,
)


def _declared_fields() -> dict[tuple[str, str], PersonalDataTreatment]:
    config = apps.get_app_config("quickscale_forms")
    return {
        (entry.model_name, entry.field_name): entry.treatment
        for entry in config.personal_data_declarations()
        if isinstance(entry, PersonalDataField)
    }


@pytest.mark.django_db
def test_declared_keep_link_treatment_holds_on_a_populated_user(user) -> None:
    """Forms' creator row is keep-link: no handler executes, so it survives."""
    from quickscale_modules_forms.models import Form
    from quickscale_modules_orgs.current_org import org_scope
    from quickscale_modules_orgs.models import Organization

    assert _declared_fields() == {
        ("Form", "created_by"): PersonalDataTreatment.KEEP_LINK,
    }

    system_org = Organization.objects.get_system_org()
    with org_scope(system_org):
        form = Form.all_objects.create(
            title="Declared treatment",
            slug="declared-treatment",
            organization=system_org,
            created_by=user,
        )

    assert form.created_by_id == user.pk
    handlers = {
        getattr(handler, "label", None)
        for handler in collect_capabilities("anonymize_handlers")
    }
    assert "quickscale_forms" not in handlers
