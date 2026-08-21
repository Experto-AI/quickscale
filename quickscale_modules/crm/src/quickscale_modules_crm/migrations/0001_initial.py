"""Initial CRM schema with tenant composite-FK and FORCE-RLS contracts."""

from __future__ import annotations

from typing import Any

import django.db.models.deletion
import django.db.models.manager
from django.conf import settings
from django.db import migrations, models

from quickscale_modules_orgs.tenancy import (
    apply_force_rls,
    remove_composite_child_fk,
    revert_force_rls,
)

CRM_TAG_TABLE = "quickscale_modules_crm_tag"
CRM_COMPANY_TABLE = "quickscale_modules_crm_company"
CRM_CONTACT_TABLE = "quickscale_modules_crm_contact"
CRM_STAGE_TABLE = "quickscale_modules_crm_stage"
CRM_DEAL_TABLE = "quickscale_modules_crm_deal"
CRM_CONTACTNOTE_TABLE = "quickscale_modules_crm_contactnote"
CRM_DEALNOTE_TABLE = "quickscale_modules_crm_dealnote"

CRM_TAG_RLS_POLICY = "crm_tag_org_isolation"
CRM_COMPANY_RLS_POLICY = "crm_company_org_isolation"
CRM_CONTACT_RLS_POLICY = "crm_contact_org_isolation"
CRM_STAGE_RLS_POLICY = "crm_stage_org_isolation"
CRM_DEAL_RLS_POLICY = "crm_deal_org_isolation"
CRM_CONTACTNOTE_RLS_POLICY = "crm_contactnote_org_isolation"
CRM_DEALNOTE_RLS_POLICY = "crm_dealnote_org_isolation"

_CRM_CORE_RLS_TARGETS = (
    (CRM_TAG_TABLE, CRM_TAG_RLS_POLICY),
    (CRM_COMPANY_TABLE, CRM_COMPANY_RLS_POLICY),
    (CRM_CONTACT_TABLE, CRM_CONTACT_RLS_POLICY),
    (CRM_STAGE_TABLE, CRM_STAGE_RLS_POLICY),
    (CRM_DEAL_TABLE, CRM_DEAL_RLS_POLICY),
)
_CRM_NOTE_RLS_TARGETS = (
    (CRM_CONTACTNOTE_TABLE, CRM_CONTACTNOTE_RLS_POLICY),
    (CRM_DEALNOTE_TABLE, CRM_DEALNOTE_RLS_POLICY),
)

CRM_CONTACT_ID_ORG_UNIQUE = "crm_contact_id_org_unique"
CRM_DEAL_ID_ORG_UNIQUE = "crm_deal_id_org_unique"
CRM_CONTACTNOTE_CONTACT_ORG_FK = "crm_contactnote_contact_org_fk"
CRM_DEALNOTE_DEAL_ORG_FK = "crm_dealnote_deal_org_fk"


def _add_composite_fk(
    schema_editor: Any,
    child_table: str,
    constraint: str,
    child_fk_column: str,
    parent_table: str,
    on_delete: str,
) -> None:
    schema_editor.execute(
        f"ALTER TABLE {child_table} ADD CONSTRAINT {constraint} "
        f"FOREIGN KEY ({child_fk_column}, organization_id) "
        f"REFERENCES {parent_table}(id, organization_id) "
        f"ON DELETE {on_delete} NOT DEFERRABLE NOT VALID"
    )
    schema_editor.execute(f"ALTER TABLE {child_table} VALIDATE CONSTRAINT {constraint}")


def _forward_note_composite_fks_and_rls(apps: Any, schema_editor: Any) -> None:
    """Add composite child FKs and enable FORCE RLS for CRM tables."""
    del apps
    _add_composite_fk(
        schema_editor,
        CRM_CONTACTNOTE_TABLE,
        CRM_CONTACTNOTE_CONTACT_ORG_FK,
        "contact_id",
        CRM_CONTACT_TABLE,
        "CASCADE",
    )
    _add_composite_fk(
        schema_editor,
        CRM_DEALNOTE_TABLE,
        CRM_DEALNOTE_DEAL_ORG_FK,
        "deal_id",
        CRM_DEAL_TABLE,
        "CASCADE",
    )


