"""
Example implementations showing how to use the AI Service Framework.

This file demonstrates how AI engineers can create services that integrate
with the existing credit system using the BaseService class and @register_service decorator.

These examples show common patterns for AI services including:
- Text processing and analysis
- Image processing and classification
- External API integration
- Error handling and validation
- Performance optimization techniques
"""

import time
import json
from typing import Dict, Any, List, Optional, Union
from decimal import Decimal

from .base import BaseService
from .decorators import register_service
from django.contrib.auth import get_user_model

User = get_user_model()


@register_service("text_sentiment_analysis")
class TextSentimentAnalysisService(BaseService):
    """Advanced text sentiment analysis service with keyword-based scoring."""
    
    def execute_service(self, user: User, text: str = "", **kwargs) -> Dict[str, Any]:
        """Analyze sentiment of text using keyword matching and scoring."""
        if not text or not text.strip():
            raise ValueError("Text input is required and cannot be empty")
        
        # Simple sentiment analysis using keyword matching
        positive_words = {
            'excellent', 'amazing', 'wonderful', 'fantastic', 'great', 'good', 'love', 
            'awesome', 'brilliant', 'perfect', 'outstanding', 'superb', 'happy', 'pleased'
        }
        negative_words = {
            'terrible', 'awful', 'horrible', 'bad', 'hate', 'disappointing', 'worst',
            'useless', 'frustrating', 'annoying', 'poor', 'sad', 'angry', 'disappointed'
        }
        
        # Preprocessing
        words = text.lower().split()
        total_words = len(words)
        
        # Count sentiment words
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        # Calculate sentiment score (-1 to 1)
        if total_words > 0:
            sentiment_score = (positive_count - negative_count) / total_words
        else:
            sentiment_score = 0.0
        
        # Determine sentiment label
        if sentiment_score > 0.1:
            sentiment_label = "positive"
        elif sentiment_score < -0.1:
            sentiment_label = "negative"
        else:
            sentiment_label = "neutral"
        
        # Calculate confidence based on sentiment word density
        sentiment_word_density = (positive_count + negative_count) / max(total_words, 1)
        confidence = min(0.9, max(0.3, sentiment_word_density * 2))
        
        return {
            'sentiment': {
                'label': sentiment_label,
                'score': round(sentiment_score, 3),
                'confidence': round(confidence, 3)
            },
            'analysis': {
                'total_words': total_words,
                'positive_words_found': positive_count,
                'negative_words_found': negative_count,
                'text_length': len(text)
            },
            'metadata': {
                'service_name': 'text_sentiment_analysis',
                'processing_time_ms': 50,  # Simulated processing time
                'algorithm': 'keyword_matching',
                'version': '1.0'
            }
        }


@register_service("text_keyword_extractor")
class TextKeywordExtractorService(BaseService):
    """Service to extract important keywords from text."""
    
    def execute_service(self, user: User, text: str = "", max_keywords: int = 10, **kwargs) -> Dict[str, Any]:
        """Extract keywords from text using frequency analysis."""
        if not text or not text.strip():
            raise ValueError("Text input is required and cannot be empty")
        
        # Common stop words to filter out
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 
            'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 
            'after', 'above', 'below', 'between', 'among', 'throughout', 'despite', 
            'towards', 'upon', 'concerning', 'is', 'are', 'was', 'were', 'be', 'been', 
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 
            'should', 'may', 'might', 'must', 'shall', 'can', 'this', 'that', 'these', 
            'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 
            'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their'
        }
        
        # Process text
        words = text.lower().replace('.', '').replace(',', '').replace('!', '').replace('?', '').split()
        
        # Filter words
        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Count word frequencies
        word_freq = {}
        for word in filtered_words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Sort by frequency and get top keywords
        sorted_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        top_keywords = sorted_keywords[:max_keywords]
        
        return {
            'keywords': [
                {
                    'word': word,
                    'frequency': freq,
                    'relevance_score': round(freq / len(filtered_words), 3)
                }
                for word, freq in top_keywords
            ],
            'analysis': {
                'total_words': len(words),
                'unique_words': len(set(words)),
                'filtered_words': len(filtered_words),
                'stop_words_removed': len(words) - len(filtered_words)
            },
            'metadata': {
                'service_name': 'text_keyword_extractor',
                'max_keywords_requested': max_keywords,
                'keywords_found': len(top_keywords),
                'processing_time_ms': 75,
                'version': '1.0'
            }
        }


