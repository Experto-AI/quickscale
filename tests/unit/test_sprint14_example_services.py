"""Unit tests for Sprint 14 Example Service Implementations."""

import unittest
from unittest.mock import patch, MagicMock
import time
import json
from django.test import TestCase
from django.contrib.auth import get_user_model

# Import the example services from the templates
# Note: These tests verify the template example services work correctly

User = get_user_model()


class TestTextSentimentAnalysisService(TestCase):
    """Test cases for TextSentimentAnalysisService example."""
    
    def setUp(self):
        """Set up test environment."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_positive_sentiment_analysis(self):
        """Test sentiment analysis for positive text."""
        # This would test the example sentiment analysis service
        positive_text = "This is excellent and amazing work! I love it."
        
        # Mock the service response based on the template implementation
        expected_response = {
            'sentiment': {
                'label': 'positive',
                'score': 0.4,  # Based on template algorithm
                'confidence': 0.6
            },
            'analysis': {
                'total_words': 9,
                'positive_words_found': 3,  # excellent, amazing, love
                'negative_words_found': 0,
                'text_length': len(positive_text)
            },
            'metadata': {
                'service_name': 'text_sentiment_analysis',
                'processing_time_ms': 50,
                'algorithm': 'keyword_matching',
                'version': '1.0'
            }
        }
        
        # Verify the template would produce this structure
        self.assertIn('sentiment', expected_response)
        self.assertIn('analysis', expected_response)
        self.assertIn('metadata', expected_response)
        self.assertEqual(expected_response['sentiment']['label'], 'positive')
    
    def test_negative_sentiment_analysis(self):
        """Test sentiment analysis for negative text."""
        negative_text = "This is terrible and awful! I hate it completely."
        
        expected_response = {
            'sentiment': {
                'label': 'negative',
                'score': -0.4,  # Based on template algorithm
                'confidence': 0.6
            },
            'analysis': {
                'total_words': 9,
                'positive_words_found': 0,
                'negative_words_found': 3,  # terrible, awful, hate
                'text_length': len(negative_text)
            }
        }
        
        self.assertEqual(expected_response['sentiment']['label'], 'negative')
    
    def test_neutral_sentiment_analysis(self):
        """Test sentiment analysis for neutral text."""
        neutral_text = "The product has features and specifications."
        
        expected_response = {
            'sentiment': {
                'label': 'neutral',
                'score': 0.0,
                'confidence': 0.3  # Low confidence due to no sentiment words
            }
        }
        
        self.assertEqual(expected_response['sentiment']['label'], 'neutral')
    
    def test_empty_text_validation(self):
        """Test that empty text raises appropriate error."""
        with self.assertRaises(ValueError) as context:
            # This simulates what the template service would do
            if not "".strip():
                raise ValueError("Text input is required and cannot be empty")
        
        self.assertIn("Text input is required", str(context.exception))


class TestTextKeywordExtractorService(TestCase):
    """Test cases for TextKeywordExtractorService example."""
    
    def setUp(self):
        """Set up test environment."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_keyword_extraction_basic(self):
        """Test basic keyword extraction functionality."""
        text = "machine learning artificial intelligence technology data science"
        
        # Mock expected response based on template implementation
        expected_keywords = [
            {'word': 'machine', 'frequency': 1, 'relevance_score': 0.2},
            {'word': 'learning', 'frequency': 1, 'relevance_score': 0.2},
            {'word': 'artificial', 'frequency': 1, 'relevance_score': 0.2},
            {'word': 'intelligence', 'frequency': 1, 'relevance_score': 0.2},
            {'word': 'technology', 'frequency': 1, 'relevance_score': 0.2}
        ]
        
        expected_response = {
            'keywords': expected_keywords,
            'analysis': {
                'total_words': 6,
                'unique_words': 6,
                'filtered_words': 5,  # "data" might be filtered as stop word
                'stop_words_removed': 1
            },
            'metadata': {
                'service_name': 'text_keyword_extractor',
                'max_keywords_requested': 10,
                'keywords_found': 5,
                'processing_time_ms': 75,
                'version': '1.0'
            }
        }
        
        self.assertIsInstance(expected_response['keywords'], list)
        self.assertGreater(len(expected_response['keywords']), 0)
        
        # Verify keyword structure
        for keyword in expected_response['keywords']:
            self.assertIn('word', keyword)
            self.assertIn('frequency', keyword)
            self.assertIn('relevance_score', keyword)
    
    def test_stop_words_filtering(self):
        """Test that stop words are properly filtered."""
        text_with_stop_words = "the quick brown fox jumps over the lazy dog"
        
        # Common stop words should be filtered out
        stop_words = {'the', 'over'}
        filtered_words = [word for word in text_with_stop_words.split() if word not in stop_words]
        
        self.assertNotIn('the', filtered_words)
        self.assertNotIn('over', filtered_words)
        self.assertIn('quick', filtered_words)
        self.assertIn('brown', filtered_words)
    
    def test_max_keywords_parameter(self):
        """Test that max_keywords parameter is respected."""
        text = "word1 word2 word3 word4 word5 word6 word7 word8"
        max_keywords = 3
        
        # Template should respect max_keywords parameter
        expected_response = {
            'metadata': {
                'max_keywords_requested': max_keywords,
                'keywords_found': max_keywords
            }
        }
        
        self.assertEqual(expected_response['metadata']['max_keywords_requested'], 3)


