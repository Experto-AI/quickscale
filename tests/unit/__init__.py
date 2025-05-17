"""QuickScale unit tests package."""
# Import Django setup to ensure proper configuration for all unit tests
import os
import django
import sys

# Configure Django settings before any tests are run
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.core.settings")

# Handle potential reentrant populate() errors
try:
    django.setup()
except RuntimeError as e:
    # If the error is about populate() being reentrant, it means Django is already set up
    if "populate() isn't reentrant" in str(e):
        # Django is already set up, which is fine
        pass
    else:
        # This is some other error, so we should re-raise it
        raise 