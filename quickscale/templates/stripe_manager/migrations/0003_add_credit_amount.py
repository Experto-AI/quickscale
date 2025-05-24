# Generated migration for adding credit_amount field to StripeProduct

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stripe_manager', '0002_add_stripe_customer'),
    ]

    operations = [
        migrations.AddField(
            model_name='stripeproduct',
            name='credit_amount',
            field=models.IntegerField(
                default=1000,
                help_text='Number of credits provided by this product',
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name='Credit Amount'
            ),
        ),
    ]
