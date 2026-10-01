"""Tracked submission notifications for the Forms module (rules 20-21).

Forms sends every email through notifications' ``send_notification``; the
module declares ``notifications`` in ``required_modules`` and carries no
fallback sender.  The send is scheduled with ``transaction.on_commit`` so a
rolled-back submission sends nothing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db import transaction

from quickscale_modules_notifications.services import send_notification

if TYPE_CHECKING:
    from quickscale_modules_forms.models import FormSubmission

logger = logging.getLogger(__name__)

_TRACKED_SUBMISSION_TEMPLATE_KEY = "notifications.forms_submission"


def notify_submission(submission: "FormSubmission") -> str:
    """Queue the tracked notification for a new non-spam submission.

    Never raises — a notification failure must never affect the form
    submission response.  Returns a status string: "queued",
    "no_recipients", "skipped_spam", or "enqueue_error".
    """
    try:
        return _enqueue_notification(submission)
    except Exception:
        logger.warning(
            "Unexpected error preparing notification for submission #%s",
            submission.pk,
            exc_info=True,
        )
        return "enqueue_error"


def _enqueue_notification(submission: "FormSubmission") -> str:
    if submission.is_spam:
        return "skipped_spam"

    # CR-SA85-REV-007: dereference submission.form inside org_scope so
    # that lazy FK traversal finds the related Form under the correct
    # RLS context.  Extract the fields we need before the scope exits.
    from quickscale_modules_orgs.current_org import org_scope

    with org_scope(submission.organization):
        form = submission.form
        notify_emails_raw = form.notify_emails if form else ""
        form_slug = form.slug if form else "unknown"
        form_pk = form.pk if form else None

    recipients = [
        email.strip() for email in notify_emails_raw.split(",") if email.strip()
    ]
    if not recipients:
        logger.warning(
            "No notify_emails configured for form '%s' (pk=%s) — notification skipped",
            form_slug,
            form_pk,
        )
        return "no_recipients"

    # CR-P3-006: materialize notification context inside a short org scope
    # so FORCE RLS allows reading committed FormFieldValue rows via the
    # DB-level app.current_org_id GUC.  The scope exits before the actual
    # delivery so we never hold a live transaction for remote calls.
    with org_scope(submission.organization):
        notification_context = _build_submission_notification_context(submission)

    def _dispatch() -> None:
        try:
            send_notification(
                template_key=_TRACKED_SUBMISSION_TEMPLATE_KEY,
                recipients=recipients,
                context=notification_context,
                tags=["forms"],
                metadata={"workflow": "form-submission"},
            )
        except Exception:
            # Never block submission processing due to delivery failure
            logger.warning(
                "Failed to send notification email for submission #%s (form: %s)",
                submission.pk,
                form_slug,
                exc_info=True,
            )

    logger.warning(
        "Queueing notification for submission #%s (form: %s) to %s",
        submission.pk,
        form_slug,
        recipients,
    )
    # Rule 21: the effect belongs to the write's commit, not to the caller.
    transaction.on_commit(_dispatch)
    return "queued"


def _build_submission_notification_context(
    submission: "FormSubmission",
) -> dict[str, Any]:
    form = submission.form
    # CR-P3-006: use all_objects to bypass TenantManager scoping.
    # This function can be called after tenant_context() exits (post-commit),
    # so the ContextVar may be None — the TenantManager would return zero
    # rows, causing notification emails to lose field values.
    from quickscale_modules_forms.models import FormFieldValue

    field_pairs = [
        [fv.field_label, fv.value]
        for fv in FormFieldValue.all_objects.filter(submission=submission).order_by(
            "field__order", "field_name"
        )
    ]
    submitter_name = next(
        (value for label, value in field_pairs if "name" in label.lower()),
        None,
    )

    return {
        "form_title": form.title,
        "submitted_at": str(submission.submitted_at),
        "fields": field_pairs,
        "ip_address": submission.ip_address or "unknown",
        "status": submission.status,
        "submitter_name": submitter_name or "",
    }
