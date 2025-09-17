"""
Timeout constants for Docker operations and service management.

This module centralizes all timeout configurations used throughout the QuickScale
project to improve maintainability and consistency.
"""
import os

# Docker service timeouts
DOCKER_CONTAINER_START_TIMEOUT = 60   # Timeout for individual container startup
DOCKER_SERVICE_STARTUP_TIMEOUT = 300  # Timeout for starting services (after images are ready)
DOCKER_PS_CHECK_TIMEOUT = 10          # Timeout for docker-compose ps command

# Building and pulling images can be slow on first run or slow networks
DOCKER_BUILD_TIMEOUT = 600     # Generous timeout for building the web image

# Allow environment variable override for Docker pull timeout (especially useful for E2E tests)
DOCKER_PULL_TIMEOUT = int(os.environ.get('QUICKSCALE_DOCKER_PULL_TIMEOUT', 120))  # Default 120, overridable for tests

# General Docker operations timeout
DOCKER_OPERATIONS_TIMEOUT = 30  # < DOCKER_CONTAINER_START_TIMEOUT

# PostgreSQL connection check timeout
POSTGRES_CONNECTION_TIMEOUT = 5  # < DOCKER_INFO_TIMEOUT

# Docker info command timeout
DOCKER_INFO_TIMEOUT = 5  # >= POSTGRES_CONNECTION_TIMEOUT

# Docker run operation timeout
DOCKER_RUN_TIMEOUT = 10  # < DOCKER_CONTAINER_START_TIMEOUT
