# Generated migration to add credit_type field to CreditTransaction

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('credits', '0002_add_services'),
    ]

    operations = [
        migrations.AddField(
            model_name='credittransaction',
            name='credit_type',
            field=models.CharField(
                choices=[('PURCHASE', 'Purchase'), ('CONSUMPTION', 'Consumption'), ('ADMIN', 'Admin Adjustment')],
                default='ADMIN',
                help_text='Type of credit transaction',
                max_length=20,
                verbose_name='credit type'
            ),
        ),
        migrations.AddIndex(
            model_name='credittransaction',
            index=models.Index(fields=['credit_type'], name='credits_cre_credit__e8a7e2_idx'),
        ),
    ]
