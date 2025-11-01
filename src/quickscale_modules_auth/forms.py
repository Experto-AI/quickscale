"""Custom forms for authentication"""

from typing import Any

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm

User = get_user_model()


class SignupForm(forms.Form):
    """Custom signup form for django-allauth integration

    WARNING: Do NOT inherit from allauth.account.forms.SignupForm directly.
    This causes a circular import because allauth loads this form during initialization
    before its own forms module is fully loaded.

    Instead, define form fields directly and let allauth handle the integration.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Add custom CSS classes for styling
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"

    def signup(self, request: Any, user: Any) -> None:
        """Called by allauth after user creation"""
        # Add any custom post-signup logic here
        pass


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
