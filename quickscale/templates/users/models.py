"""Custom user model for email-only authentication."""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


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

class StripeCustomer(models.Model):
    """
    Model representing a Stripe customer linked to a user.
    
    This model stores the relationship between a Django user and their
    corresponding Stripe customer ID, allowing the application to track
    which user is associated with which Stripe customer.
    """
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE,
        related_name='stripe_customer',
        verbose_name=_('user')
    )
    stripe_id = models.CharField(
        _('stripe customer ID'),
        max_length=255,
        help_text=_('Stripe customer identifier')
    )
    created = models.DateTimeField(
        _('created'),
        auto_now_add=True,
        help_text=_('Date and time when the customer was created')
    )
    
    class Meta:
        app_label = "users"
        verbose_name = _('stripe customer')
        verbose_name_plural = _('stripe customers')
    
    def __str__(self):
        """Return string representation of the customer."""
        return f"{self.user.email} ({self.stripe_id})" 