@register_service("image_metadata_extractor")
class ImageMetadataExtractorService(BaseService):
    """Service to extract metadata from image data."""
    
    def execute_service(self, user: User, image_data: Union[str, bytes] = None, **kwargs) -> Dict[str, Any]:
        """Extract basic metadata from image data."""
        if not image_data:
            raise ValueError("Image data is required for processing")
        
        # Simulate image processing
        start_time = time.time()
        
        # Basic analysis based on data size and format hints
        if isinstance(image_data, str):
            # Assume base64 encoded or file path
            data_size = len(image_data)
            if image_data.startswith('data:image/'):
                format_hint = image_data.split(';')[0].split('/')[-1]
            else:
                format_hint = 'unknown'
        else:
            # Binary data
            data_size = len(image_data)
            # Try to detect format from binary headers
            if image_data.startswith(b'\xFF\xD8\xFF'):
                format_hint = 'jpeg'
            elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):
                format_hint = 'png'
            elif image_data.startswith(b'GIF8'):
                format_hint = 'gif'
            else:
                format_hint = 'unknown'
        
        # Estimate dimensions based on file size (very rough estimation)
        if data_size < 50000:  # < 50KB
            estimated_size = 'small'
            estimated_dimensions = '400x300'
        elif data_size < 500000:  # < 500KB
            estimated_size = 'medium'
            estimated_dimensions = '800x600'
        else:
            estimated_size = 'large'
            estimated_dimensions = '1920x1080'
        
        processing_time = round((time.time() - start_time) * 1000, 2)
        
        return {
            'metadata': {
                'format': format_hint,
                'file_size_bytes': data_size,
                'estimated_size_category': estimated_size,
                'estimated_dimensions': estimated_dimensions,
                'color_space': 'RGB',  # Default assumption
            },
            'analysis': {
                'compression_ratio': 'unknown',
                'quality_estimate': 'medium',
                'has_transparency': format_hint in ['png', 'gif'],
                'is_animated': format_hint == 'gif'
            },
            'metadata': {
                'service_name': 'image_metadata_extractor',
                'processing_time_ms': processing_time,
                'algorithm': 'header_analysis',
                'version': '1.0'
            }
        }


@register_service("data_validator")
class DataValidatorService(BaseService):
    """Service to validate and clean various types of data."""
    
    def execute_service(self, user: User, data: Any = None, data_type: str = "text", **kwargs) -> Dict[str, Any]:
        """Validate and analyze data quality."""
        if data is None:
            raise ValueError("Data input is required")
        
        validation_result = {
            'is_valid': True,
            'issues': [],
            'suggestions': [],
            'data_quality_score': 1.0
        }
        
        if data_type == "text":
            validation_result.update(self._validate_text_data(data))
        elif data_type == "email":
            validation_result.update(self._validate_email_data(data))
        elif data_type == "json":
            validation_result.update(self._validate_json_data(data))
        else:
            validation_result.update(self._validate_generic_data(data))
        
        return {
            'validation': validation_result,
            'data_info': {
                'type': data_type,
                'size': len(str(data)),
                'empty': not bool(data)
            },
            'metadata': {
                'service_name': 'data_validator',
                'validation_rules_applied': ['basic', 'format_specific'],
                'processing_time_ms': 25,
                'version': '1.0'
            }
        }
    
    def _validate_text_data(self, text: str) -> Dict[str, Any]:
        """Validate text data."""
        issues = []
        suggestions = []
        quality_score = 1.0
        
        if not isinstance(text, str):
            issues.append("Data is not a string")
            quality_score -= 0.5
        else:
            if len(text.strip()) == 0:
                issues.append("Text is empty or contains only whitespace")
                quality_score -= 0.3
            
            if len(text) > 10000:
                suggestions.append("Text is very long, consider chunking for better processing")
            
            # Check for common encoding issues
            try:
                text.encode('utf-8')
            except UnicodeEncodeError:
                issues.append("Text contains invalid Unicode characters")
                quality_score -= 0.2
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'suggestions': suggestions,
            'data_quality_score': max(0.0, quality_score)
        }
    
    def _validate_email_data(self, email: str) -> Dict[str, Any]:
        """Validate email format."""
        issues = []
        suggestions = []
        quality_score = 1.0
        
        if not isinstance(email, str):
            issues.append("Email must be a string")
            quality_score -= 0.5
        else:
            email = email.strip()
            if '@' not in email:
                issues.append("Email must contain @ symbol")
                quality_score -= 0.4
            elif email.count('@') > 1:
                issues.append("Email contains multiple @ symbols")
                quality_score -= 0.3
            
            if '.' not in email.split('@')[-1] if '@' in email else False:
                issues.append("Email domain must contain a dot")
                quality_score -= 0.3
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'suggestions': suggestions,
            'data_quality_score': max(0.0, quality_score)
        }
    
    def _validate_json_data(self, data: str) -> Dict[str, Any]:
        """Validate JSON format."""
        issues = []
        suggestions = []
        quality_score = 1.0
        
        try:
            parsed = json.loads(data)
            if len(str(parsed)) > 100000:
                suggestions.append("JSON data is very large, consider pagination")
        except json.JSONDecodeError as e:
            issues.append(f"Invalid JSON format: {str(e)}")
            quality_score -= 0.6
        except TypeError:
            issues.append("Data is not JSON serializable")
            quality_score -= 0.5
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'suggestions': suggestions,
            'data_quality_score': max(0.0, quality_score)
        }
    
    def _validate_generic_data(self, data: Any) -> Dict[str, Any]:
        """Generic data validation."""
        return {
            'is_valid': True,
            'issues': [],
            'suggestions': ["Consider specifying a more specific data_type for better validation"],
            'data_quality_score': 0.8
        }


