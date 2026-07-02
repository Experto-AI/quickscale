"""Signal receivers for the QuickScale CRM module.

SA7.1 — ``seed_crm_default_stages_on_org_created`` is the CRM-side
receiver of the ``organization_created`` signal from the orgs module,
replacing the old reverse-import pattern in ``crm_bootstrap.py``.
"""

from django.dispatch import receiver

from quickscale_modules_crm.services import ensure_org_default_stages
from quickscale_modules_orgs.models import Organization
from quickscale_modules_orgs.signals import organization_created


@receiver(organization_created, sender=Organization)
def seed_crm_default_stages_on_org_created(
    sender: type[Organization],
    organization: Organization,
    **kwargs: object,
) -> None:
    """Seed CRM default pipeline stages for a newly created organization.

    Connected in ``QuickscaleCrmConfig.ready()`` so that this receiver
    is only active when the CRM module is installed.
    """
    ensure_org_default_stages(organization)
