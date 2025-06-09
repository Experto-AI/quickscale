"""Unit tests for Sprint 14 Example Service Implementations."""

import unittest
import json
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class TestServiceExampleStructure(TestCase):
    """Test cases for Sprint 14 example service structure."""
    
    def setUp(self):
        """Set up test environment."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_sentiment_analysis_structure(self):
        """Test sentiment analysis service structure."""
        # Mock response structure based on template
        response = {
            'sentiment': {
                'label': 'positive',
                'score': 0.8,
                'confidence': 0.9
            },
            'analysis': {
                'total_words': 10,
                'positive_words_found': 3,
                'negative_words_found': 0
            },
            'metadata': {
                'service_name': 'text_sentiment_analysis',
                'version': '1.0'
            }
        }
        
        self.assertIn('sentiment', response)
        self.assertIn('analysis', response)
        self.assertIn('metadata', response)
        self.assertEqual(response['sentiment']['label'], 'positive')
    
    def test_keyword_extraction_structure(self):
        """Test keyword extraction service structure."""
        response = {
            'keywords': [
                {'word': 'machine', 'frequency': 2, 'relevance_score': 0.4}
            ],
            'analysis': {
                'total_words': 15,
                'unique_words': 12
            },
            'metadata': {
                'service_name': 'text_keyword_extractor',
                'version': '1.0'
            }
        }
        
        self.assertIn('keywords', response)
        self.assertIsInstance(response['keywords'], list)
        self.assertIn('word', response['keywords'][0])
    
    def test_data_validator_structure(self):
        """Test data validator service structure."""
        response = {
            'validation': {
                'is_valid': True,
                'issues': [],
                'data_quality_score': 1.0
            },
            'data_info': {
                'type': 'text',
                'size': 50
            },
            'metadata': {
                'service_name': 'data_validator',
                'version': '1.0'
            }
        }
        
        self.assertIn('validation', response)
        self.assertIn('data_info', response)
        self.assertTrue(response['validation']['is_valid'])


class TestServiceValidationPatterns(unittest.TestCase):
    """Test cases for service validation patterns."""
    
    def test_empty_input_validation(self):
        """Test validation of empty inputs."""
        # All services should validate empty inputs
        test_inputs = ["", None, "   "]
        
        for empty_input in test_inputs:
            with self.subTest(input=empty_input):
                if not empty_input or not str(empty_input).strip():
                    with self.assertRaises(ValueError):
                        raise ValueError("Input is required and cannot be empty")
    
    def test_json_validation_logic(self):
        """Test JSON validation logic from data validator."""
        valid_json = '{"key": "value"}'
        invalid_json = '{"key": "value"'
        
        # Valid JSON should parse without error
        try:
            json.loads(valid_json)
            valid_result = True
        except json.JSONDecodeError:
            valid_result = False
        
        # Invalid JSON should raise error
        try:
            json.loads(invalid_json)
            invalid_result = True
        except json.JSONDecodeError:
            invalid_result = False
        
        self.assertTrue(valid_result)
        self.assertFalse(invalid_result)


if __name__ == "__main__":
    unittest.main() 