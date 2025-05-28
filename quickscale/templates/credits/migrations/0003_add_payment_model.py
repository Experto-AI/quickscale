# Generated migration for Sprint 8: Payment History & Receipts

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('credits', '0002_add_subscription_support'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add Payment model
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_payment_intent_id', models.CharField(blank=True, help_text='Stripe Payment Intent ID', max_length=255, null=True, verbose_name='stripe payment intent id')),
                ('stripe_subscription_id', models.CharField(blank=True, help_text='Stripe Subscription ID (for subscription payments)', max_length=255, null=True, verbose_name='stripe subscription id')),
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
        
        # Add indexes for Payment model
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['user'], name='credits_payment_user_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['stripe_payment_intent_id'], name='credits_payment_stripe_pi_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['stripe_subscription_id'], name='credits_payment_stripe_sub_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['status'], name='credits_payment_status_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['payment_type'], name='credits_payment_type_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['created_at'], name='credits_payment_created_at_idx'),
        ),
    ] 