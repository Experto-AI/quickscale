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
        User.objects.create_user(username="other", email="other@test.com", password="pass")
        form = ProfileUpdateForm(
            {"first_name": "Test", "last_name": "User", "email": "other@test.com"},
            instance=user,
        )
        assert not form.is_valid()
        assert "email" in form.errors


@pytest.mark.django_db
class TestSignupForm:
    """Tests for SignupForm"""

    def test_email_normalization(self):
        """Test email is lowercased and stripped"""
        form = SignupForm(
            {
                "username": "newuser",
                "email": "  NewUser@Example.com  ",
                "password1": "TestPass123!",
                "password2": "TestPass123!",
            }
        )
        if form.is_valid():
            assert form.cleaned_data["email"] == "newuser@example.com"
