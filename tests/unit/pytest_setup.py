"""Setup Django environment for unit tests."""
import os
import django

# Configure Django settings before any tests are run
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.core.settings")
django.setup()
