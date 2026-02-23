"""Email notification helpers for Forms module"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

if TYPE_CHECKING:
    from quickscale_modules_forms.models import FormSubmission

logger = logging.getLogger(__name__)


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

    # Build field value pairs for email body
    field_pairs = [
        (fv.field_label, fv.value)
        for fv in submission.values.all().order_by("field__order", "field_name")
    ]

    # Use submitter name in subject if available
    name_value = next((v for label, v in field_pairs if "name" in label.lower()), None)
    if name_value:
        subject = f"[{form.title}] New submission from {name_value}"
    else:
        subject = f"[{form.title}] New submission"

    # Build plain-text body
    body_lines = [f"New submission for: {form.title}", ""]
    for label, value in field_pairs:
        body_lines.append(f"{label}: {value}")
    body_lines += [
        "",
        f"Submitted: {submission.submitted_at}",
        f"IP address: {submission.ip_address or 'unknown'}",
        f"Status: {submission.status}",
    ]
    plain_text_body = "\n".join(body_lines)

    html_body = render_to_string(
        "quickscale_modules_forms/forms/form_email.html",
        {
            "form_title": form.title,
            "submitted_at": submission.submitted_at,
            "fields": field_pairs,
            "ip_address": submission.ip_address or "unknown",
            "status": submission.status,
        },
    )

    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_text_body,
            from_email=None,  # Uses DEFAULT_FROM_EMAIL
            to=recipients,
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)
    except Exception:
        # Never block submission processing due to email failure
        logger.warning(
            "Failed to send notification email for submission #%s (form: %s)",
            submission.pk,
            form.slug,
            exc_info=True,
        )
