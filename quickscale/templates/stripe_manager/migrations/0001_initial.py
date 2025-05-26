"""Consolidated initial migration for stripe_manager app.

This migration creates all Stripe integration models in their final state:
- StripeProduct: Stripe products with credit amounts and pricing
- StripeCustomer: Links Django users to Stripe customers

Consolidated from multiple migrations for cleaner project generation.
"""
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
        migrations.CreateModel(
            name='StripeProduct',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Product name as shown to customers', max_length=255, verbose_name='Name')),
                ('description', models.TextField(blank=True, help_text='Product description', verbose_name='Description')),
                ('active', models.BooleanField(default=True, help_text='Whether this product is available for purchase', verbose_name='Active')),
                ('price', models.DecimalField(decimal_places=2, help_text='Product price', max_digits=10, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Price')),
                ('currency', models.CharField(default='USD', help_text='Price currency (ISO 4217 code)', max_length=3, verbose_name='Currency')),
                ('interval', models.CharField(choices=[('month', 'Monthly'), ('year', 'Yearly'), ('one-time', 'One Time')], default='month', help_text='Billing interval for subscription products', max_length=20, verbose_name='Billing Interval')),
                ('credit_amount', models.IntegerField(
                    default=1000,
                    help_text='Number of credits provided by this product',
                    validators=[django.core.validators.MinValueValidator(1)],
                    verbose_name='Credit Amount'
                )),
                ('display_order', models.IntegerField(default=0, help_text='Order in which to display this product', verbose_name='Display Order')),
                ('stripe_id', models.CharField(help_text='Stripe product ID', max_length=255, unique=True, verbose_name='Stripe ID')),
                ('stripe_price_id', models.CharField(blank=True, default='', help_text='Stripe price ID', max_length=255, verbose_name='Stripe Price ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
            ],
            options={
                'verbose_name': 'Stripe Product',
                'verbose_name_plural': 'Stripe Products',
                'ordering': ['display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='StripeCustomer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_id', models.CharField(blank=True, help_text='Stripe customer ID', max_length=255, unique=True, verbose_name='Stripe Customer ID')),
                ('email', models.EmailField(help_text='Email address used in Stripe', max_length=254, verbose_name='Email')),
                ('name', models.CharField(blank=True, help_text='Customer name in Stripe', max_length=255, verbose_name='Name')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='stripe_customer', to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'Stripe Customer',
                'verbose_name_plural': 'Stripe Customers',
            },
        ),
        # Add all indexes at once
        migrations.AddIndex(
            model_name='stripeproduct',
            index=models.Index(fields=['stripe_id'], name='stripe_mana_stripe__9f5fe4_idx'),
        ),
        migrations.AddIndex(
            model_name='stripeproduct',
            index=models.Index(fields=['active'], name='stripe_mana_active_4a0768_idx'),
        ),
        migrations.AddIndex(
            model_name='stripeproduct',
            index=models.Index(fields=['display_order'], name='stripe_mana_display_da36ef_idx'),
        ),
        migrations.AddIndex(
            model_name='stripecustomer',
            index=models.Index(fields=['stripe_id'], name='stripe_mana_stripe__74c94e_idx'),
        ),
        migrations.AddIndex(
            model_name='stripecustomer',
            index=models.Index(fields=['user'], name='stripe_mana_user_id_4a8b5c_idx'),
        ),
    ] 