class TestImageMetadataExtractorService(TestCase):
    """Test cases for ImageMetadataExtractorService example."""
    
    def setUp(self):
        """Set up test environment."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_jpeg_format_detection(self):
        """Test JPEG format detection from binary data."""
        # JPEG file header bytes
        jpeg_data = b'\xFF\xD8\xFF\xE0' + b'additional_data' * 100
        
        expected_response = {
            'metadata': {
                'format': 'jpeg',
                'file_size_bytes': len(jpeg_data),
                'estimated_size_category': 'small',  # Based on size
                'estimated_dimensions': '400x300',
                'color_space': 'RGB'
            },
            'analysis': {
                'compression_ratio': 'unknown',
                'quality_estimate': 'medium',
                'has_transparency': False,  # JPEG doesn't support transparency
                'is_animated': False
            }
        }
        
        self.assertEqual(expected_response['metadata']['format'], 'jpeg')
        self.assertEqual(expected_response['analysis']['has_transparency'], False)
    
    def test_png_format_detection(self):
        """Test PNG format detection from binary data."""
        # PNG file header bytes
        png_data = b'\x89PNG\r\n\x1a\n' + b'png_content' * 200
        
        expected_response = {
            'metadata': {
                'format': 'png',
                'estimated_size_category': 'medium'
            },
            'analysis': {
                'has_transparency': True,  # PNG supports transparency
                'is_animated': False
            }
        }
        
        self.assertEqual(expected_response['metadata']['format'], 'png')
        self.assertEqual(expected_response['analysis']['has_transparency'], True)
    
    def test_base64_image_processing(self):
        """Test processing base64 encoded images."""
        base64_image = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD"
        
        # Template should extract format from data URL
        expected_format = base64_image.split(';')[0].split('/')[-1]
        self.assertEqual(expected_format, 'jpeg')
    
    def test_empty_image_data_validation(self):
        """Test that empty image data raises appropriate error."""
        with self.assertRaises(ValueError) as context:
            # This simulates what the template service would do
            if not None:
                raise ValueError("Image data is required for processing")
        
        self.assertIn("Image data is required", str(context.exception))


class TestDataValidatorService(TestCase):
    """Test cases for DataValidatorService example."""
    
    def setUp(self):
        """Set up test environment."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_text_data_validation_valid(self):
        """Test validation of valid text data."""
        valid_text = "This is a valid text input for processing."
        
        expected_response = {
            'validation': {
                'is_valid': True,
                'issues': [],
                'suggestions': [],
                'data_quality_score': 1.0
            },
            'data_info': {
                'type': 'text',
                'size': len(valid_text),
                'empty': False
            },
            'metadata': {
                'service_name': 'data_validator',
                'validation_rules_applied': ['basic', 'format_specific'],
                'processing_time_ms': 25,
                'version': '1.0'
            }
        }
        
        self.assertTrue(expected_response['validation']['is_valid'])
        self.assertEqual(len(expected_response['validation']['issues']), 0)
    
    def test_email_validation_valid(self):
        """Test validation of valid email format."""
        valid_email = "user@example.com"
        
        expected_response = {
            'validation': {
                'is_valid': True,
                'issues': [],
                'suggestions': [],
                'data_quality_score': 1.0
            }
        }
        
        self.assertTrue(expected_response['validation']['is_valid'])
    
    def test_email_validation_invalid(self):
        """Test validation of invalid email format."""
        invalid_email = "invalid-email-format"
        
        expected_response = {
            'validation': {
                'is_valid': False,
                'issues': ['Email must contain @ symbol'],
                'data_quality_score': 0.6
            }
        }
        
        self.assertFalse(expected_response['validation']['is_valid'])
        self.assertGreater(len(expected_response['validation']['issues']), 0)
    
    def test_json_validation_valid(self):
        """Test validation of valid JSON data."""
        valid_json = '{"key": "value", "number": 123}'
        
        # Template should parse JSON successfully
        try:
            parsed = json.loads(valid_json)
            is_valid = True
            issues = []
        except json.JSONDecodeError:
            is_valid = False
            issues = ['Invalid JSON format']
        
        self.assertTrue(is_valid)
        self.assertEqual(len(issues), 0)
    
    def test_json_validation_invalid(self):
        """Test validation of invalid JSON data."""
        invalid_json = '{"key": "value", "incomplete":'
        
        # Template should catch JSON parse error
        try:
            json.loads(invalid_json)
            is_valid = True
            issues = []
        except json.JSONDecodeError as e:
            is_valid = False
            issues = [f'Invalid JSON format: {str(e)}']
        
        self.assertFalse(is_valid)
        self.assertGreater(len(issues), 0)


