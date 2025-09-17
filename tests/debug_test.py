"""Debug script to help diagnose test failures."""
import os
import sys

# Import centralized test utilities using DRY principles
from tests.test_utilities import TestUtilities

# Add the parent directory to sys.path to access tests module
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

def validate_production_settings():
    """The validate_production_settings function to debug."""
    print("DEBUG: Called validate_production_settings")
    print(f"DEBUG: os.environ = {os.environ}")
    # Use IS_PRODUCTION (opposite of old DEBUG logic)
    if TestUtilities.is_feature_enabled(TestUtilities.TestUtilities.get_env('IS_PRODUCTION', 'False')):
        print("DEBUG: IS_PRODUCTION is True, checking settings")
        if TestUtilities.TestUtilities.get_env('SECRET_KEY') == 'dev-only-dummy-key-replace-in-production':
            print("DEBUG: Insecure SECRET_KEY detected")
            raise ValueError("Production requires a secure SECRET_KEY")
        if '*' in TestUtilities.TestUtilities.get_env('ALLOWED_HOSTS', '').split(','):
            print("DEBUG: Wildcard in ALLOWED_HOSTS detected")
            raise ValueError("Production requires specific ALLOWED_HOSTS")
        # Check database settings
        if TestUtilities.TestUtilities.get_env('DB_PASSWORD') in ['postgres', 'admin', 'adminpasswd', 'password']:
            print(f"DEBUG: Insecure DB_PASSWORD detected: {TestUtilities.TestUtilities.get_env('DB_PASSWORD')}")
            raise ValueError("Production requires a secure database password")
        # Check email settings
        if not TestUtilities.is_feature_enabled(TestUtilities.TestUtilities.get_env('EMAIL_USE_TLS', 'True')):
            print(f"DEBUG: EMAIL_USE_TLS is not True: {TestUtilities.TestUtilities.get_env('EMAIL_USE_TLS')}")
            raise ValueError("Production requires TLS for email")
    else:
        print("DEBUG: IS_PRODUCTION is False, skipping validation")

def test_secret_key():
    """Test SECRET_KEY validation."""
    print("\nTesting SECRET_KEY validation")
    try:
        os.environ.clear()
        os.environ['DEBUG'] = 'False'
        os.environ['SECRET_KEY'] = 'dev-only-dummy-key-replace-in-production'
        validate_production_settings()
        print("ERROR: No exception was raised for insecure SECRET_KEY")
    except ValueError as e:
        print(f"SUCCESS: Caught expected ValueError: {e}")

def test_allowed_hosts():
    """Test ALLOWED_HOSTS validation."""
    print("\nTesting ALLOWED_HOSTS validation")
    try:
        os.environ.clear()
        os.environ['DEBUG'] = 'False'
        os.environ['SECRET_KEY'] = 'secure-key'
        os.environ['ALLOWED_HOSTS'] = '*'
        validate_production_settings()
        print("ERROR: No exception was raised for wildcard ALLOWED_HOSTS")
    except ValueError as e:
        print(f"SUCCESS: Caught expected ValueError: {e}")

def test_db_password():
    """Test DB_PASSWORD validation."""
    print("\nTesting DB_PASSWORD validation")
    try:
        os.environ.clear()
        os.environ['DEBUG'] = 'False'
        os.environ['SECRET_KEY'] = 'secure-key'
        os.environ['ALLOWED_HOSTS'] = 'example.com'
        os.environ['DB_PASSWORD'] = 'adminpasswd'
        validate_production_settings()
        print("ERROR: No exception was raised for insecure DB_PASSWORD")
    except ValueError as e:
        print(f"SUCCESS: Caught expected ValueError: {e}")

def test_email_tls():
    """Test EMAIL_USE_TLS validation."""
    print("\nTesting EMAIL_USE_TLS validation")
    try:
        os.environ.clear()
        os.environ['DEBUG'] = 'False'
        os.environ['SECRET_KEY'] = 'secure-key'
        os.environ['ALLOWED_HOSTS'] = 'example.com'
        os.environ['DB_PASSWORD'] = 'secure-password'
        os.environ['EMAIL_USE_TLS'] = 'False'
        validate_production_settings()
        print("ERROR: No exception was raised for EMAIL_USE_TLS=False")
    except ValueError as e:
        print(f"SUCCESS: Caught expected ValueError: {e}")

if __name__ == "__main__":
    # Save original environment
    orig_env = os.environ.copy()
    
    try:
        test_secret_key()
        test_allowed_hosts()
        test_db_password()
        test_email_tls()
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(orig_env)
