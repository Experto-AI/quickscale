"""Views for account management"""

from typing import Any

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.urls import reverse_lazy
from django.views.generic import DeleteView, DetailView, UpdateView

from quickscale_modules_auth.forms import ProfileUpdateForm

User = get_user_model()


class ProfileView(LoginRequiredMixin, DetailView):  # type: ignore[misc]
    """Display user profile"""

    model = User
    template_name = "quickscale_modules_auth/account/profile.html"
    context_object_name = "profile_user"

    def get_object(self, queryset: Any = None) -> Any:
        """Return the current user"""
        return self.request.user


class ProfileUpdateView(LoginRequiredMixin, UpdateView):  # type: ignore[misc]
    """Update user profile"""

    model = User
    form_class = ProfileUpdateForm
    template_name = "quickscale_modules_auth/account/profile_edit.html"
    success_url = reverse_lazy("quickscale_auth:profile")

    def get_object(self, queryset: Any = None) -> Any:
        """Return the current user"""
        return self.request.user

    def form_valid(self, form: Any) -> HttpResponse:
        """Add success message after profile update"""
        messages.success(self.request, "Your profile has been updated successfully.")
        return super().form_valid(form)


class AccountDeleteView(LoginRequiredMixin, DeleteView):  # type: ignore[misc]
    """Delete user account"""

    model = User
    template_name = "quickscale_modules_auth/account/account_delete.html"
    success_url = reverse_lazy("home")  # Redirect to home after deletion

    def get_object(self, queryset: Any = None) -> Any:
        """Return the current user"""
        return self.request.user

    def delete(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Add success message after account deletion"""
        messages.success(request, "Your account has been deleted successfully.")
        return super().delete(request, *args, **kwargs)
