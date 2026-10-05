"""Tests for backups' declared personal-data treatments (rule 49)."""

from __future__ import annotations

import pytest
from django.apps import apps

from quickscale_core.runtime import (
    PersonalDataField,
    PersonalDataTreatment,
    collect_capabilities,
)


def _declared_fields() -> dict[tuple[str, str], PersonalDataTreatment]:
    config = apps.get_app_config("quickscale_backups")
    return {
        (entry.model_name, entry.field_name): entry.treatment
        for entry in config.personal_data_declarations()
        if isinstance(entry, PersonalDataField)
    }


@pytest.mark.django_db
def test_declared_keep_link_treatment_holds_on_a_populated_user(superuser) -> None:
    """Backups' initiator row is keep-link: no handler executes for it."""
    from quickscale_modules_backups.models import BackupArtifact

    assert _declared_fields() == {
        ("BackupArtifact", "initiated_by"): PersonalDataTreatment.KEEP_LINK,
    }

    artifact = BackupArtifact.objects.create(
        filename="declared-treatment.dump",
        checksum_sha256="abc123",
        database_engine="django.db.backends.postgresql",
        initiated_by=superuser,
    )

    assert artifact.initiated_by_id == superuser.pk
    handlers = {
        getattr(handler, "label", None)
        for handler in collect_capabilities("anonymize_handlers")
    }
    assert "quickscale_backups" not in handlers
