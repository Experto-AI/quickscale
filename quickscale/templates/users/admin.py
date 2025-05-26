"""Admin configuration for user accounts."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from allauth.account.models import EmailAddress

from .models import CustomUser


class EmailAddressInline(admin.TabularInline):
    """Inline admin for managing user email addresses."""
    model = EmailAddress
    extra = 0
    readonly_fields = ('verified', 'primary')
    fields = ('email', 'verified', 'primary')
    
    def has_add_permission(self, request, obj=None):
        """Limit email address creation to prevent conflicts."""
        return True
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion of email addresses."""
        return True


class CustomUserAdmin(UserAdmin):
    """Admin configuration for the custom user model with email management."""
    inlines = [EmailAddressInline]
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {
            'fields': ('first_name', 'last_name', 'bio', 'phone_number', 'profile_picture', 'job_title', 'company')
        }),
        (_('Contact & Social'), {
            'fields': ('website', 'location', 'twitter', 'linkedin', 'github'),
            'classes': ('collapse',)
        }),
        (_('Preferences'), {
            'fields': ('email_notifications',),
            'classes': ('collapse',)
        }),
        (
            _('Permissions'),
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                ),
            },
        ),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('email', 'password1', 'password2'),
            },
        ),
    )
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active', 'email_verified_status')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name', 'company', 'job_title')
    ordering = ('email',)
    
    def email_verified_status(self, obj):
        """Display email verification status."""
        try:
            email_address = EmailAddress.objects.get(user=obj, email=obj.email)
            return '✓ Verified' if email_address.verified else '✗ Unverified'
        except EmailAddress.DoesNotExist:
            return '? No record'
    email_verified_status.short_description = _('Email Status')


# Unregister the default EmailAddress admin from django-allauth
try:
    admin.site.unregister(EmailAddress)
except admin.sites.NotRegistered:
    # EmailAddress might not be registered yet, which is fine
    pass

# Register our enhanced user management admin
admin.site.register(CustomUser, CustomUserAdmin) 