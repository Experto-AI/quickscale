"""
Test environment configuration utilities.

Provides reusable fixtures and utilities for configuring test environments
with appropriate timeouts and settings without polluting global test runner.
"""
import os
from contextlib import contextmanager
from typing import Dict, Optional

import pytest


@contextmanager
def docker_timeout_context(pull_timeout: int = 300, compose_timeout: int = 180):
    """
    Context manager for setting Docker timeout environment variables.
    
    Args:
        pull_timeout: Timeout for docker pull operations in seconds (default 300 = 5 minutes)
        compose_timeout: Timeout for docker-compose operations in seconds (default 180 = 3 minutes)
    """
    # Store original values
    original_values = {
        'QUICKSCALE_DOCKER_PULL_TIMEOUT': os.environ.get('QUICKSCALE_DOCKER_PULL_TIMEOUT'),
        'COMPOSE_HTTP_TIMEOUT': os.environ.get('COMPOSE_HTTP_TIMEOUT'),
        'DOCKER_CLIENT_TIMEOUT': os.environ.get('DOCKER_CLIENT_TIMEOUT'),
    }
    
    try:
        # Set extended timeouts
        os.environ['QUICKSCALE_DOCKER_PULL_TIMEOUT'] = str(pull_timeout)
        os.environ['COMPOSE_HTTP_TIMEOUT'] = str(compose_timeout)
        os.environ['DOCKER_CLIENT_TIMEOUT'] = str(compose_timeout)
        
        yield
        
    finally:
        # Restore original values
        for key, value in original_values.items():
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)


@pytest.fixture(scope="module")
def extended_docker_timeouts():
    """
    Pytest fixture providing extended Docker timeouts for E2E tests.
    
    Use this fixture for tests that perform real Docker operations like
    pulling images or starting containers.
    """
    with docker_timeout_context(pull_timeout=300, compose_timeout=180):
        yield


@pytest.fixture  
def fast_docker_timeouts():
    """
    Pytest fixture providing reduced Docker timeouts for fast unit tests.
    
    Use this fixture for tests that mock Docker operations and should fail
    fast if they accidentally hit real Docker.
    """
    with docker_timeout_context(pull_timeout=30, compose_timeout=30):
        yield


def configure_test_environment(
    docker_pull_timeout: Optional[int] = None,
    compose_timeout: Optional[int] = None,
    test_flags: Optional[Dict[str, str]] = None
):
    """
    Configure test environment with specific settings.
    
    Args:
        docker_pull_timeout: Override for QUICKSCALE_DOCKER_PULL_TIMEOUT
        compose_timeout: Override for COMPOSE_HTTP_TIMEOUT and DOCKER_CLIENT_TIMEOUT
        test_flags: Dictionary of additional test environment variables
    """
    if docker_pull_timeout is not None:
        os.environ['QUICKSCALE_DOCKER_PULL_TIMEOUT'] = str(docker_pull_timeout)
        
    if compose_timeout is not None:
        os.environ['COMPOSE_HTTP_TIMEOUT'] = str(compose_timeout)
        os.environ['DOCKER_CLIENT_TIMEOUT'] = str(compose_timeout)
        
    if test_flags:
        for key, value in test_flags.items():
            os.environ[key] = str(value)