"""Email notification helpers for Forms module"""

from __future__ import annotations

import logging
from importlib import import_module
from typing import TYPE_CHECKING, Any

from django.apps import apps
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

if TYPE_CHECKING:
    from quickscale_modules_forms.models import FormSubmission

logger = logging.getLogger(__name__)

_TRACKED_SUBMISSION_TEMPLATE_KEY = "notifications.forms_submission"


def notify_submission(submission: "FormSubmission") -> None:
    """Send email notification to form owners for a new non-spam submission"""
    if submission.is_spam:
        return

    form = submission.form
    recipients = [
        email.strip() for email in form.notify_emails.split(",") if email.strip()
    ]
    if not recipients:
        return

    notification_content = _build_submission_notification_content(submission)

    try:
        tracked_sender = _load_tracked_notification_sender()
        if tracked_sender is None:
            _send_untracked_submission_email(
                recipients=recipients,
                subject=notification_content["subject"],
                plain_text_body=notification_content["plain_text_body"],
                html_body=notification_content["html_body"],
            )
            return

        tracked_sender(
            template_key=_TRACKED_SUBMISSION_TEMPLATE_KEY,
            recipients=recipients,
            context=notification_content["tracked_context"],
            tags=["forms"],
            metadata={"workflow": "form-submission"},
        )
    except Exception:
        # Never block submission processing due to delivery failure
        logger.warning(
            "Failed to send notification email for submission #%s (form: %s)",
            submission.pk,
            form.slug,
            exc_info=True,
        )


def _build_submission_notification_content(
    submission: "FormSubmission",
) -> dict[str, Any]:
    form = submission.form
    field_pairs = [
        (fv.field_label, fv.value)
        for fv in submission.values.all().order_by("field__order", "field_name")
    ]
    submitter_name = next(
        (value for label, value in field_pairs if "name" in label.lower()),
        None,
    )
    subject = f"[{form.title}] New submission"
    if submitter_name:
        subject = f"{subject} from {submitter_name}"

    submitted_at_display = str(submission.submitted_at)
    ip_address = submission.ip_address or "unknown"
    template_context = {
        "form_title": form.title,
        "submitted_at": submitted_at_display,
        "fields": field_pairs,
        "ip_address": ip_address,
        "status": submission.status,
        "submitter_name": submitter_name or "",
    }

    body_lines = [f"New submission for: {form.title}", ""]
    for label, value in field_pairs:
        body_lines.append(f"{label}: {value}")
    body_lines += [
        "",
        f"Submitted: {submitted_at_display}",
        f"IP address: {ip_address}",
        f"Status: {submission.status}",
    ]

    html_body = render_to_string(
        "quickscale_modules_forms/forms/form_email.html",
        template_context,
    )

    return {
        "subject": subject,
        "plain_text_body": "\n".join(body_lines),
        "html_body": html_body,
        "tracked_context": template_context,
    }


def _load_tracked_notification_sender() -> Any | None:
    if not apps.is_installed("quickscale_modules_notifications"):
        return None
    if not bool(getattr(settings, "QUICKSCALE_NOTIFICATIONS_ENABLED", True)):
        return None
    notifications_services = import_module("quickscale_modules_notifications.services")
    return getattr(notifications_services, "send_notification")


def _send_untracked_submission_email(
    *,
    recipients: list[str],
    subject: str,
    plain_text_body: str,
    html_body: str,
) -> None:
    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_text_body,
        from_email=None,
        to=recipients,
    )
    email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=False)
