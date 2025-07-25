# Generated migration for Sprint 6: Basic Monthly Subscription

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('credits', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add UserSubscription model
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
        
        # Add SUBSCRIPTION to credit type choices
        migrations.AlterField(
            model_name='credittransaction',
            name='credit_type',
            field=models.CharField(choices=[('PURCHASE', 'Purchase'), ('SUBSCRIPTION', 'Subscription'), ('CONSUMPTION', 'Consumption'), ('ADMIN', 'Admin Adjustment')], default='ADMIN', help_text='Type of credit transaction', max_length=20, verbose_name='credit type'),
        ),
        
        # Add expires_at field to CreditTransaction
        migrations.AddField(
            model_name='credittransaction',
            name='expires_at',
            field=models.DateTimeField(blank=True, help_text='When these credits expire (for subscription credits)', null=True, verbose_name='expires at'),
        ),
        
        # Add indexes for UserSubscription
        migrations.AddIndex(
            model_name='usersubscription',
            index=models.Index(fields=['stripe_subscription_id'], name='credits_usersubscription_stripe_sub_idx'),
        ),
        migrations.AddIndex(
            model_name='usersubscription',
            index=models.Index(fields=['status'], name='credits_usersubscription_status_idx'),
        ),
        migrations.AddIndex(
            model_name='usersubscription',
            index=models.Index(fields=['current_period_end'], name='credits_usersubscription_period_end_idx'),
        ),
        
        # Add index for expires_at field
        migrations.AddIndex(
            model_name='credittransaction',
            index=models.Index(fields=['expires_at'], name='credits_credittransaction_expires_at_idx'),
        ),
    ] 