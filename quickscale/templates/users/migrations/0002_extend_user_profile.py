"""Migration to extend the CustomUser model with profile fields."""
from django.db import migrations, models


class Migration(migrations.Migration):
    """Add profile fields to the CustomUser model."""

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20, verbose_name='phone number'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='profile_picture',
            field=models.ImageField(blank=True, null=True, upload_to='profile_pictures', verbose_name='profile picture'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='job_title',
            field=models.CharField(blank=True, max_length=100, verbose_name='job title'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='company',
            field=models.CharField(blank=True, max_length=100, verbose_name='company'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='website',
            field=models.URLField(blank=True, verbose_name='website'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='location',
            field=models.CharField(blank=True, max_length=100, verbose_name='location'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='twitter',
            field=models.CharField(blank=True, help_text='Twitter username', max_length=100, verbose_name='twitter'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='linkedin',
            field=models.CharField(blank=True, help_text='LinkedIn username', max_length=100, verbose_name='linkedin'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='github',
            field=models.CharField(blank=True, help_text='GitHub username', max_length=100, verbose_name='github'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='email_notifications',
            field=models.BooleanField(default=True, verbose_name='email notifications'),
        ),
    ] 