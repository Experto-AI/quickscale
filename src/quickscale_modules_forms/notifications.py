"""Email notification helpers for Forms module"""

from __future__ import annotations

import logging
import threading
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
_SYNC_EMAIL_BACKENDS = {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
}


def notify_submission(submission: "FormSubmission") -> str:
    """Send email notification to form owners for a new non-spam submission.

    Never raises — a notification failure must never affect the form submission response.
    Returns a status string: "queued", "no_recipients", "skipped_spam", or "enqueue_error".
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

    form = submission.form
    recipients = [
        email.strip() for email in form.notify_emails.split(",") if email.strip()
    ]
    if not recipients:
        logger.warning(
            "No notify_emails configured for form '%s' (pk=%s) — notification skipped",
            form.slug,
            form.pk,
        )
        return "no_recipients"

    notification_content = _build_submission_notification_content(submission)

    tracked_sender = _load_tracked_notification_sender()

    def _dispatch() -> None:
        try:
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

    logger.warning(
        "Sending notification for submission #%s (form: %s) to %s",
        submission.pk,
        form.slug,
        recipients,
    )
    if tracked_sender is not None or _should_send_untracked_inline():
        _dispatch()
        return "queued"

    # Keep real backend delivery off the request thread for the legacy SMTP path.
    threading.Thread(target=_dispatch, daemon=False).start()
    return "queued"


def _build_submission_notification_content(
    submission: "FormSubmission",
) -> dict[str, Any]:
    form = submission.form
    # CR-P3-006: use all_objects to bypass TenantManager scoping.
    # This function can be called after tenant_context() exits (post-commit),
    # so the ContextVar may be None — the TenantManager would return zero
    # rows, causing notification emails to lose field values.
    from quickscale_modules_forms.models import FormFieldValue

    field_pairs = [
        (fv.field_label, fv.value)
        for fv in FormFieldValue.all_objects.filter(submission=submission).order_by(
            "field__order", "field_name"
        )
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


def _should_send_untracked_inline() -> bool:
    return str(getattr(settings, "EMAIL_BACKEND", "")).strip() in _SYNC_EMAIL_BACKENDS


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
