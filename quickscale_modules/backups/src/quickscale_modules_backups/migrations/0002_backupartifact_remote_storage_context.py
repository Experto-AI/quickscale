from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_backups", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="backupartifact",
            name="remote_bucket_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="backupartifact",
            name="remote_endpoint_url",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="backupartifact",
            name="remote_region_name",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
