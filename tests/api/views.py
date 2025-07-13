"""API views for text processing and other services."""
import json
import logging
from decimal import Decimal
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from credits.models import Service, CreditAccount, ServiceUsage, InsufficientCreditsError

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class TextProcessingView(View):
    """API view for text processing operations."""

    def get(self, request):
        """Return API endpoint information."""
        return JsonResponse({
            'success': True,
            'data': {
                'endpoint': 'Text Processing API',
                'version': '1.0',
                'description': 'API for text analysis and processing operations',
                'supported_operations': [
                    {
                        'operation': 'count_words',
                        'description': 'Count words in text',
                        'credit_cost': 0.5
                    },
                    {
                        'operation': 'count_characters',
                        'description': 'Count characters in text',
                        'credit_cost': 0.1
                    },
                    {
                        'operation': 'analyze',
                        'description': 'Comprehensive text analysis',
                        'credit_cost': 2.0
                    },
                    {
                        'operation': 'summarize',
                        'description': 'Generate text summary',
                        'credit_cost': 5.0
                    }
                ],
                'required_fields': ['text', 'operation'],
                'text_limits': {
                    'min_length': 1,
                    'max_length': 10000
                }
            }
        })

    def post(self, request):
        """Process text analysis requests."""
        try:
            # Validate content type
            if request.content_type != 'application/json':
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid content type',
                    'details': {'error': 'Content-Type must be application/json'}
                }, status=400)

            # Parse JSON data
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid JSON',
                    'details': {'error': 'Invalid JSON format'}
                }, status=400)

            # Validate required fields presence
            text = data.get('text')
            operation = data.get('operation')
            
            missing_fields = []
            if 'text' not in data:
                missing_fields.append('text')
            if 'operation' not in data:
                missing_fields.append('operation')
                
            if missing_fields:
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required fields',
                    'details': {'error': f'Missing required fields: {", ".join(missing_fields)}'}
                }, status=400)

            # Validate operation
            valid_operations = ['count_words', 'count_characters', 'analyze', 'summarize']
            if operation not in valid_operations:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid operation',
                    'details': {'operation': f'Operation must be one of: {", ".join(valid_operations)}'}
                }, status=400)

            # Validate text length
            if len(text) < 1:
                return JsonResponse({
                    'success': False,
                    'error': 'Text too short',
                    'details': {'error': 'Text must be at least 1 characters long'}
                }, status=400)
            
            if len(text) > 10000:
                return JsonResponse({
                    'success': False,
                    'error': 'Text too long',
                    'details': {'error': 'Text must not exceed 10000 characters'}
                }, status=400)

            # Get credit costs for operations
            credit_costs = {
                'count_words': Decimal('0.5'),
                'count_characters': Decimal('0.1'),
                'analyze': Decimal('2.0'),
                'summarize': Decimal('5.0')
            }
            
            credit_cost = credit_costs[operation]

            # Check user credits
            credit_account = CreditAccount.get_or_create_for_user(request.user)
            current_balance = credit_account.get_balance()
            
            if current_balance < credit_cost:
                return JsonResponse({
                    'success': False,
                    'error': f'Insufficient credits. Current balance: {current_balance}, Required: {credit_cost}',
                    'error_code': 'INSUFFICIENT_CREDITS',
                    'data': {
                        'current_balance': str(current_balance),
                        'required_credits': str(credit_cost)
                    }
                }, status=402)

            # Process the text based on operation
            result = self._process_text(text, operation)
            
            # Consume credits and track usage
            try:
                # Get the Text Processing service
                service = Service.objects.get(name='Text Processing')
                
                # Consume credits
                credit_transaction = credit_account.consume_credits_with_priority(
                    amount=credit_cost,
                    description=f'Text processing: {operation}'
                )
                
                # Track service usage
                ServiceUsage.objects.create(
                    user=request.user,
                    service=service,
                    credit_transaction=credit_transaction
                )
                
                # Log successful request
                logger.info(f"Text processing request completed for user {request.user.email}: {operation}")
                
                return JsonResponse({
                    'success': True,
                    'data': {
                        'operation': operation,
                        'result': result,
                        'credits_consumed': str(credit_cost),
                        'remaining_balance': str(credit_account.get_balance())
                    }
                })
                
            except InsufficientCreditsError as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e),
                    'error_code': 'INSUFFICIENT_CREDITS'
                }, status=402)

        except Exception as e:
            logger.error(f"Error processing text request: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Internal server error',
                'details': {'error': str(e)}
            }, status=500)

    def _process_text(self, text, operation):
        """Process text based on the requested operation."""
        if operation == 'count_words':
            word_count = len(text.split())
            return {'word_count': word_count}
        
        elif operation == 'count_characters':
            char_count = len(text)
            char_count_no_spaces = len(text.replace(' ', ''))
            return {
                'character_count': char_count,
                'character_count_no_spaces': char_count_no_spaces
            }
        
        elif operation == 'analyze':
            words = text.split()
            sentences = text.replace('!', '.').replace('?', '.').split('.')
            sentences = [s.strip() for s in sentences if s.strip()]
            
            return {
                'word_count': len(words),
                'character_count': len(text),
                'sentence_count': len(sentences),
                'average_words_per_sentence': round(len(words) / len(sentences), 2) if sentences else 0
            }
        
        elif operation == 'summarize':
            # Simple summarization: take first half of sentences
            sentences = text.replace('!', '.').replace('?', '.').split('.')
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if len(sentences) <= 2:
                summary = text
            else:
                # Take first half of sentences
                summary_sentences = sentences[:len(sentences)//2]
                summary = '. '.join(summary_sentences) + '.'
            
            compression_ratio = len(summary) / len(text) if text else 0
            
            return {
                'summary': summary,
                'original_length': len(text),
                'summary_length': len(summary),
                'compression_ratio': round(compression_ratio, 2)
            }