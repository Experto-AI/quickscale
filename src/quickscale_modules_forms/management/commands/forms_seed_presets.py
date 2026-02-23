"""Management command to seed built-in form presets"""

from typing import Any

from django.core.management.base import BaseCommand

from quickscale_modules_forms.models import Form, FormField


class Command(BaseCommand):
    """Seeds ready-to-use form presets: contact, newsletter, feedback, support"""

    help = "Seed built-in form presets (contact, newsletter, feedback, support)"

    PRESETS = [
        {
            "title": "Contact",
            "slug": "contact",
            "description": "Get in Touch — share your current constraints, timeline, and target outcomes.",
            "success_message": "Thank you, we will respond within 24 hours.",
            "notify_emails": "",
            "fields": [
                {
                    "name": "full_name",
                    "field_type": "text",
                    "label": "Name",
                    "required": True,
                    "order": 1,
                    "layout_hint": "half_left",
                },
                {
                    "name": "email",
                    "field_type": "email",
                    "label": "Email",
                    "required": True,
                    "order": 2,
                    "layout_hint": "half_right",
                },
                {
                    "name": "company",
                    "field_type": "text",
                    "label": "Company",
                    "required": False,
                    "order": 3,
                    "layout_hint": "half_left",
                },
                {
                    "name": "subject",
                    "field_type": "text",
                    "label": "Subject",
                    "required": True,
                    "order": 4,
                    "layout_hint": "half_right",
                },
                {
                    "name": "project_context",
                    "field_type": "textarea",
                    "label": "Project Context",
                    "required": True,
                    "order": 5,
                    "layout_hint": "full",
                    "placeholder": "Describe your constraints, timeline, and target outcomes...",
                },
            ],
        },
        {
            "title": "Newsletter",
            "slug": "newsletter",
            "description": "Subscribe to our newsletter.",
            "success_message": "You're subscribed! Welcome aboard.",
            "notify_emails": "",
            "fields": [
                {
                    "name": "full_name",
                    "field_type": "text",
                    "label": "Name",
                    "required": True,
                    "order": 1,
                    "layout_hint": "half_left",
                },
                {
                    "name": "email",
                    "field_type": "email",
                    "label": "Email",
                    "required": True,
                    "order": 2,
                    "layout_hint": "half_right",
                },
            ],
        },
        {
            "title": "Feedback",
            "slug": "feedback",
            "description": "Share your feedback with us.",
            "success_message": "Thank you for your feedback!",
            "notify_emails": "",
            "fields": [
                {
                    "name": "full_name",
                    "field_type": "text",
                    "label": "Name",
                    "required": False,
                    "order": 1,
                    "layout_hint": "half_left",
                },
                {
                    "name": "email",
                    "field_type": "email",
                    "label": "Email",
                    "required": False,
                    "order": 2,
                    "layout_hint": "half_right",
                },
                {
                    "name": "rating",
                    "field_type": "select",
                    "label": "Rating",
                    "required": True,
                    "order": 3,
                    "layout_hint": "full",
                    "options": [
                        {"value": "1", "label": "1 — Poor"},
                        {"value": "2", "label": "2 — Fair"},
                        {"value": "3", "label": "3 — Good"},
                        {"value": "4", "label": "4 — Very Good"},
                        {"value": "5", "label": "5 — Excellent"},
                    ],
                },
                {
                    "name": "message",
                    "field_type": "textarea",
                    "label": "Message",
                    "required": True,
                    "order": 4,
                    "layout_hint": "full",
                },
            ],
        },
        {
            "title": "Support",
            "slug": "support",
            "description": "Submit a support request.",
            "success_message": "Your support request has been received. We'll get back to you shortly.",
            "notify_emails": "",
            "fields": [
                {
                    "name": "full_name",
                    "field_type": "text",
                    "label": "Name",
                    "required": True,
                    "order": 1,
                    "layout_hint": "half_left",
                },
                {
                    "name": "email",
                    "field_type": "email",
                    "label": "Email",
                    "required": True,
                    "order": 2,
                    "layout_hint": "half_right",
                },
                {
                    "name": "subject",
                    "field_type": "text",
                    "label": "Subject",
                    "required": True,
                    "order": 3,
                    "layout_hint": "full",
                },
                {
                    "name": "priority",
                    "field_type": "select",
                    "label": "Priority",
                    "required": True,
                    "order": 4,
                    "layout_hint": "half_left",
                    "options": [
                        {"value": "low", "label": "Low"},
                        {"value": "medium", "label": "Medium"},
                        {"value": "high", "label": "High"},
                    ],
                },
                {
                    "name": "description",
                    "field_type": "textarea",
                    "label": "Description",
                    "required": True,
                    "order": 5,
                    "layout_hint": "full",
                },
            ],
        },
    ]

    def handle(self, *args: Any, **options: Any) -> None:
        for preset in self.PRESETS:
            form, created = Form.objects.get_or_create(
                slug=preset["slug"],
                defaults={
                    "title": preset["title"],
                    "description": preset["description"],
                    "success_message": preset["success_message"],
                    "notify_emails": preset["notify_emails"],
                },
            )
            status_label = "Created" if created else "Already exists"
            self.stdout.write(f"  {status_label}: {form.slug}")

            for field_data in preset["fields"]:
                field_defaults = {k: v for k, v in field_data.items() if k != "name"}
                field_defaults.setdefault("placeholder", "")
                field_defaults.setdefault("options", [])
                field_defaults.setdefault("validation_rules", {})
                FormField.objects.get_or_create(
                    form=form,
                    name=field_data["name"],
                    defaults=field_defaults,
                )

        self.stdout.write(self.style.SUCCESS("Form presets seeded successfully."))
