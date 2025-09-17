"""Consolidated initial migration for users app.

This migration creates all user-related models in their final state:
- CustomUser: Custom user model with email authentication and profile fields
- AccountLockout: Account security and lockout management
- TwoFactorAuth: Two-factor authentication settings

Consolidates what was previously in 0001_initial.py and 0002_add_security_models.py
"""
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    """Consolidated initial migration for users app."""

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('username', models.CharField(blank=True, help_text='Optional. 150 characters or fewer. Letters, digits and @/./+/-/_ only.', max_length=150, null=True, verbose_name='username')),
                ('email', models.EmailField(error_messages={'unique': 'A user with that email already exists.'}, max_length=254, unique=True, verbose_name='email address')),
                ('bio', models.TextField(blank=True, verbose_name='bio')),
                ('phone_number', models.CharField(blank=True, max_length=20, verbose_name='phone number')),
                ('profile_picture', models.ImageField(blank=True, null=True, upload_to='profile_pictures', verbose_name='profile picture')),
                ('job_title', models.CharField(blank=True, max_length=100, verbose_name='job title')),
                ('company', models.CharField(blank=True, max_length=100, verbose_name='company')),
                ('website', models.URLField(blank=True, verbose_name='website')),
                ('location', models.CharField(blank=True, max_length=100, verbose_name='location')),
                ('twitter', models.CharField(blank=True, help_text='Twitter username', max_length=100, verbose_name='twitter')),
                ('linkedin', models.CharField(blank=True, help_text='LinkedIn username', max_length=100, verbose_name='linkedin')),
                ('github', models.CharField(blank=True, help_text='GitHub username', max_length=100, verbose_name='github')),
                ('email_notifications', models.BooleanField(default=True, verbose_name='email notifications')),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'User',
                'verbose_name_plural': 'Users',
                'app_label': 'users',
            },
        ),
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
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='lockout_status', to='users.customuser')),
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
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='two_factor_auth', to='users.customuser')),
            ],
            options={
                'verbose_name': 'Two-Factor Authentication',
                'verbose_name_plural': 'Two-Factor Authentication Settings',
                'app_label': 'users',
            },
        ),
    ]
