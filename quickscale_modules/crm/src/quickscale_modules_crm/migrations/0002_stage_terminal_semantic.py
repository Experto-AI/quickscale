"""Add hidden stage terminal semantics and backfill canonical defaults."""

from django.db import migrations, models
from django.db.models import Count


WON_TERMINAL_SEMANTIC = "won"
LOST_TERMINAL_SEMANTIC = "lost"
TERMINAL_STAGE_NAME_TO_SEMANTIC = {
    "Closed-Won": WON_TERMINAL_SEMANTIC,
    "Closed-Lost": LOST_TERMINAL_SEMANTIC,
}


def backfill_terminal_stage_semantics(apps, _schema_editor):
    """Tag canonical exact-name terminal stages without mutating duplicates."""
    Stage = apps.get_model("quickscale_modules_crm", "Stage")

    Stage.objects.filter(terminal_semantic__isnull=False).update(terminal_semantic=None)

    for stage_name, semantic in TERMINAL_STAGE_NAME_TO_SEMANTIC.items():
        canonical_stage = (
            Stage.objects.filter(name=stage_name)
            .annotate(linked_deal_count=Count("deals"))
            .order_by("-linked_deal_count", "order", "id")
            .first()
        )
        if canonical_stage is None:
            continue

        Stage.objects.filter(name=stage_name).exclude(pk=canonical_stage.pk).update(
            terminal_semantic=None
        )
        Stage.objects.filter(pk=canonical_stage.pk).update(terminal_semantic=semantic)


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_crm", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="stage",
            name="terminal_semantic",
            field=models.CharField(
                blank=True,
                choices=[("won", "Won"), ("lost", "Lost")],
                editable=False,
                max_length=20,
                null=True,
            ),
        ),
        migrations.RunPython(
            backfill_terminal_stage_semantics,
            migrations.RunPython.noop,
        ),
    ]
