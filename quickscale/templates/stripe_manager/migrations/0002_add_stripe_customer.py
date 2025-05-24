# Generated migration for Sprint 4: Add StripeCustomer model for credit purchases

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('stripe_manager', '0001_initial'),
    ]

    operations = [
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
        migrations.AddIndex(
            model_name='stripecustomer',
            index=models.Index(fields=['stripe_id'], name='stripe_mana_stripe__74c94e_idx'),
        ),
        migrations.AddIndex(
            model_name='stripecustomer',
            index=models.Index(fields=['user'], name='stripe_mana_user_id_4a8b5c_idx'),
        ),
    ]