# Advanced usage examples and patterns
"""
# Advanced Usage Patterns for QuickScale AI Services

## 1. Service Chaining Example
def process_text_pipeline(user, text):
    '''Chain multiple services together.'''
    
    # Step 1: Validate the input
    validator = create_service_instance("data_validator")
    validation_result = validator.run(user, data=text, data_type="text")
    
    if not validation_result['result']['validation']['is_valid']:
        return {'error': 'Input validation failed', 'details': validation_result}
    
    # Step 2: Extract keywords
    extractor = create_service_instance("text_keyword_extractor")
    keywords_result = extractor.run(user, text=text, max_keywords=5)
    
    # Step 3: Analyze sentiment
    sentiment_analyzer = create_service_instance("text_sentiment_analysis")
    sentiment_result = sentiment_analyzer.run(user, text=text)
    
    return {
        'pipeline_result': {
            'validation': validation_result['result'],
            'keywords': keywords_result['result'],
            'sentiment': sentiment_result['result']
        },
        'total_credits_consumed': (
            validation_result['credits_consumed'] + 
            keywords_result['credits_consumed'] + 
            sentiment_result['credits_consumed']
        )
    }

## 2. Batch Processing Example
def batch_process_texts(user, texts: List[str], service_name: str):
    '''Process multiple texts efficiently.'''
    
    service = create_service_instance(service_name)
    if not service:
        return {'error': f'Service {service_name} not found'}
    
    # Check total credits needed
    credit_check = service.check_user_credits(user)
    total_credits_needed = credit_check['required_credits'] * len(texts)
    
    if credit_check['available_credits'] < total_credits_needed:
        return {
            'error': 'Insufficient credits for batch processing',
            'needed': total_credits_needed,
            'available': credit_check['available_credits']
        }
    
    # Process batch
    results = []
    total_consumed = 0
    
    for i, text in enumerate(texts):
        try:
            result = service.run(user, text=text)
            results.append({
                'index': i,
                'result': result['result'],
                'success': True
            })
            total_consumed += result['credits_consumed']
        except Exception as e:
            results.append({
                'index': i,
                'error': str(e),
                'success': False
            })
    
    return {
        'batch_results': results,
        'total_processed': len(texts),
        'successful': sum(1 for r in results if r['success']),
        'total_credits_consumed': total_consumed
    }

## 3. Error Handling with Retry Logic
def robust_service_call(user, service_name: str, max_retries: int = 3, **kwargs):
    '''Call a service with retry logic for transient errors.'''
    
    service = create_service_instance(service_name)
    if not service:
        return {'error': f'Service {service_name} not found'}
    
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            result = service.run(user, **kwargs)
            if attempt > 0:
                # Log successful retry
                result['retry_info'] = {
                    'attempts': attempt + 1,
                    'succeeded_on_retry': True
                }
            return result
            
        except InsufficientCreditsError:
            # Don't retry credit errors
            return {'error': 'Insufficient credits', 'retry_attempted': False}
            
        except ValueError as e:
            # Don't retry validation errors
            return {'error': f'Validation error: {str(e)}', 'retry_attempted': False}
            
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                # Wait before retry (exponential backoff)
                time.sleep(2 ** attempt)
                continue
            else:
                return {
                    'error': f'Service failed after {max_retries + 1} attempts: {str(last_error)}',
                    'retry_attempted': True,
                    'total_attempts': max_retries + 1
                }

## 4. Service Performance Monitoring
def monitored_service_call(user, service_name: str, **kwargs):
    '''Call a service with performance monitoring.'''
    
    start_time = time.time()
    service = create_service_instance(service_name)
    
    if not service:
        return {'error': f'Service {service_name} not found'}
    
    try:
        result = service.run(user, **kwargs)
        
        # Add performance metrics
        execution_time = time.time() - start_time
        result['performance'] = {
            'execution_time_seconds': round(execution_time, 3),
            'credits_per_second': round(result['credits_consumed'] / execution_time, 2),
            'service_name': service_name,
            'timestamp': time.time()
        }
        
        return result
        
    except Exception as e:
        execution_time = time.time() - start_time
        return {
            'error': str(e),
            'performance': {
                'execution_time_seconds': round(execution_time, 3),
                'failed': True,
                'service_name': service_name,
                'timestamp': time.time()
            }
        }
"""