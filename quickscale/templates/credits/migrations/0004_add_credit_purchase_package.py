# Generated migration for Sprint 4: Add CreditPurchasePackage model for pay-as-you-go credit purchases

from django.db import migrations, models
import django.core.validators
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('credits', '0003_add_credit_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='CreditPurchasePackage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Package name (e.g., Basic Package)', max_length=100, verbose_name='name')),
                ('credit_amount', models.IntegerField(help_text='Number of credits in this package', validators=[django.core.validators.MinValueValidator(1)], verbose_name='credit amount')),
                ('price', models.DecimalField(decimal_places=2, help_text='Price in USD for this package', max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))], verbose_name='price')),
                ('currency', models.CharField(default='USD', help_text='Currency code (ISO 4217)', max_length=3, verbose_name='currency')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this package is currently available for purchase', verbose_name='is active')),
                ('display_order', models.IntegerField(default=0, help_text='Order in which to display this package', verbose_name='display order')),
                ('stripe_price_id', models.CharField(blank=True, help_text='Stripe price ID for this package', max_length=255, verbose_name='Stripe price ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
            ],
            options={
                'verbose_name': 'credit purchase package',
                'verbose_name_plural': 'credit purchase packages',
                'ordering': ['display_order', 'credit_amount'],
            },
        ),
    ]
