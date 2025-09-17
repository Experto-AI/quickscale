"""
Unit tests for timeout constants module.

Tests the centralized timeout configuration to ensure maintainability
and consistency across Docker operations.
"""

from quickscale.utils.timeout_constants import (
    DOCKER_CONTAINER_START_TIMEOUT,
    DOCKER_INFO_TIMEOUT,
    DOCKER_OPERATIONS_TIMEOUT,
    DOCKER_PS_CHECK_TIMEOUT,
    DOCKER_PULL_TIMEOUT,
    DOCKER_RUN_TIMEOUT,
    DOCKER_SERVICE_STARTUP_TIMEOUT,
    POSTGRES_CONNECTION_TIMEOUT,
)


class TestTimeoutConstants:
    """Test timeout constant values and their relationships."""
    
    def test_docker_service_startup_timeout_is_reasonable(self):
        """Test that Docker service startup timeout is reasonable."""
        # Should be 5 minutes for e2e tests with fresh builds - increased from 180 to handle Docker timeouts
        assert DOCKER_SERVICE_STARTUP_TIMEOUT == 300
        assert DOCKER_SERVICE_STARTUP_TIMEOUT >= 180 
    
    def test_docker_ps_check_timeout_is_short(self):
        """Test that Docker ps check timeout is short."""
        # Should be quick for status checks
        assert DOCKER_PS_CHECK_TIMEOUT == 10
        assert DOCKER_PS_CHECK_TIMEOUT < 60  # Should be under 1 minute
    
    def test_docker_container_start_timeout_is_medium(self):
        """Test that Docker container start timeout is medium."""
        # Should be reasonable for container startup - increased from 40 to 60 for reliability
        assert DOCKER_CONTAINER_START_TIMEOUT == 60
        assert 20 <= DOCKER_CONTAINER_START_TIMEOUT <= 60
    
    def test_docker_operations_timeout_is_short(self):
        """Test that general Docker operations timeout is short."""
        # Increased from 20 to 30 for better reliability
        assert DOCKER_OPERATIONS_TIMEOUT == 30
        assert DOCKER_OPERATIONS_TIMEOUT < 60  # Should be under 1 minute
    
    def test_postgres_connection_timeout_is_short(self):
        """Test that PostgreSQL connection timeout is short."""
        assert POSTGRES_CONNECTION_TIMEOUT == 5
        assert POSTGRES_CONNECTION_TIMEOUT < 30  # Should be under 30s
    
    def test_docker_info_timeout_is_very_short(self):
        """Test that Docker info timeout is very short."""
        assert DOCKER_INFO_TIMEOUT == 5
        assert DOCKER_INFO_TIMEOUT < 10  # Should be under 10s
    
    def test_docker_pull_timeout_is_medium(self):
        """Test that Docker pull timeout is medium length or can be overridden by environment variable."""
        # Default should be 120, but can be overridden by QUICKSCALE_DOCKER_PULL_TIMEOUT
        import os
        expected_default = 120
        env_override = os.environ.get('QUICKSCALE_DOCKER_PULL_TIMEOUT')
        
        if env_override:
            # If environment variable is set, DOCKER_PULL_TIMEOUT should match it
            assert DOCKER_PULL_TIMEOUT == int(env_override)
        else:
            # If no environment variable, should be default
            assert DOCKER_PULL_TIMEOUT == expected_default
            
        # Regardless of source, should be within reasonable bounds
        assert 15 <= DOCKER_PULL_TIMEOUT <= 600  # Between 15s and 10min
    
    def test_docker_run_timeout_is_short(self):
        """Test that Docker run timeout is short."""
        assert DOCKER_RUN_TIMEOUT == 10
        assert 5 <= DOCKER_RUN_TIMEOUT <= 30  # Between 5s and 30s
    
    def test_timeout_hierarchy_makes_sense(self):
        """Test that timeout values follow a logical hierarchy."""
        # Startup should be longest
        assert DOCKER_SERVICE_STARTUP_TIMEOUT > DOCKER_CONTAINER_START_TIMEOUT
        
        # Container start should be longer than general operations
        assert DOCKER_CONTAINER_START_TIMEOUT > DOCKER_OPERATIONS_TIMEOUT
        
        # General operations should be at least as long as quick checks
        assert DOCKER_OPERATIONS_TIMEOUT >= DOCKER_PS_CHECK_TIMEOUT
        
        # Quick checks should be longer than very quick checks
        assert DOCKER_PS_CHECK_TIMEOUT > DOCKER_INFO_TIMEOUT
        
        # Very quick checks should be longer than connection timeouts
        assert DOCKER_INFO_TIMEOUT >= POSTGRES_CONNECTION_TIMEOUT
    
    def test_all_timeouts_are_positive(self):
        """Test that all timeout values are positive integers."""
        timeouts = [
            DOCKER_SERVICE_STARTUP_TIMEOUT,
            DOCKER_PS_CHECK_TIMEOUT,
            DOCKER_CONTAINER_START_TIMEOUT,
            DOCKER_OPERATIONS_TIMEOUT,
            POSTGRES_CONNECTION_TIMEOUT,
            DOCKER_INFO_TIMEOUT,
            DOCKER_PULL_TIMEOUT,
            DOCKER_RUN_TIMEOUT
        ]
        
        for timeout in timeouts:
            assert isinstance(timeout, int)
            assert timeout > 0 
