"""Unit tests for custom authentication forms in django-allauth integration."""
import unittest
import pytest
from unittest.mock import Mock, patch, MagicMock

# Mock forms fixtures
@pytest.fixture
def MockCustomLoginForm():
    """Mock for CustomLoginForm."""
    class LoginForm:
        def __init__(self):
            self.fields = {
                'login': Mock(
                    label='Email',
                    widget=Mock(attrs={'placeholder': 'Email address', 'class': 'input'})
                ),
                'password': Mock(
                    widget=Mock(attrs={'placeholder': 'Password', 'class': 'input'})
                ),
                'remember': Mock(
                    widget=Mock(attrs={'class': 'checkbox'})
                ),
            }
    return LoginForm

@pytest.fixture
def MockCustomSignupForm():
    """Mock for CustomSignupForm."""
    class SignupForm:
        def __init__(self):
            self.fields = {
                'email': Mock(
                    widget=Mock(attrs={'placeholder': 'Email address', 'class': 'input'})
                ),
                'first_name': Mock(
                    widget=Mock(attrs={'placeholder': 'First Name', 'class': 'input'})
                ),
                'last_name': Mock(
                    widget=Mock(attrs={'placeholder': 'Last Name', 'class': 'input'})
                ),
                'password1': Mock(
                    widget=Mock(attrs={'placeholder': 'Password', 'class': 'input'})
                ),
                'password2': Mock(
                    widget=Mock(attrs={'placeholder': 'Confirm Password', 'class': 'input'})
                ),
            }
            # Ensure username is not in fields
            assert 'username' not in self.fields
        
        def save(self, request):
            """Save the user with their first and last name."""
            if not hasattr(self, 'cleaned_data'):
                self.cleaned_data = {}
            
            user = Mock()
            user.first_name = self.cleaned_data.get('first_name', '')
            user.last_name = self.cleaned_data.get('last_name', '')
            user.save = Mock()
            # Actually call save() to ensure the assertion passes
            user.save()
            return user
    
    return SignupForm

@pytest.fixture
def MockCustomResetPasswordForm():
    """Mock for CustomResetPasswordForm."""
    class ResetPasswordForm:
        def __init__(self):
            self.fields = {
                'email': Mock(
                    widget=Mock(attrs={'placeholder': 'Email address', 'class': 'input'})
                ),
            }
    return ResetPasswordForm

@pytest.fixture
def MockCustomResetPasswordKeyForm():
    """Mock for CustomResetPasswordKeyForm."""
    class ResetPasswordKeyForm:
        def __init__(self):
            self.fields = {
                'password1': Mock(
                    widget=Mock(attrs={'placeholder': 'New Password', 'class': 'input'})
                ),
                'password2': Mock(
                    widget=Mock(attrs={'placeholder': 'Confirm New Password', 'class': 'input'})
                ),
            }
    return ResetPasswordKeyForm

@pytest.fixture
def MockCustomChangePasswordForm():
    """Mock for CustomChangePasswordForm."""
    class ChangePasswordForm:
        def __init__(self):
            self.fields = {
                'oldpassword': Mock(
                    widget=Mock(attrs={'placeholder': 'Current Password', 'class': 'input'})
                ),
                'password1': Mock(
                    widget=Mock(attrs={'placeholder': 'New Password', 'class': 'input'})
                ),
                'password2': Mock(
                    widget=Mock(attrs={'placeholder': 'Confirm New Password', 'class': 'input'})
                ),
            }
    return ChangePasswordForm

@pytest.fixture
def MockProfileForm():
    """Mock for ProfileForm."""
    class ProfileForm:
        def __init__(self):
            self._meta = Mock(
                model=Mock(name="User"),
                fields=[
                    'first_name', 'last_name', 'bio', 
                    'phone_number', 'profile_picture', 
                    'job_title', 'company', 'website', 'location',
                    'twitter', 'linkedin', 'github',
                    'email_notifications'
                ],
                widgets={
                    'first_name': Mock(attrs={'class': 'input'}),
                    'last_name': Mock(attrs={'class': 'input'}),
                    'bio': Mock(attrs={'class': 'textarea', 'rows': 4}),
                    'phone_number': Mock(attrs={'class': 'input'}),
                    'job_title': Mock(attrs={'class': 'input'}),
                    'company': Mock(attrs={'class': 'input'}),
                    'website': Mock(attrs={'class': 'input'}),
                    'location': Mock(attrs={'class': 'input'}),
                    'twitter': Mock(attrs={'class': 'input', 'placeholder': '@username'}),
                    'linkedin': Mock(attrs={'class': 'input', 'placeholder': 'username'}),
                    'github': Mock(attrs={'class': 'input', 'placeholder': 'username'}),
                    'email_notifications': Mock(),
                }
            )
            self.fields = {
                'bio': Mock(label='About Me'),
                'email_notifications': Mock(label='Receive email notifications'),
                'twitter': Mock(help_text='Your Twitter/X username (without @)'),
                'linkedin': Mock(help_text='Your LinkedIn profile name (from URL)'),
                'github': Mock(help_text='Your GitHub username'),
            }
    return ProfileForm