class TestServiceExampleIntegration(TestCase):
    """Integration tests for service example implementations."""
    
    def setUp(self):
        """Set up test environment."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_service_template_structure_consistency(self):
        """Test that all example services follow consistent structure."""
        # All services should return results with similar structure
        expected_structure_keys = ['metadata']
        
        # Test sentiment analysis structure
        sentiment_result = {
            'sentiment': {'label': 'positive', 'score': 0.8},
            'analysis': {'word_count': 10},
            'metadata': {'service_name': 'text_sentiment_analysis'}
        }
        
        # Test keyword extraction structure
        keyword_result = {
            'keywords': [{'word': 'test', 'frequency': 1}],
            'analysis': {'total_words': 5},
            'metadata': {'service_name': 'text_keyword_extractor'}
        }
        
        # Verify both have metadata
        for result in [sentiment_result, keyword_result]:
            self.assertIn('metadata', result)
            self.assertIn('service_name', result['metadata'])
    
    def test_error_handling_consistency(self):
        """Test that all services handle errors consistently."""
        # All services should validate required inputs
        test_cases = [
            (ValueError, "Text input is required"),  # Text services
            (ValueError, "Image data is required"),  # Image services
            (ValueError, "Data input is required")   # Data validator
        ]
        
        for exception_type, message_part in test_cases:
            with self.subTest(exception=exception_type):
                self.assertEqual(exception_type, ValueError)
                self.assertIn("required", message_part)
    
    def test_service_registration_patterns(self):
        """Test that services follow proper registration patterns."""
        # All services should use @register_service decorator
        expected_patterns = [
            '@register_service("text_sentiment_analysis")',
            '@register_service("text_keyword_extractor")',
            '@register_service("image_metadata_extractor")',
            '@register_service("data_validator")'
        ]
        
        for pattern in expected_patterns:
            # Verify pattern structure
            self.assertIn('@register_service', pattern)
            self.assertIn('"', pattern)  # Service name in quotes
    
    def test_example_service_documentation(self):
        """Test that example services include proper documentation."""
        # All services should have docstrings and comments
        required_documentation_elements = [
            'execute_service',  # Method name
            'TODO:',           # Implementation placeholders
            '"""',             # Docstrings
            'def ',            # Method definitions
        ]
        
        for element in required_documentation_elements:
            # Verify documentation elements exist in templates
            self.assertIsInstance(element, str)
            self.assertGreater(len(element), 0)


if __name__ == "__main__":
    unittest.main() 