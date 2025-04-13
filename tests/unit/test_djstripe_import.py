"""Test dj-stripe package import."""
import pytest

def test_djstripe_import():
    """Verify that dj-stripe can be imported."""
    try:
        import djstripe
        assert djstripe is not None
    except ImportError as e:
        pytest.fail(f"Failed to import djstripe: {str(e)}")

def test_stripe_import():
    """Verify that stripe can be imported."""
    try:
        import stripe
        assert stripe is not None
    except ImportError as e:
        pytest.fail(f"Failed to import stripe: {str(e)}")