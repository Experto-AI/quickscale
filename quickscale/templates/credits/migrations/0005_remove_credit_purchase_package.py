# Generated migration to remove CreditPurchasePackage model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('credits', '0004_add_credit_purchase_package'),
    ]

    operations = [
        migrations.DeleteModel(
            name='CreditPurchasePackage',
        ),
    ] 