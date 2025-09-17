"""Utilities to fix Django LiveServerTestCase for end-to-end testing."""



def patch_django_for_e2e_testing():
    """Apply critical patches to Django to fix bytes/string handling issues."""
    # Step 1: Patch the get_path_info function to ensure it returns strings
    from django.core.handlers.wsgi import get_path_info as original_get_path_info
    
    def fixed_get_path_info(environ):
        """Return the path info as a string, not bytes."""
        path = original_get_path_info(environ)
        if isinstance(path, bytes):
            path = path.decode('utf-8')
        return path
    
    # Apply the get_path_info patch to the Django module
    import django.core.handlers.wsgi
    django.core.handlers.wsgi.get_path_info = fixed_get_path_info
    print("✓ Patched django.core.handlers.wsgi.get_path_info to handle bytes")
    
    # Step 2: Find StaticFilesHandler which is used by LiveServerTestCase
    # and replace its _should_handle method with our fixed version
    try:
        from django.contrib.staticfiles.handlers import StaticFilesHandler
        
        # Create a new implementation that doesn't call the original method
        def fixed_should_handle(self, path):
            """New implementation that handles both string and bytes paths."""
            if isinstance(path, bytes):
                path = path.decode('utf-8')
                
            # Direct implementation of the method's logic without calling the original
            return path.startswith(self.base_url[2]) and not self.base_url[1]
        
        # Save the original method for debugging but don't call it
        # Replace the method with our fixed version
        StaticFilesHandler._should_handle = fixed_should_handle
        print("✓ Patched StaticFilesHandler._should_handle to handle bytes")
    except (ImportError, AttributeError) as e:
        print(f"! Could not patch StaticFilesHandler: {str(e)}")



# Pytest fixture to apply Django patches for e2e testing only when needed
import pytest


@pytest.fixture(scope="function")
def patch_django_for_e2e():
    patch_django_for_e2e_testing()
    yield
    # No unpatching logic here, as the patched methods are idempotent and do not use MagicMock
