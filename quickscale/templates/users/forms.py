"""Enhanced authentication forms for QuickScale with improved security and UX."""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from allauth.account.models import EmailAddress

from .models import CustomUser

User = get_user_model()


class EnhancedSignupForm(UserCreationForm):
    """Enhanced signup form with email-only authentication and comprehensive validation."""
    
    email = forms.EmailField(
        max_length=254,
        required=True,
        help_text="Required. Enter a valid email address.",
        widget=forms.EmailInput(attrs={
            'class': 'input',
            'placeholder': 'your.email@example.com',
            'autocomplete': 'email'
        }),
        error_messages={
            'required': 'Email address is required.',
            'invalid': 'Please enter a valid email address.',
        }
    )
    
    # Remove username field completely
    username = None
    
    # Enhanced password fields with better attributes
    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'input',
            'placeholder': 'Password (8+ characters)',
            'autocomplete': 'new-password',
            'minlength': '8'
        }),
        help_text=_("Your password must be at least 8 characters long and contain uppercase letters, lowercase letters, numbers, and special characters."),
        error_messages={
            'required': 'Password is required.',
        }
    )
    
    password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput(attrs={
            'class': 'input',
            'placeholder': 'Confirm password',
            'autocomplete': 'new-password',
            'minlength': '8'
        }),
        help_text=_("Enter the same password as before, for verification."),
        error_messages={
            'required': 'Password confirmation is required.',
        }
    )
    
    class Meta:
        model = CustomUser
        fields = ('email',)
    
    def clean_email(self):
        """Validate email uniqueness and format."""
        email = self.cleaned_data.get('email')
        if email:
            # Check if user already exists
            if User.objects.filter(email=email).exists():
                raise ValidationError(
                    _("A user with this email address already exists. Please use a different email or try logging in."),
                    code='email_exists'
                )
        return email
    
    def save(self, commit=True):
        """Save user with email as primary identifier."""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = None  # Ensure username is not set
        if commit:
            user.save()
        return user


class EnhancedLoginForm(AuthenticationForm):
    """Enhanced login form with email-only authentication and improved UX."""
    
    username = forms.EmailField(
        label=_("Email"),
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'input',
            'placeholder': 'your.email@example.com',
            'autocomplete': 'email',
            'autofocus': True
        }),
        error_messages={
            'required': 'Email address is required.',
            'invalid': 'Please enter a valid email address.',
        }
    )
    
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'input',
            'placeholder': 'Password',
            'autocomplete': 'current-password'
        }),
        error_messages={
            'required': 'Password is required.',
        }
    )
    
    error_messages = {
        'invalid_login': _(
            "Please enter a correct email and password. Note that both "
            "fields may be case-sensitive."
        ),
        'inactive': _("This account is inactive."),
    }


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