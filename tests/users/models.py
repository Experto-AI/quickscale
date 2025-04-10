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
    
    # Additional fields can be added here
    
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