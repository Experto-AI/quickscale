"""Custom forms for django-allauth with email-only authentication."""
from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from allauth.account.forms import LoginForm, SignupForm, ResetPasswordForm, ResetPasswordKeyForm, ChangePasswordForm

User = get_user_model()


class CustomLoginForm(LoginForm):
    """Custom login form that uses email instead of username."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the form with custom fields."""
        super().__init__(*args, **kwargs)
        # Remove username field if it exists (should be using email)
        if 'login' in self.fields:
            self.fields['login'].label = _('Email')
            self.fields['login'].widget.attrs.update({
                'placeholder': _('Email address'),
                'class': 'input',
            })
        
        # Style the password field
        if 'password' in self.fields:
            self.fields['password'].widget.attrs.update({
                'placeholder': _('Password'),
                'class': 'input',
            })
        
        # Style the remember field
        if 'remember' in self.fields:
            self.fields['remember'].widget.attrs.update({
                'class': 'checkbox',
            })


class CustomSignupForm(SignupForm):
    """Custom signup form for email-only authentication."""
    
    # Remove username field
    username = None
    
    # Add additional fields
    first_name = forms.CharField(
        max_length=30,
        label=_('First Name'),
        widget=forms.TextInput(attrs={
            'placeholder': _('First Name'),
            'class': 'input',
        }),
    )
    
    last_name = forms.CharField(
        max_length=30,
        label=_('Last Name'),
        widget=forms.TextInput(attrs={
            'placeholder': _('Last Name'),
            'class': 'input',
        }),
    )
    
    def __init__(self, *args, **kwargs):
        """Initialize the form with custom styling."""
        super().__init__(*args, **kwargs)
        
        # Style the email field
        self.fields['email'].widget.attrs.update({
            'placeholder': _('Email address'),
            'class': 'input',
        })
        
        # Style the password fields
        self.fields['password1'].widget.attrs.update({
            'placeholder': _('Password'),
            'class': 'input',
        })
        self.fields['password2'].widget.attrs.update({
            'placeholder': _('Confirm Password'),
            'class': 'input',
        })
    
    def save(self, request):
        """Save the user with their first and last name."""
        user = super().save(request)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()
        return user


class CustomResetPasswordForm(ResetPasswordForm):
    """Custom password reset form."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the form with custom styling."""
        super().__init__(*args, **kwargs)
        
        # Style the email field
        self.fields['email'].widget.attrs.update({
            'placeholder': _('Email address'),
            'class': 'input',
        })


class CustomResetPasswordKeyForm(ResetPasswordKeyForm):
    """Custom password reset key form."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the form with custom styling."""
        super().__init__(*args, **kwargs)
        
        # Style the password fields
        self.fields['password1'].widget.attrs.update({
            'placeholder': _('New Password'),
            'class': 'input',
        })
        self.fields['password2'].widget.attrs.update({
            'placeholder': _('Confirm New Password'),
            'class': 'input',
        })


class CustomChangePasswordForm(ChangePasswordForm):
    """Custom password change form."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the form with custom styling."""
        super().__init__(*args, **kwargs)
        
        # Style the password fields
        self.fields['oldpassword'].widget.attrs.update({
            'placeholder': _('Current Password'),
            'class': 'input',
        })
        self.fields['password1'].widget.attrs.update({
            'placeholder': _('New Password'),
            'class': 'input',
        })
        self.fields['password2'].widget.attrs.update({
            'placeholder': _('Confirm New Password'),
            'class': 'input',
        })


class ProfileForm(forms.ModelForm):
    """Form for editing user profile information."""
    
    class Meta:
        """Metadata for the ProfileForm."""
        model = User
        fields = [
            'first_name', 'last_name', 'bio', 
            'phone_number', 'profile_picture', 
            'job_title', 'company', 'website', 'location',
            'twitter', 'linkedin', 'github',
            'email_notifications'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'input'}),
            'last_name': forms.TextInput(attrs={'class': 'input'}),
            'bio': forms.Textarea(attrs={'class': 'textarea', 'rows': 4}),
            'phone_number': forms.TextInput(attrs={'class': 'input'}),
            'job_title': forms.TextInput(attrs={'class': 'input'}),
            'company': forms.TextInput(attrs={'class': 'input'}),
            'website': forms.URLInput(attrs={'class': 'input'}),
            'location': forms.TextInput(attrs={'class': 'input'}),
            'twitter': forms.TextInput(attrs={'class': 'input', 'placeholder': '@username'}),
            'linkedin': forms.TextInput(attrs={'class': 'input', 'placeholder': 'username'}),
            'github': forms.TextInput(attrs={'class': 'input', 'placeholder': 'username'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'checkbox'}),
        }
        
    def __init__(self, *args, **kwargs):
        """Initialize the form with custom field labels."""
        super().__init__(*args, **kwargs)
        self.fields['bio'].label = _('About Me')
        self.fields['email_notifications'].label = _('Receive email notifications')
        self.fields['twitter'].help_text = _('Your Twitter/X username (without @)')
        self.fields['linkedin'].help_text = _('Your LinkedIn profile name (from URL)')
        self.fields['github'].help_text = _('Your GitHub username') 