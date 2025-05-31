# Generated migration for Sprint 10: AI Service Framework Foundation
# This migration documents the completion of the AI Service Framework
# The Service model and related infrastructure were already created in 0001_initial.py

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('credits', '0004_add_stripe_invoice_id'),
    ]

    operations = [
        # No database changes needed - Service model already exists with all required fields:
        # - name (CharField, unique)
        # - description (TextField) 
        # - credit_cost (DecimalField)
        # - is_active (BooleanField, default=True)
        # - created_at (DateTimeField, auto_now_add=True)
        # - updated_at (DateTimeField, auto_now=True)
        #
        # ServiceUsage model also exists with proper integration to CreditTransaction
        # Admin interface is fully implemented in credits/admin.py
        #
        # This migration serves as a marker for Sprint 10 completion
    ]