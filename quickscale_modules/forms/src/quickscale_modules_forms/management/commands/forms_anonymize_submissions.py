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
        total_anonymized = 0
        now = timezone.now()

        for form in Form.objects.all():
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
                self.stdout.write(
                    f"  Anonymized {count} submissions for form: {form.slug}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Total submissions anonymized: {total_anonymized}"
            )
        )