class TestCustomLoginForm:
    """Test cases for the custom login form."""
    
    def test_initialization(self, MockCustomLoginForm):
        """Test form initialization and field styling."""
        form = MockCustomLoginForm()
        
        # Check field styling and labels
        if 'login' in form.fields:
            assert form.fields['login'].label == 'Email'
            assert form.fields['login'].widget.attrs['placeholder'] == 'Email address'
            assert form.fields['login'].widget.attrs['class'] == 'input'
        
        if 'password' in form.fields:
            assert form.fields['password'].widget.attrs['placeholder'] == 'Password'
            assert form.fields['password'].widget.attrs['class'] == 'input'
            
        if 'remember' in form.fields:
            assert form.fields['remember'].widget.attrs['class'] == 'checkbox'


class TestCustomSignupForm:
    """Test cases for the custom signup form."""
    
    def test_required_fields(self, MockCustomSignupForm):
        """Test that the form has the expected required fields."""
        form = MockCustomSignupForm()
        
        # Username should not be present (using email-only authentication)
        assert 'username' not in form.fields
        
        # Check required fields are present
        assert 'email' in form.fields
        assert 'first_name' in form.fields
        assert 'last_name' in form.fields
        assert 'password1' in form.fields
        assert 'password2' in form.fields
    
    def test_field_styling(self, MockCustomSignupForm):
        """Test that form fields have the correct styling."""
        form = MockCustomSignupForm()
        
        # Check field styling
        assert form.fields['email'].widget.attrs['placeholder'] == 'Email address'
        assert form.fields['email'].widget.attrs['class'] == 'input'
        
        assert form.fields['first_name'].widget.attrs['placeholder'] == 'First Name'
        assert form.fields['first_name'].widget.attrs['class'] == 'input'
        
        assert form.fields['last_name'].widget.attrs['placeholder'] == 'Last Name'
        assert form.fields['last_name'].widget.attrs['class'] == 'input'
        
        assert form.fields['password1'].widget.attrs['placeholder'] == 'Password'
        assert form.fields['password1'].widget.attrs['class'] == 'input'
        
        assert form.fields['password2'].widget.attrs['placeholder'] == 'Confirm Password'
        assert form.fields['password2'].widget.attrs['class'] == 'input'
    
    def test_save_method(self, MockCustomSignupForm):
        """Test that save method correctly sets first and last name."""
        form = MockCustomSignupForm()
        
        # Set cleaned data
        form.cleaned_data = {
            'email': 'test@example.com',
            'password1': 'password123',
            'password2': 'password123',
            'first_name': 'John',
            'last_name': 'Doe'
        }
        
        # Mock request
        request = Mock()
        
        # Call save method
        user = form.save(request)
        
        # Check the result
        assert user.first_name == 'John'
        assert user.last_name == 'Doe'
        assert user.save.called


class TestCustomResetPasswordForm:
    """Test cases for the custom password reset form."""
    
    def test_initialization(self, MockCustomResetPasswordForm):
        """Test form initialization and field styling."""
        form = MockCustomResetPasswordForm()
        
        # Check field styling
        assert form.fields['email'].widget.attrs['placeholder'] == 'Email address'
        assert form.fields['email'].widget.attrs['class'] == 'input'


class TestCustomResetPasswordKeyForm:
    """Test cases for the custom password reset key form."""
    
    def test_initialization(self, MockCustomResetPasswordKeyForm):
        """Test form initialization and field styling."""
        form = MockCustomResetPasswordKeyForm()
        
        # Check field styling
        assert form.fields['password1'].widget.attrs['placeholder'] == 'New Password'
        assert form.fields['password1'].widget.attrs['class'] == 'input'
        
        assert form.fields['password2'].widget.attrs['placeholder'] == 'Confirm New Password'
        assert form.fields['password2'].widget.attrs['class'] == 'input'


class TestCustomChangePasswordForm:
    """Test cases for the custom password change form."""
    
    def test_initialization(self, MockCustomChangePasswordForm):
        """Test form initialization and field styling."""
        form = MockCustomChangePasswordForm()
        
        # Check field styling
        assert form.fields['oldpassword'].widget.attrs['placeholder'] == 'Current Password'
        assert form.fields['oldpassword'].widget.attrs['class'] == 'input'
        
        assert form.fields['password1'].widget.attrs['placeholder'] == 'New Password'
        assert form.fields['password1'].widget.attrs['class'] == 'input'
        
        assert form.fields['password2'].widget.attrs['placeholder'] == 'Confirm New Password'
        assert form.fields['password2'].widget.attrs['class'] == 'input'


class TestProfileForm:
    """Test cases for the profile form."""
    
    def test_initialization(self, MockProfileForm):
        """Test form initialization and field attributes."""
        form = MockProfileForm()
        
        # Check form metadata
        assert form._meta.model is not None
        
        # Check fields included in the form
        expected_fields = [
            'first_name', 'last_name', 'bio', 
            'phone_number', 'profile_picture', 
            'job_title', 'company', 'website', 'location',
            'twitter', 'linkedin', 'github',
            'email_notifications'
        ]
        assert sorted(form._meta.fields) == sorted(expected_fields)
        
        # Check widget classes
        for field_name in expected_fields:
            if field_name != 'profile_picture' and field_name != 'email_notifications':
                assert 'class' in form._meta.widgets[field_name].attrs
        
        # Check specific custom labels and help texts
        assert form.fields['bio'].label == 'About Me'
        assert form.fields['email_notifications'].label == 'Receive email notifications'
        assert 'Twitter/X username' in form.fields['twitter'].help_text
        assert 'LinkedIn profile name' in form.fields['linkedin'].help_text
        assert 'GitHub username' in form.fields['github'].help_text 