def _reverse_note_composite_fks_and_rls(apps: Any, schema_editor: Any) -> None:
    """Reverse the CRM composite FKs."""
    del apps
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


def _forward_refresh_rls_nullif(apps: Any, schema_editor: Any) -> None:
    """Re-create CRM policies from the NULLIF-guarded template."""
    del apps
    targets = _CRM_CORE_RLS_TARGETS + _CRM_NOTE_RLS_TARGETS
    revert_force_rls(schema_editor, targets)
    apply_force_rls(schema_editor, targets)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("quickscale_modules_orgs", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Stage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "terminal_semantic",
                    models.CharField(
                        blank=True,
                        choices=[("won", "Won"), ("lost", "Lost")],
                        editable=False,
                        max_length=20,
                        null=True,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "name"],
                "abstract": False,
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="Company",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("industry", models.CharField(blank=True, max_length=100)),
                ("website", models.URLField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Companies",
                "ordering": ["name"],
                "abstract": False,
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="Contact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("first_name", models.CharField(max_length=100)),
                ("last_name", models.CharField(max_length=100)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, max_length=20)),
                (
                    "title",
                    models.CharField(blank=True, help_text="Job title", max_length=100),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("contacted", "Contacted"),
                            ("in_discussion", "In Discussion"),
                            ("pending_response", "Pending Response"),
                            ("inactive", "Inactive"),
                        ],
                        default="new",
                        max_length=50,
                    ),
                ),
                (
                    "last_contacted_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Automatically updated when a note is logged",
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contacts",
                        to="quickscale_modules_crm.company",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["last_name", "first_name"],
                "abstract": False,
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="ContactNote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "contact",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notes",
                        to="quickscale_modules_crm.contact",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "abstract": False,
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="Deal",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                (
                    "amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Deal value in USD",
                        max_digits=12,
                        null=True,
                    ),
                ),
                ("expected_close_date", models.DateField(blank=True, null=True)),
                (
                    "probability",
                    models.IntegerField(
                        default=50, help_text="Forecast likelihood (0-100%)"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "contact",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deals",
                        to="quickscale_modules_crm.contact",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="owned_deals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "stage",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="deals",
                        to="quickscale_modules_crm.stage",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "abstract": False,
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="DealNote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "deal",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notes",
                        to="quickscale_modules_crm.deal",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "abstract": False,
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="Tag",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "abstract": False,
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.AddField(
            model_name="deal",
            name="tags",
            field=models.ManyToManyField(
                blank=True, related_name="deals", to="quickscale_modules_crm.tag"
            ),
        ),
        migrations.AddField(
            model_name="contact",
            name="tags",
            field=models.ManyToManyField(
                blank=True, related_name="contacts", to="quickscale_modules_crm.tag"
            ),
        ),
        migrations.AddConstraint(
            model_name="stage",
            constraint=models.UniqueConstraint(
                condition=models.Q(("organization__isnull", True)),
                fields=("terminal_semantic",),
                name="crm_stage_terminal_semantic_unique_null_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="stage",
            constraint=models.UniqueConstraint(
                condition=models.Q(("organization__isnull", False)),
                fields=("terminal_semantic", "organization"),
                name="crm_stage_terminal_semantic_organization_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="tag",
            constraint=models.UniqueConstraint(
                condition=models.Q(("organization__isnull", True)),
                fields=("name",),
                name="crm_tag_name_unique_null_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="tag",
            constraint=models.UniqueConstraint(
                condition=models.Q(("organization__isnull", False)),
                fields=("name", "organization"),
                name="crm_tag_name_organization_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="deal",
            constraint=models.UniqueConstraint(
                fields=("id", "organization"), name="crm_deal_id_org_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="contact",
            constraint=models.UniqueConstraint(
                fields=("id", "organization"), name="crm_contact_id_org_unique"
            ),
        ),
        migrations.RunPython(
            code=_forward_note_composite_fks_and_rls,
            reverse_code=_reverse_note_composite_fks_and_rls,
            hints={"target_db": "default"},
        ),
        migrations.RunPython(
            code=_forward_refresh_rls_nullif,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
