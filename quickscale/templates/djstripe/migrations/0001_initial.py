"""
Initial migration for the djstripe app's custom models.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Initial migration for the djstripe app custom models.
    """
    
    initial = True
    
    dependencies = [
    ]
    
    operations = [
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Product name', max_length=255, verbose_name='name')),
                ('description', models.TextField(blank=True, help_text='Detailed product description', verbose_name='description')),
                ('image', models.ImageField(blank=True, help_text='Product image', null=True, upload_to='product_images', verbose_name='image')),
                ('base_price', models.DecimalField(decimal_places=2, help_text='Base price of the product', max_digits=10, verbose_name='base price')),
                ('currency', models.CharField(default='USD', help_text='Three-letter currency code (e.g., USD, EUR)', max_length=3, verbose_name='currency')),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active', help_text='Product availability status', max_length=10, verbose_name='status')),
                ('created', models.DateTimeField(auto_now_add=True, help_text='Date and time when the product was created', verbose_name='created')),
                ('updated', models.DateTimeField(auto_now=True, help_text='Date and time when the product was last updated', verbose_name='updated')),
                ('stripe_product_id', models.CharField(blank=True, help_text='Associated Stripe product identifier, if applicable', max_length=255, null=True, verbose_name='stripe product ID')),
                ('metadata', models.JSONField(blank=True, help_text='Additional product metadata stored as JSON', null=True, verbose_name='metadata')),
            ],
            options={
                'verbose_name': 'product',
                'verbose_name_plural': 'products',
                'ordering': ['-created'],
            },
        ),
    ] 