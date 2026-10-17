"""Retention anonymization behind ``quickscale_forms_anonymize_submissions``.

The retention operation lives beside the command that invokes it because it
enters through orgs' command-only ``operator_access_for_command`` (Module
Conventions rule 44 keeps that entry inside ``management/commands/``), and it
owns the run's ``transaction.atomic()`` so the command module opens no
transaction of its own (rule 17).
"""

from __future__ import annotations


def anonymize_expired_submissions(*, dry_run: bool = False) -> list[tuple[str, int]]:
    """Anonymize each form's submissions older than its retention window.

    Rule 17: the retention operation owns its ``transaction.atomic()``, so
    the command module opens no transaction of its own.  Every form is
    visited regardless of which organization the current GUC names, and each
    update runs in its form's own organization scope so FORCE RLS's
    write-path policy admits it.

    Args:
        dry_run: Count what a real run would anonymize without writing.

    Returns:
        One ``(form slug, affected submission count)`` pair per form that has
        submissions past its retention window, in form order.
    """
    from datetime import timedelta

    from django.db import transaction
    from django.utils import timezone

    from quickscale_modules_forms.models import Form, FormSubmission
    from quickscale_modules_orgs.current_org import (
        operator_access_for_command,
        org_scope,
    )

    results: list[tuple[str, int]] = []
    now = timezone.now()

    with transaction.atomic():
        # Phase 1 — Read form inventory with operator_access_for_command
        # (SELECT-only cross-tenant read).  Ensures every form is visited
        # regardless of which org the GUC is set to; the command variant
        # records this command's name in the audit log.
        with operator_access_for_command(
            command="quickscale_forms_anonymize_submissions",
            reason="forms_anonymize: read form inventory",
        ):
            forms = list(Form.all_objects.all())

        for form in forms:
            if form.data_retention_days == 0:
                # 0 = keep forever
                continue

            cutoff = now - timedelta(days=form.data_retention_days)

            # Phase 2 — Read old submission PKs within the form's org via
            # the command operator scope.  The update itself runs under
            # org_scope so FORCE RLS write-path policy allows the
            # modification.
            with operator_access_for_command(
                command="quickscale_forms_anonymize_submissions",
                reason="forms_anonymize: read old submission PKs",
            ):
                old_pks = list(
                    FormSubmission.all_objects.filter(
                        form=form,
                        submitted_at__lt=cutoff,
                    )
                    .exclude(ip_address=None)
                    .values_list("pk", flat=True)
                )

            if not old_pks:
                continue

            if dry_run:
                results.append((form.slug, len(old_pks)))
                continue

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
                results.append((form.slug, count))

    return results
