"""Management command to anonymize old form submissions for GDPR compliance.

AF3 phase 1+2: wraps the operator-level iteration in ``operator_access()``
for audit trail, and replaces raw ``.all_objects.`` scans with explicit
org-scoped iteration.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from quickscale_modules_forms.models import Form, FormSubmission
from quickscale_modules_orgs.current_org import org_scope
from quickscale_modules_orgs.models import Organization
from quickscale_modules_orgs.operator_access import operator_access


class Command(BaseCommand):
    """Anonymizes IP address and user agent for submissions older than each
    form's data_retention_days"""

    help = (
        "Anonymize submission data older than each form's data_retention_days setting"
    )

    def handle(self, *args: Any, **options: Any) -> None:
        total_anonymized = 0
        now = timezone.now()

        with operator_access(reason="anonymize old form submissions") as log:
            log.command = "forms_anonymize_submissions"
            log.actor_identifier = "cli:forms_anonymize_submissions"
            log.target_scope = "all_orgs"

            # Pre-populate target_org_ids for failure-stable audit metadata
            # before any risky work.
            all_org_ids = list(Organization.objects.values_list("pk", flat=True))
            log.target_org_ids = sorted(str(oid) for oid in all_org_ids)
            log.touched_org_ids = []

            # Iterate all organizations explicitly — including the System
            # org (D2) — instead of using a raw ``all_objects`` scan.
            for org in Organization.objects.iterator():
                org_touched = False
                with org_scope(org):
                    for form in Form.objects.iterator():
                        if form.data_retention_days == 0:
                            # 0 = keep forever
                            continue

                        cutoff = now - timedelta(days=form.data_retention_days)
                        old_submissions = FormSubmission.objects.filter(
                            form=form,
                            submitted_at__lt=cutoff,
                        ).exclude(ip_address=None)

                        count = old_submissions.count()
                        if count > 0:
                            old_submissions.update(ip_address=None, user_agent="")
                            total_anonymized += count
                            org_touched = True
                            self.stdout.write(
                                f"  Anonymized {count} submissions for "
                                f"form: {form.slug} (org={org.pk})"
                            )

                if org_touched:
                    log.touched_org_ids.append(str(org.pk))
                    # Keep sorted so the audit record is deterministic.
                    log.touched_org_ids.sort()

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Total submissions anonymized: {total_anonymized}"
            )
        )
