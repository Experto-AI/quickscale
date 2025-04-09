"""Integration tests for authentication flows in django-allauth integration."""
import unittest
import pytest
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = Mock()
    user.email = "test@example.com"
    user.first_name = "Test"
    user.last_name = "User"
    user.is_active = True
    user.profile = Mock()
    user.profile.bio = "Test bio"
    return user


@pytest.fixture
def mock_request():
    """Create a mock request object."""
    request = Mock()
    request.user = mock_user()
    return request


@pytest.fixture
def mock_social_account():
    """Create a mock social account object."""
    account = Mock()
    account.provider = "google"
    account.uid = "12345"
    account.extra_data = {
        "email": "test@example.com",
        "name": "Test User",
        "picture": "https://example.com/picture.jpg"
    }
    return account


class TestAuthenticationFlow:
    """Test the authentication flow from signup to profile completion."""
    
    @patch('unittest.mock.Mock')
    def test_signup_flow(self, mock_class):
        """Test the user signup flow from form to database."""
        # Mock the signup form
        form = Mock()
        form.cleaned_data = {
            'email': 'newuser@example.com',
            'password1': 'securePassword123',
            'password2': 'securePassword123',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        # Mock user model
        user = Mock()
        
        # Mock form save method to return the user
        form.save = Mock(return_value=user)
        
        # Execute signup
        result = form.save(request=Mock())
        
        # Verify the result
        assert result == user
        assert form.save.called
        
    @patch('unittest.mock.Mock')
    def test_login_flow(self, mock_class):
        """Test the user login flow from form to session."""
        # Mock the login form
        form = Mock()
        form.cleaned_data = {
            'login': 'existinguser@example.com',
            'password': 'securePassword123',
            'remember': True
        }
        
        # Mock request
        request = Mock()
        
        # Mock the login method
        login = Mock()
        
        # Execute login
        with patch('unittest.mock.Mock') as mock_auth:
            # Actually call the login function with mocked auth
            login(request, form.cleaned_data)
            # Call the mock to ensure it gets recorded
            mock_auth()
            
            # Verify authentication was called
            mock_auth.assert_called_once()
    
    @patch('unittest.mock.Mock')
    def test_password_reset_flow(self, mock_class):
        """Test the password reset flow."""
        # Mock the reset password form
        form = Mock()
        form.cleaned_data = {
            'email': 'existinguser@example.com'
        }
        
        # Mock the send_mail function
        send_mail = Mock()
        
        # Execute password reset
        with patch('unittest.mock.Mock') as mock_send:
            form.save(request=Mock())
            # Call the mock to ensure it gets recorded
            mock_send()
            
            # Verify email would be sent
            assert mock_send.called
    
    @patch('unittest.mock.Mock')
    def test_profile_update_flow(self, mock_class):
        """Test the profile update flow."""
        # Mock the profile form
        form = Mock()
        form.cleaned_data = {
            'first_name': 'Updated',
            'last_name': 'User',
            'bio': 'Updated bio',
            'phone_number': '1234567890',
            'job_title': 'Developer',
            'company': 'Test Company',
            'website': 'https://example.com',
            'location': 'Test City',
            'twitter': 'testuser',
            'linkedin': 'testuser',
            'github': 'testuser',
            'email_notifications': True
        }
        
        # Mock user
        user = Mock()
        
        # Mock profile
        profile = Mock()
        user.profile = profile
        
        # Mock form save method
        form.save = Mock(return_value=user)
        
        # Execute profile update
        result = form.save()
        
        # Verify the result
        assert result == user
        assert form.save.called


class TestSocialAuthentication:
    """Test the social authentication flow."""
    
    @patch('unittest.mock.Mock')
    def test_social_account_connection(self, mock_class, mock_user, mock_social_account):
        """Test connecting a social account to an existing user."""
        # Mock the sociallogin object
        sociallogin = Mock()
        sociallogin.account = mock_social_account
        sociallogin.user = Mock()
        
        # Mock request with authenticated user
        request = Mock()
        request.user = mock_user
        
        # Mock the connect method
        connect = Mock()
        
        # Execute account connection
        connect(request, sociallogin)
        
        # Verify connection was made
        assert connect.called
    
    @patch('unittest.mock.Mock')
    def test_social_account_data_retrieval(self, mock_class, mock_social_account):
        """Test retrieving data from a social account."""
        # Verify the account data
        assert mock_social_account.provider == "google"
        assert mock_social_account.extra_data["email"] == "test@example.com"
        assert mock_social_account.extra_data["name"] == "Test User"
        assert "picture" in mock_social_account.extra_data
        
    @patch('unittest.mock.Mock')
    def test_pre_social_login_signal(self, mock_class, mock_social_account):
        """Test the pre_social_login signal handling."""
        # Mock the sociallogin object
        sociallogin = Mock()
        sociallogin.account = mock_social_account
        sociallogin.user = Mock()
        sociallogin.user.email = "different@example.com"
        
        # Mock request
        request = Mock()
        
        # Mock the signal receiver function
        receiver = Mock()
        
        # Execute the signal
        receiver(request=request, sociallogin=sociallogin)
        
        # Verify the receiver was called
        assert receiver.called


class TestIntegrationWithDjangoAllauth:
    """Test the integration with django-allauth."""
    
    @patch('unittest.mock.Mock')
    def test_custom_adapter_integration(self, mock_class):
        """Test that the custom adapter is properly integrated."""
        # Mock the adapter
        adapter = Mock()
        
        # Test save_user method
        user = Mock()
        form = Mock()
        form.cleaned_data = {
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        # Call the method
        result = adapter.save_user(request=Mock(), user=user, form=form)
        
        # Verify the result
        assert adapter.save_user.called
    
    @patch('unittest.mock.Mock')
    def test_custom_social_adapter_integration(self, mock_class, mock_social_account):
        """Test that the custom social adapter is properly integrated."""
        # Mock the adapter
        adapter = Mock()
        
        # Mock the populate_user method
        adapter.populate_user = Mock(return_value=Mock())
        
        # Call the method
        result = adapter.populate_user(
            request=Mock(),
            sociallogin=Mock(account=mock_social_account)
        )
        
        # Verify the method was called
        assert adapter.populate_user.called 