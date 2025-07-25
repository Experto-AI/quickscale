"""Custom user model for email-only authentication."""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta


class CustomUserManager(BaseUserManager):
    """Custom user manager for email-only authentication without username."""

    def create_user(self, email=None, password=None, **extra_fields):
        """Create and save a user with the given email and password."""
        if not email:
            raise ValueError(_('The Email field must be set'))
        email = self.normalize_email(email)
        # Make username optional and set to empty string if not provided
        extra_fields.setdefault('username', extra_fields.get('username', ''))
        user = self.model(email=email, **extra_fields)
        
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
            
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    """Custom user model for email-only authentication."""
    
    # Set username to null since we're using email for authentication
    username = models.CharField(
        _('username'),
        max_length=150,
        blank=True,
        null=True,
        help_text=_('Optional. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
    )
    
    # Make email required and unique
    email = models.EmailField(
        _('email address'), 
        unique=True,
        error_messages={
            'unique': _('A user with that email already exists.'),
        },
    )
    
    # Additional profile fields
    bio = models.TextField(_('bio'), blank=True)
    phone_number = models.CharField(_('phone number'), max_length=20, blank=True)
    profile_picture = models.ImageField(_('profile picture'), upload_to='profile_pictures', blank=True, null=True)
    job_title = models.CharField(_('job title'), max_length=100, blank=True)
    company = models.CharField(_('company'), max_length=100, blank=True)
    website = models.URLField(_('website'), blank=True)
    location = models.CharField(_('location'), max_length=100, blank=True)
    
    # Social media profiles
    twitter = models.CharField(_('twitter'), max_length=100, blank=True, help_text=_('Twitter username'))
    linkedin = models.CharField(_('linkedin'), max_length=100, blank=True, help_text=_('LinkedIn username'))
    github = models.CharField(_('github'), max_length=100, blank=True, help_text=_('GitHub username'))
    
    # Notification preferences
    email_notifications = models.BooleanField(_('email notifications'), default=True)
    
    # Set email as the USERNAME_FIELD
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Email already implied by USERNAME_FIELD
    
    objects = CustomUserManager()
    
    class Meta:
        app_label = "users"
    
    def __str__(self):
        """Return string representation of the user."""
        return self.email
        
    def get_full_name(self):
        """Return the full name of the user or email if not available."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.email 


class AccountLockout(models.Model):
    """Track account lockout status and failed login attempts."""
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='lockout_status'
    )
    failed_attempts = models.IntegerField(default=0)
    last_failed_attempt = models.DateTimeField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Account Lockout')
        verbose_name_plural = _('Account Lockouts')
        app_label = "users"
    
    def __str__(self):
        return f"{self.user.email} - {'Locked' if self.is_locked else 'Active'}"
    
    def reset_failed_attempts(self):
        """Reset failed login attempt counter when user successfully authenticates or lockout expires."""
        from .security_logger import log_account_unlock
        
        was_locked = self.is_locked
        self.failed_attempts = 0
        self.last_failed_attempt = None
        self.is_locked = False
        self.locked_until = None
        self.save()
        
        # Log unlock event if account was previously locked
        if was_locked:
            log_account_unlock(
                user_email=self.user.email,
                user_id=self.user.id,
                unlock_method='automatic_expiry'
            )
    
    def increment_failed_attempts(self, request=None):
        """Increment failed login attempts and trigger account lockout when threshold is exceeded."""
        from django.conf import settings
        from .security_logger import log_account_lockout
        
        self.failed_attempts += 1
        self.last_failed_attempt = timezone.now()
        
        # Get lockout settings from Django settings
        max_attempts = getattr(settings, 'ACCOUNT_LOCKOUT_MAX_ATTEMPTS', 5)
        lockout_duration = getattr(settings, 'ACCOUNT_LOCKOUT_DURATION', 300)  # 5 minutes
        
        if self.failed_attempts >= max_attempts:
            self.is_locked = True
            self.locked_until = timezone.now() + timedelta(seconds=lockout_duration)
            
            # Log lockout event
            log_account_lockout(
                user_email=self.user.email,
                request=request,
                lockout_duration=lockout_duration,
                failed_attempts=self.failed_attempts
            )
        
        self.save()
        return self.is_locked
    
    def check_lockout_expired(self):
        """Check if account lockout period has expired and automatically unlock the account."""
        if self.is_locked and self.locked_until and timezone.now() > self.locked_until:
            self.reset_failed_attempts()
            return True
        return False
    
    @property
    def time_until_unlock(self):
        """Return remaining lockout duration as timedelta or None if account is not locked."""
        if not self.is_locked or not self.locked_until:
            return None
        
        time_remaining = self.locked_until - timezone.now()
        if time_remaining.total_seconds() <= 0:
            return None
        
        return time_remaining
    
    @property
    def lockout_duration_minutes(self):
        """Return total lockout duration in minutes for user-friendly display purposes."""
        if not self.locked_until or not self.last_failed_attempt:
            return 0
        
        duration = self.locked_until - self.last_failed_attempt
        return int(duration.total_seconds() / 60)


class TwoFactorAuth(models.Model):
    """Two-factor authentication settings for users (preparation)."""
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='two_factor_auth'
    )
    is_enabled = models.BooleanField(default=False)
    secret_key = models.CharField(max_length=32, blank=True)
    backup_codes = models.JSONField(default=list, blank=True)
    last_used = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Two-Factor Authentication')
        verbose_name_plural = _('Two-Factor Authentication Settings')
        app_label = "users"
    
    def __str__(self):
        return f"{self.user.email} - {'Enabled' if self.is_enabled else 'Disabled'}"
    
    def generate_backup_codes(self, count=10):
        """Generate cryptographically secure backup codes for emergency 2FA bypass scenarios."""
        import secrets
        import string
        
        self.backup_codes = []
        for _ in range(count):
            # Generate 8-character backup code
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            self.backup_codes.append(code)
        
        self.save()
        return self.backup_codes
    
    def use_backup_code(self, code):
        """Validate and consume a backup code for 2FA authentication, removing it from available codes."""
        if code in self.backup_codes:
            self.backup_codes.remove(code)
            self.last_used = timezone.now()
            self.save()
            return True
        return False 