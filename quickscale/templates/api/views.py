"""API views for QuickScale AI services."""
import logging
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError
from decimal import Decimal
from .utils import (
    APIResponse, 
    validate_json_request, 
    validate_required_fields, 
    validate_text_length,
    consume_service_credits
)
from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

# Services imports - wrapped in try-except for template compatibility
try:
    from services.decorators import create_service_instance
    from services.examples import (
        TextSentimentAnalysisService,
        TextKeywordExtractorService,
        ImageMetadataExtractorService,
        DataValidatorService
    )
    SERVICES_AVAILABLE = True
except ImportError:
    # This will happen when running tests in the generator codebase
    # where services is just a template directory, not a Python module
    SERVICES_AVAILABLE = False
    create_service_instance = None
    TextSentimentAnalysisService = None
    TextKeywordExtractorService = None
    ImageMetadataExtractorService = None
    DataValidatorService = None

from credits.models import Service

logger = logging.getLogger(__name__)

# List of all available example services, useful for API documentation
EXAMPLE_SERVICES = []
if SERVICES_AVAILABLE:
    EXAMPLE_SERVICES = [
        TextSentimentAnalysisService,
        TextKeywordExtractorService,
        ImageMetadataExtractorService,
        DataValidatorService
    ]

@method_decorator(csrf_exempt, name='dispatch')
class TextProcessingView(View):
    """API endpoint for text processing services."""
    
    def post(self, request):
        """Process text and return analysis results."""
        try:
            # Validate API authentication (handled by middleware)
            if not hasattr(request, 'api_authenticated') or not request.api_authenticated:
                return APIResponse.unauthorized("API key authentication required")
            
            # Validate JSON request
            data = validate_json_request(request)
            
            # Validate required fields
            validate_required_fields(data, ['text', 'operation'])
            
            text = data['text']
            operation = data['operation']
            
            # Validate text length
            validate_text_length(text, min_length=1, max_length=10000)
            
            # Validate operation type
            allowed_operations = ['analyze', 'summarize', 'count_words', 'count_characters']
            if operation not in allowed_operations:
                return APIResponse.validation_error({
                    'operation': f"Operation must be one of: {', '.join(allowed_operations)}"
                })
            
            # Define credit cost based on operation
            credit_costs = {
                'analyze': Decimal('2.0'),
                'summarize': Decimal('5.0'),
                'count_words': Decimal('0.5'),
                'count_characters': Decimal('0.1')
            }
            
            credit_cost = credit_costs[operation]
            
            # Consume credits for the service
            try:
                consume_service_credits(
                    user=request.user,
                    service_name='Text Processing',
                    credit_cost=credit_cost
                )
            except ValidationError as e:
                return APIResponse.error(
                    message=str(e),
                    status=402,  # Payment Required
                    error_code='INSUFFICIENT_CREDITS'
                )
            
            # Process the text based on operation
            result = self._process_text(text, operation)
            
            # Log successful request
            logger.info(f"Text processing request completed for user {request.user.email}: {operation}")
            
            return APIResponse.success(
                data={
                    'operation': operation,
                    'credits_consumed': str(credit_cost),
                    'result': result
                },
                message=f"Text {operation} completed successfully"
            )
            
        except ValidationError as e:
            return APIResponse.validation_error({'error': str(e)})
        except Exception as e:
            logger.error(f"Text processing error: {e}")
            return APIResponse.server_error("An error occurred while processing your request")
    
    def _process_text(self, text, operation):
        """Process text based on the requested operation."""
        if operation == 'count_words':
            word_count = len(text.split())
            return {
                'word_count': word_count,
                'text_preview': text[:100] + '...' if len(text) > 100 else text
            }
        
        elif operation == 'count_characters':
            char_count = len(text)
            char_count_no_spaces = len(text.replace(' ', ''))
            return {
                'character_count': char_count,
                'character_count_no_spaces': char_count_no_spaces,
                'text_preview': text[:100] + '...' if len(text) > 100 else text
            }
        
        elif operation == 'analyze':
            words = text.split()
            sentences = text.count('.') + text.count('!') + text.count('?')
            paragraphs = len([p for p in text.split('\n\n') if p.strip()])
            
            # Basic readability metrics
            avg_words_per_sentence = len(words) / max(sentences, 1)
            avg_chars_per_word = sum(len(word.strip('.,!?;:')) for word in words) / max(len(words), 1)
            
            return {
                'word_count': len(words),
                'character_count': len(text),
                'sentence_count': sentences,
                'paragraph_count': paragraphs,
                'average_words_per_sentence': round(avg_words_per_sentence, 2),
                'average_characters_per_word': round(avg_chars_per_word, 2),
                'text_preview': text[:200] + '...' if len(text) > 200 else text
            }
        
        elif operation == 'summarize':
            # Simple extractive summarization - take first few sentences
            sentences = []
            for delimiter in ['. ', '! ', '? ']:
                if delimiter in text:
                    sentences = text.split(delimiter)
                    break
            
            if not sentences:
                sentences = [text]
            
            # Take first 2-3 sentences as summary
            summary_sentences = sentences[:min(3, len(sentences))]
            summary = '. '.join(s.strip() for s in summary_sentences if s.strip())
            
            if not summary.endswith(('.', '!', '?')):
                summary += '.'
            
            return {
                'original_length': len(text),
                'summary_length': len(summary),
                'compression_ratio': round(len(summary) / len(text), 2),
                'summary': summary,
                'sentences_extracted': len(summary_sentences)
            }
        
        return {}
    
    def get(self, request):
        """Return API endpoint information."""
        return APIResponse.success(
            data={
                'endpoint': 'Text Processing API',
                'version': '1.0',
                'supported_operations': [
                    {
                        'operation': 'count_words',
                        'description': 'Count words in text',
                        'credit_cost': '0.5'
                    },
                    {
                        'operation': 'count_characters', 
                        'description': 'Count characters in text',
                        'credit_cost': '0.1'
                    },
                    {
                        'operation': 'analyze',
                        'description': 'Comprehensive text analysis',
                        'credit_cost': '2.0'
                    },
                    {
                        'operation': 'summarize',
                        'description': 'Generate text summary',
                        'credit_cost': '5.0'
                    }
                ],
                'required_fields': ['text', 'operation'],
                'text_limits': {
                    'min_length': 1,
                    'max_length': 10000
                }
            },
            message="Text Processing API endpoint information"
        )

