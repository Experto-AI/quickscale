# Generated migration for Sprint 9: Add stripe_invoice_id field to Payment model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('credits', '0003_add_payment_model'),
    ]

    operations = [
        # Add stripe_invoice_id field to Payment model
        migrations.AddField(
            model_name='payment',
            name='stripe_invoice_id',
            field=models.CharField(blank=True, help_text='Stripe Invoice ID (for immediate charges like plan changes)', max_length=255, null=True, verbose_name='stripe invoice id'),
        ),
        
        # Add index for stripe_invoice_id field
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['stripe_invoice_id'], name='credits_payment_stripe_inv_idx'),
        ),
    ] 