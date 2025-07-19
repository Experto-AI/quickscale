# Generated migration for Sprint 24: AI API Consumption with Zero-Cost Services
# This migration removes the minimum credit cost validation to allow 0.0 credit costs

from django.db import migrations, models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('credits', '0007_add_text_processing_service'),
    ]

    operations = [
        migrations.AlterField(
            model_name='service',
            name='credit_cost',
            field=models.DecimalField(
                decimal_places=2,
                help_text='Number of credits required to use this service (0.0 for free services)',
                max_digits=10,
                validators=[MinValueValidator(Decimal('0.0'))],
                verbose_name='credit cost'
            ),
        ),
    ]