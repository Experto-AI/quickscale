"""Custom forms for authentication"""

from typing import Any

from allauth.account.forms import LoginForm as AllauthLoginForm  # type: ignore[import-untyped]
from allauth.account.forms import SignupForm as AllauthSignupForm  # type: ignore[import-untyped]
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm

User = get_user_model()


class SignupForm(AllauthSignupForm):  # type: ignore[misc]
    """Custom signup form extending django-allauth SignupForm"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Add custom CSS classes for styling
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"

    def clean_email(self) -> str:
        """Validate and normalize email"""
        email = self.cleaned_data.get("email", "")
        if email:
            email = email.lower().strip()
        return str(email)


class LoginForm(AllauthLoginForm):  # type: ignore[misc]
    """Custom login form extending django-allauth LoginForm"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Add custom CSS classes for styling
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"


class PasswordChangeForm(DjangoPasswordChangeForm):
    """Custom password change form with validation"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Add custom CSS classes for styling
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"


class ProfileUpdateForm(forms.ModelForm):
    """Form for updating user profile information"""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }

    def clean_email(self) -> str:
        """Validate email uniqueness"""
        email = self.cleaned_data.get("email", "")
        if email:
            email = email.lower().strip()
            # Check if email is already taken by another user
            existing_user = (
                User.objects.filter(email=email).exclude(pk=self.instance.pk).first()
            )
            if existing_user:
                raise forms.ValidationError("This email address is already in use.")
        return str(email)