# Service execution endpoint
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def execute_service(request: Request) -> Response:
    """Execute an AI service and deduct credits."""
    service_name = request.data.get('service_name')
    if not service_name:
        return APIResponse(
            success=False,
            message="Service name is required.",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    try:
        service_instance = create_service_instance(service_name)
    except ValueError:
        return APIResponse(
            success=False,
            message=f"Service '{service_name}' not found or not registered.",
            status_code=status.HTTP_404_NOT_FOUND
        )

    user = request.user
    if not user.is_authenticated:
        return APIResponse(
            success=False,
            message="Authentication required.",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    try:
        # Pass remaining kwargs to the service
        service_input = {k: v for k, v in request.data.items() if k != 'service_name'}
        result = service_instance.run(user, **service_input)
        return APIResponse(
            success=True,
            message=f"Service '{service_name}' executed successfully.",
            data=result,
            status_code=status.HTTP_200_OK
        )
    except ValueError as e:
        return APIResponse(
            success=False,
            message=str(e),
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return APIResponse(
            success=False,
            message=f"An unexpected error occurred: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# List available services endpoint
@api_view(['GET'])
@permission_classes([AllowAny])
def list_services(request: Request) -> Response:
    """List all available AI services with their details."""
    services = Service.objects.filter(is_active=True).values('name', 'description', 'credit_cost')
    return APIResponse(
        success=True,
        message="Available services listed.",
        data=list(services),
        status_code=status.HTTP_200_OK
    )

@require_http_methods(["GET"])
@permission_classes([AllowAny])
def api_docs(request: Request) -> HttpResponse:
    """Display the API documentation page."""
    context = {
        'page_title': 'API Documentation',
        'page_description': 'Complete API reference for AI engineers',
        'example_services': EXAMPLE_SERVICES,
    }
    return render(request, 'api/api_docs.html', context)