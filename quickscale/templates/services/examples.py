"""
Example implementations showing how to use the AI Service Framework.

This file demonstrates how AI engineers can create services that integrate
with the existing credit system using the BaseService class and @register_service decorator.
"""

from .base import BaseService
from .decorators import register_service
from django.contrib.auth import get_user_model

User = get_user_model()


@register_service("text_analysis")
class TextAnalysisService(BaseService):
    """Example service for text analysis that consumes credits."""
    
    def execute_service(self, user: User, text: str = "", **kwargs):
        """Analyze text and return results."""
        # This is where you would implement your AI service logic
        # For example: sentiment analysis, text classification, etc.
        
        # Placeholder implementation
        word_count = len(text.split()) if text else 0
        char_count = len(text)
        
        # Example analysis result
        analysis_result = {
            'word_count': word_count,
            'character_count': char_count,
            'analysis_type': 'basic_text_analysis',
            'status': 'completed'
        }
        
        return analysis_result


@register_service("image_processing")
class ImageProcessingService(BaseService):
    """Example service for image processing that consumes credits."""
    
    def execute_service(self, user: User, image_data=None, **kwargs):
        """Process image and return results."""
        # This is where you would implement your AI service logic
        # For example: image classification, object detection, etc.
        
        if not image_data:
            raise ValueError("Image data is required for processing")
        
        # Placeholder implementation
        processing_result = {
            'image_size': len(image_data) if isinstance(image_data, (str, bytes)) else 'unknown',
            'processing_type': 'basic_image_processing',
            'status': 'completed',
            'detected_objects': ['placeholder_object_1', 'placeholder_object_2']
        }
        
        return processing_result


# Example usage:
"""
# How to use the service framework:

from services.examples import TextAnalysisService
from services.decorators import create_service_instance
from django.contrib.auth import get_user_model

User = get_user_model()

# Method 1: Direct instantiation
def analyze_text_direct(user, text):
    service = TextAnalysisService("text_analysis")
    
    # Check if user has sufficient credits
    credit_check = service.check_user_credits(user)
    if not credit_check['has_sufficient_credits']:
        return {'error': f"Insufficient credits. Need {credit_check['shortfall']} more credits."}
    
    # Run the service (consumes credits and executes)
    try:
        result = service.run(user, text=text)
        return result
    except InsufficientCreditsError as e:
        return {'error': str(e)}

# Method 2: Using the service registry
def analyze_text_registry(user, text):
    service = create_service_instance("text_analysis")
    if not service:
        return {'error': 'Service not found'}
    
    try:
        result = service.run(user, text=text)
        return result
    except InsufficientCreditsError as e:
        return {'error': str(e)}

# Method 3: Just consume credits without using run()
def consume_credits_only(user):
    service = TextAnalysisService("text_analysis")
    try:
        service_usage = service.consume_credits(user)
        # Now you can use the credits for your own logic
        # The service_usage record tracks the consumption
        return {'success': True, 'service_usage_id': service_usage.id}
    except InsufficientCreditsError as e:
        return {'error': str(e)}
"""