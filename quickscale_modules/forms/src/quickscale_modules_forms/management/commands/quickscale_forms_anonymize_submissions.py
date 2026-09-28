"""Management command to anonymize old form submissions for GDPR compliance"""

from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from quickscale_modules_forms.models import Form, FormSubmission


class Command(BaseCommand):
    """Anonymizes IP address and user agent for submissions older than each form's data_retention_days"""

    help = (
        "Anonymize submission data older than each form's data_retention_days setting"
    )

    def handle(self, *args: Any, **options: Any) -> None:
        from django.db import transaction

        from quickscale_modules_orgs.current_org import operator_access, org_scope

        total_anonymized = 0
        now = timezone.now()

        with transaction.atomic():
            # Phase 1 — Read form inventory with operator_access (SELECT-only
            # cross-tenant read).  Ensures every form is visited regardless
            # of which org the GUC is set to.
            with operator_access(reason="forms_anonymize: read form inventory"):
                forms = list(Form.all_objects.all())

            for form in forms:
                if form.data_retention_days == 0:
                    # 0 = keep forever
                    continue

                cutoff = now - timedelta(days=form.data_retention_days)

                # Phase 2 — Read old submission PKs within the form's org via
                # operator_access.  The update itself runs under org_scope so
                # FORCE RLS write-path policy allows the modification.
                with operator_access(reason="forms_anonymize: read old submission PKs"):
                    old_pks = list(
                        FormSubmission.all_objects.filter(
                            form=form,
                            submitted_at__lt=cutoff,
                        )
                        .exclude(ip_address=None)
                        .values_list("pk", flat=True)
                    )

                if old_pks:
                    # Phase 3 — Update inside the form's owning org scope.
                    # Every write uses the public ``objects`` manager under
                    # ``org_scope`` so FORCE RLS sees the correct
                    # ``app.current_org_id`` (write-path policy).
                    with org_scope(form.organization):
                        count = (
                            FormSubmission.objects.filter(pk__in=old_pks)
                            .exclude(ip_address=None)
                            .update(ip_address=None, user_agent="")
                        )
                        total_anonymized += count
                        self.stdout.write(
                            f"  Anonymized {count} submissions for form: {form.slug}"
                        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Total submissions anonymized: {total_anonymized}"
            )
        )
