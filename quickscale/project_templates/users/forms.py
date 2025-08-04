"""Enhanced profile forms for QuickScale users."""
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from allauth.account.forms import SignupForm, LoginForm, ResetPasswordForm, ChangePasswordForm

from .models import CustomUser

User = get_user_model()


class CustomSignupForm(SignupForm):
    """Custom signup form with proper CSS styling."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bulma CSS classes to form fields
        self.fields['email'].widget.attrs.update({
            'class': 'input',
            'placeholder': 'your.email@example.com'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'input',
            'placeholder': 'Password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'input',
            'placeholder': 'Confirm Password'
        })


class CustomLoginForm(LoginForm):
    """Custom login form with proper CSS styling and account lockout checking."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bulma CSS classes to form fields
        self.fields['login'].widget.attrs.update({
            'class': 'input',
            'placeholder': 'your.email@example.com'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'input',
            'placeholder': 'Password'
        })

    def clean(self):
        """Add account lockout validation to login form."""
        cleaned_data = super().clean()
        
        # Get the login field (email)
        login = cleaned_data.get('login')
        if login:
            try:
                from django.contrib.auth import get_user_model
                from .models import AccountLockout
                
                User = get_user_model()
                user = User.objects.get(email=login)
                
                # Check if user has an active lockout
                try:
                    # Always fetch fresh data from database to avoid caching issues
                    lockout = AccountLockout.objects.select_for_update().get(user=user)
                    if lockout.is_locked:
                        # Check if lockout has expired
                        if not lockout.check_lockout_expired():
                            # Account is still locked
                            from django.forms import ValidationError
                            raise ValidationError("Too many failed login attempts. Try again later.")
                except AccountLockout.DoesNotExist:
                    # No lockout record exists, user can proceed
                    pass
                    
            except User.DoesNotExist:
                # User doesn't exist, let normal validation handle it
                pass
        
        return cleaned_data


class CustomResetPasswordForm(ResetPasswordForm):
    """Custom password reset form with proper CSS styling."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bulma CSS classes to form fields
        self.fields['email'].widget.attrs.update({
            'class': 'input',
            'placeholder': 'your.email@example.com'
        })


class CustomChangePasswordForm(ChangePasswordForm):
    """Custom password change form with proper CSS styling."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bulma CSS classes to form fields
        self.fields['oldpassword'].widget.attrs.update({
            'class': 'input',
            'placeholder': 'Current Password'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'input',
            'placeholder': 'New Password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'input',
            'placeholder': 'Confirm New Password'
        })


class ProfileForm(forms.ModelForm):
    """Enhanced profile form with comprehensive validation and field organization."""
    
    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'bio', 'phone_number', 'profile_picture',
            'job_title', 'company', 'website', 'location', 'twitter', 'linkedin',
            'github', 'email_notifications'
        ]
        
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'First name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Last name'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'textarea',
                'rows': 4,
                'placeholder': 'Tell us about yourself...'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': '+1 (555) 123-4567'
            }),
            'job_title': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Software Engineer'
            }),
            'company': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Company name'
            }),
            'website': forms.URLInput(attrs={
                'class': 'input',
                'placeholder': 'https://yourwebsite.com'
            }),
            'location': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'City, Country'
            }),
            'twitter': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'twitter_handle'
            }),
            'linkedin': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'linkedin_username'
            }),
            'github': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'github_username'
            }),
            'email_notifications': forms.CheckboxInput(attrs={
                'class': 'checkbox'
            }),
        }
    
    def clean_website(self):
        """Validate and format website URL with protocol."""
        website = self.cleaned_data.get('website')
        if website and not website.startswith(('http://', 'https://')):
            website = f'https://{website}'
        return website
    
    def clean_phone_number(self):
        """Basic phone number validation."""
        phone = self.cleaned_data.get('phone_number')
        if phone:
            # Remove common separators and spaces
            phone_cleaned = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('+', '')
            # Basic validation - should be digits only after cleanup
            if not phone_cleaned.isdigit():
                raise ValidationError("Please enter a valid phone number.")
            # Check reasonable length (7-15 digits for international numbers)
            if len(phone_cleaned) < 7 or len(phone_cleaned) > 15:
                raise ValidationError("Phone number must be between 7 and 15 digits.")
        return phone  # Return original format for display 
