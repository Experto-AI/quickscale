"""
Test utilities for QuickScale testing.

This module provides utilities for dynamic project generation and testing,
replacing static fixtures with live project generation.
"""

from .dynamic_project_generator import (
    DynamicProjectGenerator,
    create_dynamic_test_project,
    with_dynamic_project
)

from .dynamic_test_base import (
    DynamicProjectTestCase,
    DynamicDjangoTestCase,
    DynamicTemplateTestCase
)

# Import utility functions from the main utils.py file
import sys
from pathlib import Path

__all__ = [
    'DynamicProjectGenerator',
    'create_dynamic_test_project', 
    'with_dynamic_project',
    'DynamicProjectTestCase',
    'DynamicDjangoTestCase',
    'DynamicTemplateTestCase',
    # Note: Utility functions from tests/utils.py should be imported directly:
    # from tests.utils.utils import function_name 
    # OR import tests.utils.utils as test_utils
]
