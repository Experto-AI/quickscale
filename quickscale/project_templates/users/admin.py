"""Admin configuration for user accounts."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Q
from allauth.account.models import EmailAddress
from datetime import timedelta

from .models import CustomUser, AccountLockout, TwoFactorAuth


class LockoutStatusFilter(admin.SimpleListFilter):
    """Custom filter for account lockout status."""
    title = _('Lockout Status')
    parameter_name = 'lockout_status'
    
    def lookups(self, request, model_admin):
        return (
            ('active', _('Active (Not Locked)')),
            ('locked', _('Currently Locked')),
            ('expired', _('Expired Lockout')),
            ('recent', _('Recent Failed Attempts')),
        )
    
    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'active':
            return queryset.filter(Q(is_locked=False) | Q(locked_until__lt=now))
        if self.value() == 'locked':
            return queryset.filter(is_locked=True, locked_until__gt=now)
        if self.value() == 'expired':
            return queryset.filter(is_locked=True, locked_until__lt=now)
        if self.value() == 'recent':
            recent_time = now - timedelta(hours=24)
            return queryset.filter(last_failed_attempt__gte=recent_time)
        return queryset


class FailedAttemptsFilter(admin.SimpleListFilter):
    """Custom filter for failed attempts count."""
    title = _('Failed Attempts')
    parameter_name = 'failed_attempts'
    
    def lookups(self, request, model_admin):
        return (
            ('none', _('No Failed Attempts')),
            ('low', _('1-2 Attempts')),
            ('medium', _('3-4 Attempts')),
            ('high', _('5+ Attempts')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'none':
            return queryset.filter(failed_attempts=0)
        if self.value() == 'low':
            return queryset.filter(failed_attempts__in=[1, 2])
        if self.value() == 'medium':
            return queryset.filter(failed_attempts__in=[3, 4])
        if self.value() == 'high':
            return queryset.filter(failed_attempts__gte=5)
        return queryset


class TwoFactorStatusFilter(admin.SimpleListFilter):
    """Custom filter for two-factor authentication status."""
    title = _('2FA Status')
    parameter_name = '2fa_status'
    
    def lookups(self, request, model_admin):
        return (
            ('enabled', _('2FA Enabled')),
            ('disabled', _('2FA Disabled')),
            ('with_backups', _('Has Backup Codes')),
            ('without_backups', _('No Backup Codes')),
            ('recently_used', _('Used in Last 30 Days')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'enabled':
            return queryset.filter(is_enabled=True)
        if self.value() == 'disabled':
            return queryset.filter(is_enabled=False)
        if self.value() == 'with_backups':
            return queryset.exclude(backup_codes=[])
        if self.value() == 'without_backups':
            return queryset.filter(backup_codes=[])
        if self.value() == 'recently_used':
            recent_time = timezone.now() - timedelta(days=30)
            return queryset.filter(last_used__gte=recent_time)
        return queryset


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


@admin.register(AccountLockout)
class AccountLockoutAdmin(admin.ModelAdmin):
    """Enhanced admin interface for Account Lockout management."""
    list_display = (
        'user_link', 'lockout_status_display', 'failed_attempts_display', 
        'time_remaining_display', 'last_failed_attempt'
    )
    list_filter = (LockoutStatusFilter, FailedAttemptsFilter, 'created_at', 'updated_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'lockout_duration_display')
    ordering = ('-updated_at',)
    list_per_page = 25
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Lockout Status', {
            'fields': ('failed_attempts', 'is_locked', 'locked_until', 'last_failed_attempt')
        }),
        ('Duration Information', {
            'fields': ('lockout_duration_display',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'reset_lockout', 'unlock_accounts', 'force_lockout', 
        'reset_failed_attempts_only', 'bulk_unlock_expired'
    ]
    
    def user_link(self, obj):
        """Create a link to the user's admin page."""
        url = reverse('admin:users_customuser_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = _('User')
    user_link.admin_order_field = 'user__email'
    
    def lockout_status_display(self, obj):
        """Enhanced display of lockout status with visual indicators."""
        if not obj.is_locked:
            return format_html('<span style="color: green;">✓ Active</span>')
        
        if obj.locked_until and timezone.now() > obj.locked_until:
            return format_html('<span style="color: orange;">⚠ Expired</span>')
        
        return format_html('<span style="color: red;">🔒 Locked</span>')
    lockout_status_display.short_description = _('Status')
    
    def failed_attempts_display(self, obj):
        """Enhanced display of failed attempts with color coding."""
        attempts = obj.failed_attempts
        if attempts == 0:
            return format_html('<span style="color: green;">{}</span>', attempts)
        elif attempts < 3:
            return format_html('<span style="color: orange;">{}</span>', attempts)
        else:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', attempts)
    failed_attempts_display.short_description = _('Failed Attempts')
    failed_attempts_display.admin_order_field = 'failed_attempts'
    
    def time_remaining_display(self, obj):
        """Display time remaining until unlock."""
        if not obj.is_locked or not obj.locked_until:
            return '-'
        
        time_remaining = obj.time_until_unlock
        if not time_remaining:
            return format_html('<span style="color: orange;">Expired</span>')
        
        total_seconds = int(time_remaining.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f'{hours}h {minutes}m'
        elif minutes > 0:
            return f'{minutes}m {seconds}s'
        else:
            return f'{seconds}s'
    time_remaining_display.short_description = _('Time Remaining')
    
    def lockout_duration_display(self, obj):
        """Display total lockout duration in user-friendly format."""
        if obj.lockout_duration_minutes == 0:
            return 'N/A'
        
        minutes = obj.lockout_duration_minutes
        hours, mins = divmod(minutes, 60)
        
        if hours > 0:
            return f'{hours} hours, {mins} minutes'
        else:
            return f'{mins} minutes'
    lockout_duration_display.short_description = _('Lockout Duration')
    
    def reset_lockout(self, request, queryset):
        """Reset failed attempts and unlock accounts with logging."""
        from .security_logger import log_account_unlock
        
        count = 0
        for lockout in queryset:
            if lockout.is_locked or lockout.failed_attempts > 0:
                was_locked = lockout.is_locked
                lockout.reset_failed_attempts()
                count += 1
                
                # Log admin unlock action
                if was_locked:
                    log_account_unlock(
                        user_email=lockout.user.email,
                        user_id=lockout.user.id,
                        unlock_method='admin_reset'
                    )
        
        self.message_user(
            request, 
            f'{count} accounts unlocked and reset successfully.',
            level='SUCCESS' if count > 0 else 'INFO'
        )
    reset_lockout.short_description = "Reset lockout and unlock selected accounts"
    
    def unlock_accounts(self, request, queryset):
        """Unlock accounts without resetting failed attempts."""
        count = 0
        unlocked_users = []
        
        for lockout in queryset.filter(is_locked=True):
            lockout.is_locked = False
            lockout.locked_until = None
            lockout.save()
            unlocked_users.append(lockout.user.email)
            count += 1
        
        if count > 0:
            self.message_user(
                request, 
                f'{count} accounts unlocked successfully: {", ".join(unlocked_users[:5])}'
                + ("..." if len(unlocked_users) > 5 else ""),
                level='SUCCESS'
            )
        else:
            self.message_user(request, 'No locked accounts found in selection.', level='INFO')
    unlock_accounts.short_description = "Unlock selected accounts (keep failed attempts)"
    
    def force_lockout(self, request, queryset):
        """Force lockout for selected accounts (admin testing)."""
        count = 0
        for lockout in queryset.filter(is_locked=False):
            lockout.is_locked = True
            lockout.locked_until = timezone.now() + timedelta(minutes=5)
            lockout.failed_attempts = max(lockout.failed_attempts, 5)
            lockout.save()
            count += 1
        
        self.message_user(
            request, 
            f'{count} accounts locked for testing (5 minutes).',
            level='WARNING' if count > 0 else 'INFO'
        )
    force_lockout.short_description = "Force lockout for testing (5 minutes)"
    
    def reset_failed_attempts_only(self, request, queryset):
        """Reset only failed attempts without affecting lockout status."""
        count = queryset.exclude(failed_attempts=0).update(
            failed_attempts=0, 
            last_failed_attempt=None
        )
        self.message_user(
            request, 
            f'{count} accounts had their failed attempts reset.',
            level='SUCCESS' if count > 0 else 'INFO'
        )
    reset_failed_attempts_only.short_description = "Reset failed attempts only"
    
    def bulk_unlock_expired(self, request, queryset):
        """Unlock all accounts with expired lockouts."""
        now = timezone.now()
        expired_lockouts = queryset.filter(is_locked=True, locked_until__lt=now)
        
        count = 0
        for lockout in expired_lockouts:
            lockout.reset_failed_attempts()
            count += 1
        
        self.message_user(
            request, 
            f'{count} expired lockouts processed and unlocked.',
            level='SUCCESS' if count > 0 else 'INFO'
        )
    bulk_unlock_expired.short_description = "Unlock all expired lockouts"


@admin.register(TwoFactorAuth)
class TwoFactorAuthAdmin(admin.ModelAdmin):
    """Enhanced admin interface for Two-Factor Authentication management."""
    list_display = (
        'user_link', 'get_2fa_status_display', 'backup_codes_display', 
        'last_used_display', 'created_at'
    )
    list_filter = (TwoFactorStatusFilter, 'is_enabled', 'created_at', 'last_used')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('secret_key', 'backup_codes', 'created_at', 'updated_at', 'last_used', 'backup_codes_count')
    ordering = ('-updated_at',)
    list_per_page = 25
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('2FA Status', {
            'fields': ('is_enabled', 'last_used')
        }),
        ('Backup Codes Information', {
            'fields': ('backup_codes_count', 'backup_codes'),
            'classes': ('collapse',),
            'description': 'Backup codes for emergency access when 2FA device is unavailable'
        }),
        ('Configuration (Read-only)', {
            'fields': ('secret_key',),
            'classes': ('collapse',),
            'description': 'Secret key is managed through user interface for security'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['disable_2fa', 'enable_2fa', 'regenerate_backup_codes', 'clear_backup_codes']
    
    def user_link(self, obj):
        """Create a link to the user's admin page."""
        url = reverse('admin:users_customuser_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = _('User')
    user_link.admin_order_field = 'user__email'
    
    def get_2fa_status_display(self, obj):
        """Enhanced display of 2FA status with visual indicators."""
        if obj.is_enabled:
            if obj.backup_codes:
                return format_html('<span style="color: green;">✓ Enabled (with backups)</span>')
            else:
                return format_html('<span style="color: orange;">⚠ Enabled (no backups)</span>')
        else:
            return format_html('<span style="color: red;">✗ Disabled</span>')
    get_2fa_status_display.short_description = _('2FA Status')
    
    def backup_codes_display(self, obj):
        """Display backup codes count with visual indicators."""
        count = len(obj.backup_codes) if obj.backup_codes else 0
        
        if count == 0:
            return format_html('<span style="color: red;">None</span>')
        elif count < 3:
            return format_html('<span style="color: orange;">{} (Low)</span>', count)
        else:
            return format_html('<span style="color: green;">{}</span>', count)
    backup_codes_display.short_description = _('Backup Codes')
    
    def last_used_display(self, obj):
        """Display last used date with relative time."""
        if not obj.last_used:
            return format_html('<span style="color: gray;">Never</span>')
        
        now = timezone.now()
        time_diff = now - obj.last_used
        
        if time_diff.days > 30:
            return format_html('<span style="color: orange;">{} ({} days ago)</span>', 
                             obj.last_used.strftime('%Y-%m-%d'), time_diff.days)
        elif time_diff.days > 7:
            return format_html('<span style="color: green;">{} ({} days ago)</span>', 
                             obj.last_used.strftime('%Y-%m-%d'), time_diff.days)
        else:
            return format_html('<span style="color: green;">{} (Recent)</span>', 
                             obj.last_used.strftime('%Y-%m-%d'))
    last_used_display.short_description = _('Last Used')
    
    def backup_codes_count(self, obj):
        """Display count of backup codes."""
        return len(obj.backup_codes) if obj.backup_codes else 0
    backup_codes_count.short_description = _('Backup Codes Count')
    
    def has_backup_codes(self, obj):
        """Check if user has backup codes."""
        return bool(obj.backup_codes)
    has_backup_codes.boolean = True
    has_backup_codes.short_description = 'Has Backup Codes'
    
    def disable_2fa(self, request, queryset):
        """Disable 2FA for selected users with enhanced feedback."""
        count = 0
        disabled_users = []
        
        for two_factor in queryset.filter(is_enabled=True):
            two_factor.is_enabled = False
            two_factor.secret_key = ''
            two_factor.backup_codes = []
            two_factor.save()
            disabled_users.append(two_factor.user.email)
            count += 1
        
        if count > 0:
            self.message_user(
                request, 
                f'2FA disabled for {count} users: {", ".join(disabled_users[:5])}'
                + ("..." if len(disabled_users) > 5 else ""),
                level='SUCCESS'
            )
        else:
            self.message_user(request, 'No enabled 2FA accounts found in selection.', level='INFO')
    disable_2fa.short_description = "Disable 2FA for selected users"
    
    def enable_2fa(self, request, queryset):
        """Enable 2FA preparation for selected users."""
        count = 0
        enabled_users = []
        
        for two_factor in queryset.filter(is_enabled=False):
            # Only enable the flag, users must still set up their device
            two_factor.is_enabled = True
            two_factor.save()
            enabled_users.append(two_factor.user.email)
            count += 1
        
        if count > 0:
            self.message_user(
                request, 
                f'2FA enabled for {count} users (they must still configure their device): {", ".join(enabled_users[:5])}'
                + ("..." if len(enabled_users) > 5 else ""),
                level='SUCCESS'
            )
        else:
            self.message_user(request, 'No disabled 2FA accounts found in selection.', level='INFO')
    enable_2fa.short_description = "Enable 2FA for selected users"
    
    def regenerate_backup_codes(self, request, queryset):
        """Regenerate backup codes for selected users."""
        count = 0
        regenerated_users = []
        
        for two_factor in queryset:
            two_factor.generate_backup_codes(count=10)
            regenerated_users.append(two_factor.user.email)
            count += 1
        
        if count > 0:
            self.message_user(
                request, 
                f'Backup codes regenerated for {count} users: {", ".join(regenerated_users[:5])}'
                + ("..." if len(regenerated_users) > 5 else ""),
                level='SUCCESS'
            )
        else:
            self.message_user(request, 'No users found in selection.', level='INFO')
    regenerate_backup_codes.short_description = "Regenerate backup codes for selected users"
    
    def clear_backup_codes(self, request, queryset):
        """Clear backup codes for selected users."""
        count = queryset.exclude(backup_codes=[]).update(backup_codes=[])
        
        self.message_user(
            request, 
            f'Backup codes cleared for {count} users.',
            level='WARNING' if count > 0 else 'INFO'
        )
    clear_backup_codes.short_description = "Clear backup codes for selected users" 