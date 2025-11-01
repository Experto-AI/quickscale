"""Tests for auth module forms"""

import pytest
from django.contrib.auth import get_user_model
from quickscale_modules_auth.forms import ProfileUpdateForm, SignupForm

User = get_user_model()


@pytest.mark.django_db
class TestProfileUpdateForm:
    """Tests for ProfileUpdateForm"""

    def test_form_valid_data(self, user):
        """Test form with valid data"""
        form = ProfileUpdateForm(
            {
                "first_name": "Updated",
                "last_name": "Name",
                "email": "newemail@example.com",
            },
            instance=user,
        )
        assert form.is_valid()

    def test_form_duplicate_email(self, user, db):
        """Test form rejects duplicate email"""
        User.objects.create_user(
            username="other", email="other@test.com", password="pass"
        )
        form = ProfileUpdateForm(
            {"first_name": "Test", "last_name": "User", "email": "other@test.com"},
            instance=user,
        )
        assert not form.is_valid()
        assert "email" in form.errors


@pytest.mark.django_db
class TestSignupForm:
    """Tests for SignupForm"""

    def test_form_initialization(self):
        """Test form can be initialized without circular import"""
        # This test ensures no circular import occurs during form instantiation
        form = SignupForm()
        assert form is not None

    def test_form_has_signup_method(self):
        """Test form has required signup method for allauth integration"""
        form = SignupForm()
        assert hasattr(form, "signup")
        assert callable(form.signup)
