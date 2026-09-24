"""Project-owned provider-ID classification fixture used by the SA208 suite."""

from django.db import models

from quickscale_modules_orgs.managers import TenantManager
from quickscale_modules_orgs.removal import NOT_PROVIDER_BACKED, PROVIDER_BACKED
from quickscale_modules_orgs.tenancy import tenant_org_fk


class ProjectProviderRecord(models.Model):
    """Project-owned tenant model classifying its own ``*_id`` fields.

    ``mls_id`` is provider-backed: purge refuses while a row carries a value.
    ``local_ref_id`` is project-internal and is deleted with the row.
    """

    organization = tenant_org_fk(related_name="sa208_provider_records")
    mls_id = models.CharField(max_length=64, blank=True, default="")
    local_ref_id = models.CharField(max_length=64, blank=True, default="")

    provider_id_classification = {
        "mls_id": PROVIDER_BACKED,
        "local_ref_id": NOT_PROVIDER_BACKED,
    }

    objects = TenantManager()
    all_objects = TenantManager(super_scope=True)

    class Meta:
        base_manager_name = "all_objects"
        verbose_name = "Project provider record"
        verbose_name_plural = "Project provider records"
