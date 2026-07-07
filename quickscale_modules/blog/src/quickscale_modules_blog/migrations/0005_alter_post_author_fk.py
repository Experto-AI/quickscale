"""SA35: Change Post.author on_delete from CASCADE to SET_NULL

Account deletion no longer cascade-destroys blog posts authored by the
deleted user.  Post.author was already nullable (null=True, blank=True),
so the migration only changes the on_delete rule.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_blog", "0004_tenant_model_inheritance"),
    ]

    operations = [
        migrations.AlterField(
            model_name="post",
            name="author",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="blog_posts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
