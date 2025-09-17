"""Consolidated initial migration for credits app.

This migration creates all credit system models in their final state based on 
the current models.py file. This consolidates what was previously spread across
10 separate migration files into a single, clean initial migration.

Models created:
- Service: Services that consume credits
- UserSubscription: User subscription status and billing information
- CreditAccount: User credit account with balance management
- CreditTransaction: Individual credit transactions with full feature set
- ServiceUsage: Tracking of service usage by users
- Payment: Payment transaction tracking
- APIKey: API keys for authentication with secure hashing

Depends on users app for the CustomUser model.
"""
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Service model
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Name of the service', max_length=100, unique=True, verbose_name='name')),
                ('description', models.TextField(help_text='Description of what this service does', verbose_name='description')),
                ('credit_cost', models.DecimalField(decimal_places=2, help_text='Number of credits required to use this service (0.0 for free services)', max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.0'))], verbose_name='credit cost')),
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

        # UserSubscription model
        migrations.CreateModel(
            name='UserSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_subscription_id', models.CharField(blank=True, help_text='Stripe subscription ID', max_length=255, null=True, unique=True, verbose_name='stripe subscription id')),
                ('stripe_product_id', models.CharField(blank=True, help_text='Stripe product ID for this subscription', max_length=255, verbose_name='stripe product id')),
                ('status', models.CharField(choices=[('active', 'Active'), ('canceled', 'Canceled'), ('past_due', 'Past Due'), ('unpaid', 'Unpaid'), ('incomplete', 'Incomplete'), ('incomplete_expired', 'Incomplete Expired'), ('trialing', 'Trialing'), ('paused', 'Paused')], default='incomplete', help_text='Current subscription status', max_length=20, verbose_name='status')),
                ('current_period_start', models.DateTimeField(blank=True, help_text='Start of the current billing period', null=True, verbose_name='current period start')),
                ('current_period_end', models.DateTimeField(blank=True, help_text='End of the current billing period', null=True, verbose_name='current period end')),
                ('cancel_at_period_end', models.BooleanField(default=False, help_text='Whether the subscription will cancel at the end of the current period', verbose_name='cancel at period end')),
                ('canceled_at', models.DateTimeField(blank=True, help_text='When the subscription was canceled', null=True, verbose_name='canceled at')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='subscription', to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
            options={
                'verbose_name': 'user subscription',
                'verbose_name_plural': 'user subscriptions',
            },
        ),

        # CreditAccount model
        migrations.CreateModel(
            name='CreditAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subscription_credits', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Current subscription credit balance', max_digits=10, verbose_name='subscription credits')),
                ('payg_credits', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Current pay-as-you-go credit balance', max_digits=10, verbose_name='pay-as-you-go credits')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='credit_account', to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
            options={
                'verbose_name': 'credit account',
                'verbose_name_plural': 'credit accounts',
            },
        ),

        # CreditTransaction model (most complex)
        migrations.CreateModel(
            name='CreditTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, help_text='Credit amount (positive for additions, negative for consumption)', max_digits=10, verbose_name='amount')),
                ('description', models.CharField(help_text='Description of the transaction', max_length=255, verbose_name='description')),
                ('credit_type', models.CharField(choices=[('PAYG_PURCHASE', 'Pay-as-You-Go Purchase'), ('SUBSCRIPTION', 'Subscription'), ('SUBSCRIPTION_CONSUMPTION', 'Subscription Consumption'), ('PAYG_CONSUMPTION', 'Pay-as-You-Go Consumption'), ('ADMIN', 'Admin Adjustment')], default='ADMIN', help_text='Type of credit transaction', max_length=25, verbose_name='credit type')),
                ('transaction_type', models.CharField(blank=True, choices=[('addition', 'Credit Addition'), ('consumption', 'Credit Consumption'), ('allocation', 'Credit Allocation'), ('expiration', 'Credit Expiration'), ('adjustment', 'Admin Adjustment')], help_text='High-level transaction category for reporting', max_length=20, verbose_name='transaction type')),
                ('source', models.CharField(blank=True, help_text='Source of the transaction (stripe_payment, subscription_renewal, api_usage, admin_panel)', max_length=50, verbose_name='source')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional context (product ID, service used, etc.)', verbose_name='metadata')),
                ('expires_at', models.DateTimeField(blank=True, help_text='When these credits expire (for subscription credits)', null=True, verbose_name='expires at')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='credit_transactions', to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
            options={
                'verbose_name': 'credit transaction',
                'verbose_name_plural': 'credit transactions',
                'ordering': ['-created_at'],
            },
        ),

        # ServiceUsage model
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

        # Payment model
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_payment_intent_id', models.CharField(blank=True, help_text='Stripe Payment Intent ID', max_length=255, null=True, verbose_name='stripe payment intent id')),
                ('stripe_subscription_id', models.CharField(blank=True, help_text='Stripe Subscription ID (for subscription payments)', max_length=255, null=True, verbose_name='stripe subscription id')),
                ('stripe_invoice_id', models.CharField(blank=True, help_text='Stripe Invoice ID (for immediate charges like plan changes)', max_length=255, null=True, verbose_name='stripe invoice id')),
                ('amount', models.DecimalField(decimal_places=2, help_text='Payment amount in the specified currency', max_digits=10, verbose_name='amount')),
                ('currency', models.CharField(default='USD', help_text='Currency code (ISO 4217)', max_length=3, verbose_name='currency')),
                ('payment_type', models.CharField(choices=[('CREDIT_PURCHASE', 'Credit Purchase'), ('SUBSCRIPTION', 'Subscription'), ('REFUND', 'Refund')], help_text='Type of payment', max_length=20, verbose_name='payment type')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('succeeded', 'Succeeded'), ('failed', 'Failed'), ('refunded', 'Refunded'), ('cancelled', 'Cancelled')], default='pending', help_text='Payment status', max_length=20, verbose_name='status')),
                ('description', models.CharField(help_text='Payment description', max_length=255, verbose_name='description')),
                ('receipt_data', models.JSONField(blank=True, help_text='Receipt information in JSON format', null=True, verbose_name='receipt data')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to=settings.AUTH_USER_MODEL, verbose_name='user')),
                ('credit_transaction', models.ForeignKey(blank=True, help_text='Associated credit transaction (if applicable)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment', to='credits.credittransaction', verbose_name='credit transaction')),
                ('subscription', models.ForeignKey(blank=True, help_text='Associated subscription (if applicable)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payments', to='credits.usersubscription', verbose_name='subscription')),
            ],
            options={
                'verbose_name': 'payment',
                'verbose_name_plural': 'payments',
                'ordering': ['-created_at'],
            },
        ),

        # APIKey model
        migrations.CreateModel(
            name='APIKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, help_text='Optional name for this API key', max_length=100, verbose_name='name')),
                ('prefix', models.CharField(db_index=True, help_text='Short prefix for API key identification', max_length=8, verbose_name='prefix')),
                ('hashed_key', models.CharField(help_text='Hashed secret part of the API key', max_length=128, verbose_name='hashed key')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this API key is currently active', verbose_name='is active')),
                ('last_used_at', models.DateTimeField(blank=True, help_text='When this API key was last used', null=True, verbose_name='last used at')),
                ('expiry_date', models.DateTimeField(blank=True, help_text='Optional expiration date for this API key', null=True, verbose_name='expiry date')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='api_keys', to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
            options={
                'verbose_name': 'API key',
                'verbose_name_plural': 'API keys',
                'ordering': ['-created_at'],
            },
        ),

        # Add all indexes
        migrations.AddIndex(
            model_name='usersubscription',
            index=models.Index(fields=['stripe_subscription_id'], name='credits_use_stripe__0a5c47_idx'),
        ),
        migrations.AddIndex(
            model_name='usersubscription',
            index=models.Index(fields=['status'], name='credits_use_status_e89fb7_idx'),
        ),
        migrations.AddIndex(
            model_name='usersubscription',
            index=models.Index(fields=['current_period_end'], name='credits_use_current_2d7924_idx'),
        ),
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
            model_name='credittransaction',
            index=models.Index(fields=['expires_at'], name='credits_cre_expires_f8a1b3_idx'),
        ),
        migrations.AddIndex(
            model_name='credittransaction',
            index=models.Index(fields=['user', 'credit_type'], name='credits_cre_user_cr_9c2d84_idx'),
        ),
        migrations.AddIndex(
            model_name='credittransaction',
            index=models.Index(fields=['credit_type', 'expires_at'], name='credits_cre_credit_ex_7a5b92_idx'),
        ),
        migrations.AddIndex(
            model_name='serviceusage',
            index=models.Index(fields=['user', '-created_at'], name='credits_ser_user_id_f82c84_idx'),
        ),
        migrations.AddIndex(
            model_name='serviceusage',
            index=models.Index(fields=['service', '-created_at'], name='credits_ser_service_5b8f57_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['user', '-created_at'], name='credits_pay_user_id_5a7c24_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['status'], name='credits_pay_status_8f3b45_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['payment_type'], name='credits_pay_payment_9d4e12_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['stripe_payment_intent_id'], name='credits_pay_stripe__a8f5c3_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['-created_at'], name='credits_pay_created_7b9e81_idx'),
        ),
        migrations.AddIndex(
            model_name='apikey',
            index=models.Index(fields=['prefix'], name='credits_api_prefix_3e7a58_idx'),
        ),
        migrations.AddIndex(
            model_name='apikey',
            index=models.Index(fields=['user', 'is_active'], name='credits_api_user_id_6f4d92_idx'),
        ),
        migrations.AddIndex(
            model_name='apikey',
            index=models.Index(fields=['is_active', 'expiry_date'], name='credits_api_is_acti_1c9f47_idx'),
        ),

        # Add constraints
        migrations.AddConstraint(
            model_name='credittransaction',
            constraint=models.CheckConstraint(check=models.Q(('amount__gte', Decimal('-999999.99')), ('amount__lte', Decimal('999999.99'))), name='valid_amount_range'),
        ),
        migrations.AddConstraint(
            model_name='credittransaction',
            constraint=models.CheckConstraint(check=~(models.Q(credit_type='SUBSCRIPTION') & models.Q(expires_at__isnull=True)), name='subscription_credits_must_have_expiration'),
        ),
    ]
