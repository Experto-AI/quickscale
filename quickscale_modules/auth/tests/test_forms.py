"""Tests for auth module forms"""

import pytest
from django import forms
from quickscale_modules_auth.forms import (
    PasswordChangeForm,
    ProfileUpdateForm,
    SignupForm,
)


@pytest.mark.django_db
class TestProfileUpdateForm:
    """Tests for ProfileUpdateForm"""

    def test_form_valid_data(self, user):
        """Test form with valid name data"""
        form = ProfileUpdateForm(
            {"first_name": "Updated", "last_name": "Name"},
            instance=user,
        )
        assert form.is_valid()
        updated = form.save()
        assert updated.first_name == "Updated"
        assert updated.last_name == "Name"

    def test_form_excludes_email(self, user):
        """The account address is owned by django-allauth's email flow."""
        form = ProfileUpdateForm(instance=user)
        assert "email" not in form.fields

    def test_form_ignores_a_submitted_email(self, user):
        """A submitted email cannot bypass the allauth address flow."""
        form = ProfileUpdateForm(
            {
                "first_name": "Test",
                "last_name": "User",
                "email": "replacement@example.com",
            },
            instance=user,
        )
        assert form.is_valid()
        updated = form.save()
        assert updated.email == user.email


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

    def test_signup_hook_accepts_the_allauth_call(self):
        """The post-signup hook is a no-op the allauth integration can call."""
        form = SignupForm()
        assert form.signup(None, None) is None

    def test_form_styles_every_declared_field(self):
        """A subclass's fields receive the shared form-control class."""

        class FieldedSignupForm(SignupForm):
            nickname = forms.CharField()

        form = FieldedSignupForm()
        assert form.fields["nickname"].widget.attrs["class"] == "form-control"


@pytest.mark.django_db
class TestPasswordChangeForm:
    """Tests for PasswordChangeForm"""

    def test_form_styles_every_field(self, user):
        """Every password field receives the shared form-control class."""
        form = PasswordChangeForm(user=user)
        assert form.fields
        assert all(
            field.widget.attrs["class"] == "form-control"
            for field in form.fields.values()
        )
