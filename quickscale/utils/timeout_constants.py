"""
Timeout constants for Docker operations and service management.

This module centralizes all timeout configurations used throughout the QuickScale
project to improve maintainability and consistency.
"""

# Docker service startup timeout
DOCKER_SERVICE_STARTUP_TIMEOUT = 60  # > DOCKER_CONTAINER_START_TIMEOUT

# Docker ps command timeout for checking service status 
DOCKER_PS_CHECK_TIMEOUT = 20  # < DOCKER_OPERATIONS_TIMEOUT

# Docker container start timeout
DOCKER_CONTAINER_START_TIMEOUT = 30  # > DOCKER_OPERATIONS_TIMEOUT

# General Docker operations timeout
DOCKER_OPERATIONS_TIMEOUT = 20  # < DOCKER_CONTAINER_START_TIMEOUT

# Service stabilization delay after startup
SERVICE_STABILIZATION_DELAY = 15

# Retry pause delay between attempts 
RETRY_PAUSE_DELAY = 2

# PostgreSQL connection check timeout
POSTGRES_CONNECTION_TIMEOUT = 5  # < DOCKER_INFO_TIMEOUT

# Docker info command timeout
DOCKER_INFO_TIMEOUT = 5  # >= POSTGRES_CONNECTION_TIMEOUT

# Docker pull operation timeout
DOCKER_PULL_TIMEOUT = 30  # < DOCKER_SERVICE_STARTUP_TIMEOUT

# Docker run operation timeout
DOCKER_RUN_TIMEOUT = 10  # < DOCKER_CONTAINER_START_TIMEOUT