"""Profile views for the QuickScale auth module.

Module Conventions rule 28: ``quickscale_modules_auth.views`` re-exports
these classes, so the public view surface and every existing import path
stay unchanged.
"""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import DetailView, UpdateView

from quickscale_modules_auth.forms import ProfileUpdateForm

User = get_user_model()


class ProfileView(LoginRequiredMixin, DetailView):
    """Display user profile"""

    model = User
    template_name = "quickscale_auth/account/profile.html"
    context_object_name = "profile_user"

    def get_object(self, queryset: Any = None) -> Any:
        """Return the current user"""
        return self.request.user


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Update user profile"""

    model = User
    form_class = ProfileUpdateForm
    template_name = "quickscale_auth/account/profile_edit.html"
    success_url = reverse_lazy("quickscale_auth:profile")

    def get_object(self, queryset: Any = None) -> Any:
        """Return the current user"""
        return self.request.user

    def form_valid(self, form: Any) -> HttpResponse:
        """Add success message after profile update"""
        messages.success(self.request, "Your profile has been updated successfully.")
        return super().form_valid(form)
