"""Add direct organization ownership to ContactNote and DealNote (AF1 Phase 3 / AF12 Phase 1).

Schema changes:
  - Add NOT NULL ``organization`` FK (PROTECT) to both ContactNote and DealNote.
  - Backfill existing rows from the parent Contact/Deal.
  - Add UNIQUE (id, organization_id) constraints on Contact and Deal (parent tables).
  - Add DB-only composite FOREIGN KEYs enforcing child-parent org equality:
      ContactNote(contact_id, organization_id) → Contact(id, organization_id)
      DealNote(deal_id, organization_id) → Deal(id, organization_id)
  - Enable and FORCE PostgreSQL Row-Level Security on both note tables.

After this migration, ContactNote and DealNote are direct-owned tenant tables:
  - ``objects`` = TenantManager()
  - ``all_objects`` = TenantManager(super_scope=True)
  - live FORCE-RLS policy on ``organization_id``
  - DB-level composite FK enforcing child-parent ``organization_id`` equality.
"""

from __future__ import annotations

from typing import Any

import django.db.models.deletion
from django.db import migrations, models

from quickscale_modules_orgs.tenancy import (
    add_composite_child_fk,
    add_parent_unique_constraint,
    apply_force_rls,
    remove_composite_child_fk,
    remove_parent_unique_constraint,
    revert_force_rls,
)

# ---------------------------------------------------------------------------
# Table names
# ---------------------------------------------------------------------------
CRM_CONTACT_TABLE = "quickscale_modules_crm_contact"
CRM_DEAL_TABLE = "quickscale_modules_crm_deal"
CRM_CONTACTNOTE_TABLE = "quickscale_modules_crm_contactnote"
CRM_DEALNOTE_TABLE = "quickscale_modules_crm_dealnote"

CRM_CONTACTNOTE_RLS_POLICY = "crm_contactnote_org_isolation"
CRM_DEALNOTE_RLS_POLICY = "crm_dealnote_org_isolation"

_CONTACTNOTE_RLS_TARGETS = (
    (CRM_CONTACTNOTE_TABLE, CRM_CONTACTNOTE_RLS_POLICY),
    (CRM_DEALNOTE_TABLE, CRM_DEALNOTE_RLS_POLICY),
)

# ---------------------------------------------------------------------------
# Constraint names (AF12 Phase 1 naming contract)
# ---------------------------------------------------------------------------
CRM_CONTACT_ID_ORG_UNIQUE = "crm_contact_id_org_unique"
CRM_DEAL_ID_ORG_UNIQUE = "crm_deal_id_org_unique"
CRM_CONTACTNOTE_CONTACT_ORG_FK = "crm_contactnote_contact_org_fk"
CRM_DEALNOTE_DEAL_ORG_FK = "crm_dealnote_deal_org_fk"

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


# ---------------------------------------------------------------------------
# Composite FK + RLS helpers (AF12 Phase 1)
# ---------------------------------------------------------------------------


def _install_composite_fks_and_rls(apps: Any, schema_editor: Any) -> None:
    """Add parent unique constraints, composite child FKs, and enable FORCE RLS."""
    del apps

    # 1. Add UNIQUE (id, organization_id) on parent tables Contact and Deal.
    add_parent_unique_constraint(
        schema_editor,
        table=CRM_CONTACT_TABLE,
        constraint_name=CRM_CONTACT_ID_ORG_UNIQUE,
    )
    add_parent_unique_constraint(
        schema_editor,
        table=CRM_DEAL_TABLE,
        constraint_name=CRM_DEAL_ID_ORG_UNIQUE,
    )

    # 2. Add composite child FKs.
    add_composite_child_fk(
        schema_editor,
        child_table=CRM_CONTACTNOTE_TABLE,
        constraint_name=CRM_CONTACTNOTE_CONTACT_ORG_FK,
        child_fk_column="contact_id",
        parent_table=CRM_CONTACT_TABLE,
        on_delete="CASCADE",
    )
    add_composite_child_fk(
        schema_editor,
        child_table=CRM_DEALNOTE_TABLE,
        constraint_name=CRM_DEALNOTE_DEAL_ORG_FK,
        child_fk_column="deal_id",
        parent_table=CRM_DEAL_TABLE,
        on_delete="CASCADE",
    )

    # 3. Enable FORCE RLS on both note tables.
    apply_force_rls(schema_editor, _CONTACTNOTE_RLS_TARGETS)


def _uninstall_composite_fks_and_rls(apps: Any, schema_editor: Any) -> None:
    """Reverse: drop RLS policies, drop composite FKs, drop parent unique constraints."""
    del apps

    # 1. Revert FORCE RLS (drop policies, disable RLS).
    revert_force_rls(schema_editor, _CONTACTNOTE_RLS_TARGETS)

    # 2. Drop composite child FKs.
    remove_composite_child_fk(
        schema_editor,
        child_table=CRM_CONTACTNOTE_TABLE,
        constraint_name=CRM_CONTACTNOTE_CONTACT_ORG_FK,
    )
    remove_composite_child_fk(
        schema_editor,
        child_table=CRM_DEALNOTE_TABLE,
        constraint_name=CRM_DEALNOTE_DEAL_ORG_FK,
    )

    # 3. Drop parent unique constraints.
    remove_parent_unique_constraint(
        schema_editor,
        table=CRM_CONTACT_TABLE,
        constraint_name=CRM_CONTACT_ID_ORG_UNIQUE,
    )
    remove_parent_unique_constraint(
        schema_editor,
        table=CRM_DEAL_TABLE,
        constraint_name=CRM_DEAL_ID_ORG_UNIQUE,
    )


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
        # ---- Step 5: Add parent unique constraints, composite FKs, enable RLS ----
        migrations.RunPython(
            code=_install_composite_fks_and_rls,
            reverse_code=_uninstall_composite_fks_and_rls,
            hints={"target_db": "default"},
        ),
    ]
