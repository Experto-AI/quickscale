"""
Usage example for TestServiceService.

This example demonstrates how to use the test_service service
with the QuickScale credit system.
"""

from django.contrib.auth import get_user_model
from services.decorators import create_service_instance
from credits.models import InsufficientCreditsError

User = get_user_model()


def use_test_service_service(user, **kwargs):
    """Example function showing how to use the test_service service."""
    
    # Method 1: Using the service registry
    service = create_service_instance("test_service")
    if not service:
        return {'error': 'Service test_service not found'}
    
    # Check if user has sufficient credits
    credit_check = service.check_user_credits(user)
    if not credit_check['has_sufficient_credits']:
        return {
            'error': f"Insufficient credits. Need {credit_check['shortfall']} more credits.",
            'required_credits': credit_check['required_credits'],
            'available_credits': credit_check['available_credits']
        }
    
    # Run the service (consumes credits and executes)
    try:
        result = service.run(user, **kwargs)
        return result
    except InsufficientCreditsError as e:
        return {'error': str(e)}
    except ValueError as e:
        return {'error': f"Validation error: {str(e)}"}
    except Exception as e:
        return {'error': f"Service execution error: {str(e)}"}


def example_usage():
    """Example usage scenarios."""
    # Get a user (in real usage, this would come from request.user or similar)
    user = User.objects.first()
    if not user:
        print("No users found. Please create a user first.")
        return
    
    # Example 1: Basic usage
    result = use_test_service_service(
        user,
        input_data="Example input data"  # TODO: Adjust based on your service needs
    )
    print("Result:", result)
    
    # Example 2: Error handling
    if 'error' in result:
        print(f"Service error: {result['error']}")
    else:
        print(f"Service succeeded: {result.get('result', {})}")
        print(f"Credits consumed: {result.get('credits_consumed', 0)}")


if __name__ == "__main__":
    # This would typically be called from views, management commands, or API endpoints
    example_usage()
