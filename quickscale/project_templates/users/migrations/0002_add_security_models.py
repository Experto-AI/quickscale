# Generated migration for security enhancements

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountLockout',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('failed_attempts', models.IntegerField(default=0)),
                ('last_failed_attempt', models.DateTimeField(blank=True, null=True)),
                ('locked_until', models.DateTimeField(blank=True, null=True)),
                ('is_locked', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='lockout_status', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Account Lockout',
                'verbose_name_plural': 'Account Lockouts',
                'app_label': 'users',
            },
        ),
        migrations.CreateModel(
            name='TwoFactorAuth',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_enabled', models.BooleanField(default=False)),
                ('secret_key', models.CharField(blank=True, max_length=32)),
                ('backup_codes', models.JSONField(blank=True, default=list)),
                ('last_used', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='two_factor_auth', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Two-Factor Authentication',
                'verbose_name_plural': 'Two-Factor Authentication Settings',
                'app_label': 'users',
            },
        ),
    ] 