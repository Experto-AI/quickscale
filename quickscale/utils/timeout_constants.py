"""
Timeout constants for Docker operations and service management.

This module centralizes all timeout configurations used throughout the QuickScale
project to improve maintainability and consistency.
"""

# Docker service timeouts
DOCKER_CONTAINER_START_TIMEOUT = 30  # Timeout for individual container startup
DOCKER_SERVICE_STARTUP_TIMEOUT = 120  # Timeout for full service startup
DOCKER_PS_CHECK_TIMEOUT = 10  # Timeout for docker-compose ps command
DOCKER_PULL_TIMEOUT = 30  # < DOCKER_SERVICE_STARTUP_TIMEOUT

# General Docker operations timeout
DOCKER_OPERATIONS_TIMEOUT = 20  # < DOCKER_CONTAINER_START_TIMEOUT

# PostgreSQL connection check timeout
POSTGRES_CONNECTION_TIMEOUT = 5  # < DOCKER_INFO_TIMEOUT

# Docker info command timeout
DOCKER_INFO_TIMEOUT = 5  # >= POSTGRES_CONNECTION_TIMEOUT

# Docker run operation timeout
DOCKER_RUN_TIMEOUT = 10  # < DOCKER_CONTAINER_START_TIMEOUT