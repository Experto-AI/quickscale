"""Canonicalize duplicate terminal semantics before enforcing uniqueness."""

from django.db import migrations, models
from django.db.models import Count


def deduplicate_terminal_stage_semantics(apps, _schema_editor):
    """Keep one stage per terminal semantic before the unique constraint lands."""
    Stage = apps.get_model("quickscale_modules_crm", "Stage")

    semantics = (
        Stage.objects.exclude(terminal_semantic__isnull=True)
        .values_list("terminal_semantic", flat=True)
        .distinct()
    )
    for semantic in semantics:
        canonical_stage = (
            Stage.objects.filter(terminal_semantic=semantic)
            .annotate(linked_deal_count=Count("deals"))
            .order_by("-linked_deal_count", "order", "id")
            .first()
        )
        if canonical_stage is None:
            continue

        Stage.objects.filter(terminal_semantic=semantic).exclude(
            pk=canonical_stage.pk
        ).update(terminal_semantic=None)


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_crm", "0002_stage_terminal_semantic"),
    ]

    operations = [
        migrations.RunPython(
            deduplicate_terminal_stage_semantics,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="stage",
            name="terminal_semantic",
            field=models.CharField(
                blank=True,
                choices=[("won", "Won"), ("lost", "Lost")],
                editable=False,
                max_length=20,
                null=True,
                unique=True,
            ),
        ),
    ]
