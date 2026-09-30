"""Project-owned provider-ID classification fixture used by the provider-ID suite."""

from django.db import models

from quickscale_modules_orgs.models import TenantModel
from quickscale_modules_orgs.removal import NOT_PROVIDER_BACKED, PROVIDER_BACKED


class ProjectProviderRecord(TenantModel):
    """Project-owned tenant model classifying its own ``*_id`` fields.

    ``mls_id`` is provider-backed: purge refuses while a row carries a value.
    ``local_ref_id`` is project-internal and is deleted with the row.
    """

    mls_id = models.CharField(max_length=64, blank=True, default="")
    local_ref_id = models.CharField(max_length=64, blank=True, default="")

    provider_id_classification = {
        "mls_id": PROVIDER_BACKED,
        "local_ref_id": NOT_PROVIDER_BACKED,
    }

    class Meta(TenantModel.Meta):
        verbose_name = "Project provider record"
        verbose_name_plural = "Project provider records"
