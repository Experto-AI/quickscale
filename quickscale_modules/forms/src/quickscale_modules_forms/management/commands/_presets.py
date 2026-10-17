"""Preset seeding behind ``quickscale_forms_seed_presets``.

The seeding operation lives beside the command that invokes it because it
enters through orgs' command-only ``operator_access_for_command`` (Module
Conventions rule 44 keeps that entry inside ``management/commands/``), and it
owns the run's ``transaction.atomic()`` so the command module opens no
transaction of its own (rule 17).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

#: The ready-to-use presets, in seeding order.
PRESETS: list[dict[str, Any]] = [
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


def seed_form_presets() -> list[tuple[str, bool]]:
    """Seed the built-in form presets into the System organization.

    Rule 17: the seeding operation owns its ``transaction.atomic()``, so the
    command module opens no transaction of its own.  Presets are read and
    written under the System organization's scope so FORCE RLS's write-path
    policy admits every insert, and a rerun reports each preset that already
    exists instead of duplicating it.

    Returns:
        One ``(preset slug, created)`` pair per preset, in preset order.
    """
    from quickscale_modules_forms.models import Form, FormField
    from quickscale_modules_orgs.current_org import (
        operator_access_for_command,
        org_scope,
    )
    from quickscale_modules_orgs.models import Organization

    system_org = Organization.objects.get_system_org()

    results: list[tuple[str, bool]] = []
    with transaction.atomic():
        # Phase 1 — Read inventory: find which preset slugs already exist
        # in the System org. operator_access_for_command is SELECT-only:
        # it lets us see cross-tenant rows without elevating write
        # privilege, and records this command's name in the audit log.
        with operator_access_for_command(
            command="quickscale_forms_seed_presets",
            reason="quickscale_forms_seed_presets: lookup existing preset slugs",
        ):
            existing_slugs = set(
                Form.all_objects.filter(
                    organization=system_org,
                ).values_list("slug", flat=True)
            )

        # Phase 2 — Create/verify presets inside System org scope.
        # Every write uses the public ``objects`` manager under
        # ``org_scope`` so FORCE RLS sees the correct
        # ``app.current_org_id`` (write-path policy).
        with org_scope(system_org):
            for preset in PRESETS:
                slug = preset["slug"]
                if slug in existing_slugs:
                    form = Form.objects.get(slug=slug)
                    results.append((slug, False))
                else:
                    form = Form.objects.create(
                        slug=preset["slug"],
                        title=preset["title"],
                        description=preset["description"],
                        success_message=preset["success_message"],
                        notify_emails=preset["notify_emails"],
                        organization=system_org,
                    )
                    results.append((slug, True))

                for field_data in preset["fields"]:
                    field_defaults = {
                        k: v for k, v in field_data.items() if k != "name"
                    }
                    field_defaults.setdefault("placeholder", "")
                    field_defaults.setdefault("options", [])
                    field_defaults.setdefault("validation_rules", {})
                    # The ``objects`` manager does not auto-populate
                    # the org FK — set it explicitly in create values
                    # so FORCE RLS write-path policy allows the INSERT.
                    field_defaults.setdefault("organization", form.organization)
                    FormField.objects.get_or_create(
                        form=form,
                        name=field_data["name"],
                        defaults=field_defaults,
                    )

    return results
