"""Consolidated initial migration for credits app.

This migration creates all credit system models in their final state:
- CreditAccount: User credit account management
- CreditTransaction: Credit transaction ledger with credit_type field
- Service: Services that consume credits
- ServiceUsage: Tracking of service usage by users

Consolidated from multiple migrations for cleaner project generation.
"""
import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CreditAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='credit_account', to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
            options={
                'verbose_name': 'credit account',
                'verbose_name_plural': 'credit accounts',
            },
        ),
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Name of the service', max_length=100, unique=True, verbose_name='name')),
                ('description', models.TextField(help_text='Description of what this service does', verbose_name='description')),
                ('credit_cost', models.DecimalField(decimal_places=2, help_text='Number of credits required to use this service', max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))], verbose_name='credit cost')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this service is currently available for use', verbose_name='is active')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
            ],
            options={
                'verbose_name': 'service',
                'verbose_name_plural': 'services',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='CreditTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, help_text='Credit amount (positive for additions, negative for consumption)', max_digits=10, verbose_name='amount')),
                ('description', models.CharField(help_text='Description of the transaction', max_length=255, verbose_name='description')),
                ('credit_type', models.CharField(
                    choices=[('PURCHASE', 'Purchase'), ('CONSUMPTION', 'Consumption'), ('ADMIN', 'Admin Adjustment')],
                    default='ADMIN',
                    help_text='Type of credit transaction',
                    max_length=20,
                    verbose_name='credit type'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='credit_transactions', to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
            options={
                'verbose_name': 'credit transaction',
                'verbose_name_plural': 'credit transactions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ServiceUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('credit_transaction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='service_usage', to='credits.credittransaction', verbose_name='credit transaction')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usages', to='credits.service', verbose_name='service')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='service_usages', to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
            options={
                'verbose_name': 'service usage',
                'verbose_name_plural': 'service usages',
                'ordering': ['-created_at'],
            },
        ),
        # Add all indexes at once
        migrations.AddIndex(
            model_name='credittransaction',
            index=models.Index(fields=['user', '-created_at'], name='credits_cre_user_id_8bb1a8_idx'),
        ),
        migrations.AddIndex(
            model_name='credittransaction',
            index=models.Index(fields=['-created_at'], name='credits_cre_created_2e2f60_idx'),
        ),
        migrations.AddIndex(
            model_name='credittransaction',
            index=models.Index(fields=['credit_type'], name='credits_cre_credit__e8a7e2_idx'),
        ),
        migrations.AddIndex(
            model_name='serviceusage',
            index=models.Index(fields=['user', '-created_at'], name='credits_ser_user_id_f82c84_idx'),
        ),
        migrations.AddIndex(
            model_name='serviceusage',
            index=models.Index(fields=['service', '-created_at'], name='credits_ser_service_5b8f57_idx'),
        ),
    ] 