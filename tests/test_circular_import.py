"""Tests to prevent circular import regressions"""

import pytest


def test_forms_import_without_circular_dependency():
    """Test that forms can be imported without circular import

    Regression test for circular import between quickscale_modules_auth.forms
    and allauth.account.forms. This test should be run BEFORE Django is configured
    to catch import-time circular dependencies.
    """
    # This import should succeed without circular import errors
    try:
        from quickscale_modules_auth.forms import SignupForm

        # Verify form is usable
        assert SignupForm is not None
        form = SignupForm()
        assert hasattr(form, "signup")
    except ImportError as e:
        if "circular import" in str(e).lower():
            pytest.fail(f"Circular import detected: {e}")
        raise


@pytest.mark.django_db
def test_forms_allauth_integration():
    """Test that forms integrate correctly with allauth after Django setup

    This test runs after Django configuration to ensure the forms work
    correctly with allauth's form discovery mechanism.
    """
    from quickscale_modules_auth.forms import SignupForm

    # Create form instance
    form = SignupForm()

    # Verify allauth integration method exists
    assert hasattr(form, "signup"), "Form must have signup() method for allauth"
    assert callable(form.signup), "signup() must be callable"

    # Test that signup method accepts correct parameters
    import inspect

    sig = inspect.signature(form.signup)
    params = list(sig.parameters.keys())
    assert "request" in params, "signup() must accept 'request' parameter"
    assert "user" in params, "signup() must accept 'user' parameter"


def test_forms_do_not_import_allauth_forms():
    """Verify forms do NOT import from allauth.account.forms directly

    This prevents the circular import issue where allauth tries to load
    our custom form while initializing its own forms module.
    """
    import inspect
    from quickscale_modules_auth import forms

    # Get the source code of the forms module
    source = inspect.getsource(forms)

    # Check that we don't import from allauth.account.forms
    forbidden_imports = [
        "from allauth.account.forms import SignupForm",
        "from allauth.account.forms import LoginForm",
        "import allauth.account.forms",
    ]

    for forbidden in forbidden_imports:
        assert forbidden not in source, (
            f"Forms module should NOT contain: {forbidden}\n"
            f"This causes circular import with allauth. Use django.forms.Form instead."
        )
