"""Custom password validators for enhanced security."""
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class PasswordStrengthValidator:
    """Validate that password meets minimum strength requirements."""
    
    def __init__(self, min_length=8, require_uppercase=True, require_lowercase=True,
                 require_digit=True, require_special=True):
        """Initialize validator with customizable requirements."""
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digit = require_digit
        self.require_special = require_special
    
    def validate(self, password, user=None):
        """Validate the password against the requirements."""
        errors = []
        
        # Check password length
        if len(password) < self.min_length:
            errors.append(ValidationError(
                _("Password must be at least %(min_length)d characters long."),
                code='password_too_short',
                params={'min_length': self.min_length},
            ))
        
        # Check for uppercase letters
        if self.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append(ValidationError(
                _("Password must contain at least one uppercase letter."),
                code='password_no_uppercase',
            ))
        
        # Check for lowercase letters
        if self.require_lowercase and not re.search(r'[a-z]', password):
            errors.append(ValidationError(
                _("Password must contain at least one lowercase letter."),
                code='password_no_lowercase',
            ))
        
        # Check for digits
        if self.require_digit and not re.search(r'\d', password):
            errors.append(ValidationError(
                _("Password must contain at least one digit."),
                code='password_no_digit',
            ))
        
        # Check for special characters
        if self.require_special and not re.search(r'[^A-Za-z0-9]', password):
            errors.append(ValidationError(
                _("Password must contain at least one special character (e.g., @, #, $, etc.)."),
                code='password_no_special',
            ))
        
        if errors:
            raise ValidationError(errors)
    
    def get_help_text(self):
        """Return help text for this validator."""
        help_texts = [
            _("Your password must be at least %(min_length)d characters long.") % {'min_length': self.min_length}
        ]
        
        if self.require_uppercase:
            help_texts.append(_("Your password must contain at least one uppercase letter."))
            
        if self.require_lowercase:
            help_texts.append(_("Your password must contain at least one lowercase letter."))
            
        if self.require_digit:
            help_texts.append(_("Your password must contain at least one digit."))
            
        if self.require_special:
            help_texts.append(_("Your password must contain at least one special character (e.g., @, #, $, etc.)."))
            
        return " ".join(help_texts)


class BreachedPasswordValidator:
    """Validator that checks if the password has been compromised in data breaches."""
    
    def __init__(self, min_pwned_count=1):
        """Initialize validator with minimum number of times a password needs to be present in breaches."""
        self.min_pwned_count = min_pwned_count
        
    def validate(self, password, user=None):
        """
        Check if password appears in known breached password databases.
        
        This is a placeholder for the actual implementation which would use:
        - API calls to services like HaveIBeenPwned or similar
        - Check against locally stored breach data
        
        In a production environment, replace with actual implementation.
        """
        # Placeholder implementation with some common passwords
        common_passwords = {
            'password', 'password123', '123456', 'qwerty', 'admin', 
            'welcome', 'letmein', 'abc123', 'monkey'
        }
        
        if password.lower() in common_passwords:
            raise ValidationError(
                _("This password has been found in data breaches and is not secure."),
                code='password_compromised',
            )
            
    def get_help_text(self):
        """Return help text for this validator."""
        return _("Your password cannot be a commonly used password that has appeared in data breaches.") 