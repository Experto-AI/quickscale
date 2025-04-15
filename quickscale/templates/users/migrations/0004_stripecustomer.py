"""Migration to create the StripeCustomer model."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Create the StripeCustomer model linked to CustomUser."""

    dependencies = [
        ('users', '0003_alter_customuser_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='StripeCustomer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_id', models.CharField(help_text='Stripe customer identifier', max_length=255, verbose_name='stripe customer ID')),
                ('created', models.DateTimeField(auto_now_add=True, help_text='Date and time when the customer was created', verbose_name='created')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='stripe_customer', to='users.customuser', verbose_name='user')),
            ],
            options={
                'verbose_name': 'stripe customer',
                'verbose_name_plural': 'stripe customers',
            },
        ),
    ] 