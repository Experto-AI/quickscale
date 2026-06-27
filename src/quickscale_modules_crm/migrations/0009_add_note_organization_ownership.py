"""Add direct organization ownership to ContactNote and DealNote (AF1 Phase 3).

Schema changes:
  - Add NOT NULL ``organization`` FK (PROTECT) to both ContactNote and DealNote.
  - Backfill existing rows from the parent Contact/Deal.
  - Install/ensure the shared child-parent equality trigger function.
  - Enable BEFORE INSERT OR UPDATE triggers that enforce
    ContactNote.organization_id = Contact.organization_id and
    DealNote.organization_id = Deal.organization_id.
  - Enable and FORCE PostgreSQL Row-Level Security on both note tables.

After this migration, ContactNote and DealNote are direct-owned tenant tables:
  - ``objects`` = TenantManager()
  - ``all_objects`` = TenantManager(super_scope=True)
  - live FORCE-RLS policy on ``organization_id``
  - DB-level child-parent equality trigger against the parent table.
"""

from __future__ import annotations

from typing import Any

import django.db.models.deletion
from django.db import migrations, models

from quickscale_modules_orgs.tenancy import (
    apply_force_rls,
    enable_child_parent_equality,
    install_equality_trigger_function,
    revert_force_rls,
    disable_child_parent_equality,
)

# ---------------------------------------------------------------------------
# Table names
# ---------------------------------------------------------------------------
CRM_CONTACTNOTE_TABLE = "quickscale_modules_crm_contactnote"
CRM_DEALNOTE_TABLE = "quickscale_modules_crm_dealnote"

CRM_CONTACTNOTE_RLS_POLICY = "crm_contactnote_org_isolation"
CRM_DEALNOTE_RLS_POLICY = "crm_dealnote_org_isolation"

_CONTACTNOTE_RLS_TARGETS = (
    (CRM_CONTACTNOTE_TABLE, CRM_CONTACTNOTE_RLS_POLICY),
    (CRM_DEALNOTE_TABLE, CRM_DEALNOTE_RLS_POLICY),
)

# ---------------------------------------------------------------------------
# Backfill helpers
# ---------------------------------------------------------------------------


def _backfill_contactnote_org(apps: Any, schema_editor: Any) -> None:
    """Copy organization_id from the parent Contact to ContactNote rows."""
    del schema_editor
    ContactNote = apps.get_model("quickscale_modules_crm", "ContactNote")
    Contact = apps.get_model("quickscale_modules_crm", "Contact")
    for note in ContactNote._base_manager.filter(organization__isnull=True).iterator():
        try:
            parent = Contact._base_manager.get(pk=note.contact_id)
        except Contact.DoesNotExist:
            continue
        ContactNote._base_manager.filter(pk=note.pk).update(
            organization_id=parent.organization_id
        )


def _backfill_dealnote_org(apps: Any, schema_editor: Any) -> None:
    """Copy organization_id from the parent Deal to DealNote rows."""
    del schema_editor
    DealNote = apps.get_model("quickscale_modules_crm", "DealNote")
    Deal = apps.get_model("quickscale_modules_crm", "Deal")
    for note in DealNote._base_manager.filter(organization__isnull=True).iterator():
        try:
            parent = Deal._base_manager.get(pk=note.deal_id)
        except Deal.DoesNotExist:
            continue
        DealNote._base_manager.filter(pk=note.pk).update(
            organization_id=parent.organization_id
        )


def _assert_no_null_org_notes(apps: Any, schema_editor: Any) -> None:
    """Guard: fail the migration if any note still has NULL organization."""
    del schema_editor
    ContactNote = apps.get_model("quickscale_modules_crm", "ContactNote")
    DealNote = apps.get_model("quickscale_modules_crm", "DealNote")

    null_cn = ContactNote._base_manager.filter(organization__isnull=True).count()
    null_dn = DealNote._base_manager.filter(organization__isnull=True).count()

    if null_cn or null_dn:
        parts = []
        if null_cn:
            parts.append(f"ContactNote={null_cn}")
        if null_dn:
            parts.append(f"DealNote={null_dn}")
        raise RuntimeError(
            "Migration 0009 cannot set NOT NULL on note.organization "
            "while NULL-owned rows remain: "
            + ", ".join(parts)
            + ". Backfill organization ownership for these rows before "
            "applying the AF1 Phase 3 schema flip."
        )


def _install_equality_and_rls(apps: Any, schema_editor: Any) -> None:
    """Install equality trigger function, enable triggers, and enable FORCE RLS."""
    del apps

    # 1. Install/refresh the shared trigger function (idempotent).
    install_equality_trigger_function(schema_editor)

    # 2. Enable child-parent equality triggers.
    enable_child_parent_equality(
        schema_editor,
        child_table=CRM_CONTACTNOTE_TABLE,
        parent_table="quickscale_modules_crm_contact",
        child_fk_column="contact_id",
    )
    enable_child_parent_equality(
        schema_editor,
        child_table=CRM_DEALNOTE_TABLE,
        parent_table="quickscale_modules_crm_deal",
        child_fk_column="deal_id",
    )

    # 3. Enable FORCE RLS on both note tables.
    apply_force_rls(schema_editor, _CONTACTNOTE_RLS_TARGETS)


def _uninstall_equality_and_rls(apps: Any, schema_editor: Any) -> None:
    """Reverse: drop RLS policies, drop triggers (function is kept)."""
    del apps

    # 1. Revert FORCE RLS (drop policies, disable RLS).
    revert_force_rls(schema_editor, _CONTACTNOTE_RLS_TARGETS)

    # 2. Drop equality triggers.
    disable_child_parent_equality(
        schema_editor,
        child_table=CRM_CONTACTNOTE_TABLE,
    )
    disable_child_parent_equality(
        schema_editor,
        child_table=CRM_DEALNOTE_TABLE,
    )
    # Note: the shared trigger function is left in place — it may be
    # used by other tables and is simply kept as a no-op function.


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class Migration(migrations.Migration):
    """Add direct organization ownership to ContactNote and DealNote."""

    dependencies = [
        ("quickscale_modules_crm", "0008_enable_rls"),
        ("quickscale_modules_orgs", "0004_organizationtombstone"),
    ]

    operations = [
        # ---- Step 1: Add nullable organization FK ----
        migrations.AddField(
            model_name="contactnote",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="crm_contact_notes",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AddField(
            model_name="dealnote",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="crm_deal_notes",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        # ---- Step 2: Backfill from parent Contact/Deal ----
        migrations.RunPython(
            code=_backfill_contactnote_org,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            code=_backfill_dealnote_org,
            reverse_code=migrations.RunPython.noop,
        ),
        # ---- Step 3: Guard against NULL rows before setting NOT NULL ----
        migrations.RunPython(
            code=_assert_no_null_org_notes,
            reverse_code=migrations.RunPython.noop,
        ),
        # ---- Step 4: Make NOT NULL + PROTECT ----
        migrations.AlterField(
            model_name="contactnote",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="crm_contact_notes",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AlterField(
            model_name="dealnote",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="crm_deal_notes",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        # ---- Step 5: Install equality triggers and enable RLS ----
        migrations.RunPython(
            code=_install_equality_and_rls,
            reverse_code=_uninstall_equality_and_rls,
            hints={"target_db": "default"},
        ),
    ]
