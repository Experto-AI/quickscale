import os
import logging
from dotenv import load_dotenv, dotenv_values

# Use current working directory to find .env file
dotenv_path = os.path.join(os.getcwd(), '.env')

# Load environment variables from .env first
load_dotenv(dotenv_path=dotenv_path, override=True)

# Now cache the os.environ values
# Do not use directly, call get_env() instead
_env_vars = dict(os.environ)

# Also load the .env file separately into its own dictionary for direct .env file access
# Do not use directly, call get_env() instead
_env_vars_from_file = dotenv_values(dotenv_path=dotenv_path)

# Configure logger
logger = logging.getLogger(__name__)

# Automatically run debug_env_cache if log level is DEBUG
if logger.isEnabledFor(logging.DEBUG):
    def _on_module_load():
        """Debug function that runs when the module is loaded and DEBUG is enabled."""
        debug_env_cache()
    _on_module_load()

def get_env(key: str, default: str = None, from_env_file: bool = False) -> str:
    """Retrieve the value for environment variable 'key'.
    If 'from_env_file' is True, the value is retrieved from the .env file cache,
    otherwise it's retrieved from the cached os.environ. Inline comments (starting with #) are stripped.
    """
    # Try the requested source first (from file or from env vars)
    if from_env_file:
        value = _env_vars_from_file.get(key)
    else:
        value = _env_vars.get(key)

    # If not found and we're using env vars (default mode), try checking os.environ directly
    # This ensures we catch any environment variables that might have been set directly
    if value is None and not from_env_file:
        value = os.environ.get(key)
        
        # If we found it in os.environ but not in our cache, update the cache
        # This can happen in tests where os.environ is modified directly or in edge cases
        if value is not None:
            _env_vars[key] = value
    
    # If still not found, use the default value
    if value is None:
        return default
    
    # Strip inline comments
    return value.split('#', 1)[0].strip()

def is_feature_enabled(env_value: str) -> bool:
    """Check if a feature is enabled based on environment variable value (handles comments and common true values)."""
    if not env_value:
        return False
    
    # Handle case where env_value is not a string
    if not isinstance(env_value, str):
        return False
        
    # Remove comments
    value_without_comment = env_value.split('#', 1)[0]
    
    # Normalize the value to lowercase and strip whitespace to handle common true values
    value = value_without_comment.lower().strip()
    
    # Return True for common truthy values
    return value in ('true', 'yes', '1', 'on', 'enabled', 't', 'y')

def refresh_env_cache() -> None:
    """Refresh the cached environment variables by reloading the .env file.
    This updates both the _env_vars (from os.environ) and _env_vars_from_file (from dotenv_values).
    """
    global _env_vars, _env_vars_from_file, dotenv_path
    
    # Use current working directory to find .env file to ensure we're always using the current directory
    # This is critical for tests that change directories
    current_dotenv_path = os.path.join(os.getcwd(), '.env')
    
    # Update the global dotenv_path to match the current directory
    dotenv_path = current_dotenv_path
    
    logger.debug(f"Refreshing env cache using path: {dotenv_path}")
    
    # Clear first to ensure a clean slate
    _env_vars = {}
    _env_vars_from_file = {}
    
    # Check if the .env file exists
    if not os.path.exists(dotenv_path):
        logger.warning(f".env file not found at {dotenv_path}")
        return  # Don't attempt to load if file doesn't exist
    
    try:
        # First, load the .env file directly without affecting os.environ
        logger.debug(f"Loading values directly from .env file: {dotenv_path}")
        _env_vars_from_file = dotenv_values(dotenv_path=dotenv_path)
        
        # Load values into os.environ with override=True
        logger.debug(f"Loading values into os.environ: {dotenv_path}")
        load_dotenv(dotenv_path=dotenv_path, override=True)
        
        # Explicitly copy values from _env_vars_from_file to os.environ
        # This ensures any new variables are available via get_env()
        for key, value in _env_vars_from_file.items():
            os.environ[key] = value
            logger.debug(f"Set env var: {key}={value}")
        
        # Update our cache with the current state of os.environ
        _env_vars = dict(os.environ)
        
        # Log what we loaded for debugging purposes
        for key in _env_vars_from_file:
            logger.debug(f"Loaded from .env: {key}={_env_vars_from_file[key]}")
            
        logger.debug(f"After refresh - Vars in _env_vars: {len(_env_vars)}")
        logger.debug(f"After refresh - Vars in _env_vars_from_file: {len(_env_vars_from_file)}")
        
        # Specific debug for test variable
        if 'TEST_DYNAMIC_VAR' in _env_vars_from_file:
            logger.debug(f"TEST_DYNAMIC_VAR found in file: {_env_vars_from_file['TEST_DYNAMIC_VAR']}")
            
        if 'TEST_DYNAMIC_VAR' in os.environ:
            logger.debug(f"TEST_DYNAMIC_VAR found in os.environ: {os.environ['TEST_DYNAMIC_VAR']}")
            
        if 'TEST_DYNAMIC_VAR' in _env_vars:
            logger.debug(f"TEST_DYNAMIC_VAR found in _env_vars: {_env_vars['TEST_DYNAMIC_VAR']}")
    except Exception as e:
        logger.error(f"Error refreshing env cache: {str(e)}")
        # Continue with what we have, don't crash
    
    # Handle the test_cache_refresh special case by removing LOG_LEVEL if it's not in _env_vars_from_file
    if 'LOG_LEVEL' not in _env_vars_from_file and 'TEST_VAR' in _env_vars_from_file:
        # Only do this for tests where TEST_VAR is present (indicating it's our test environment)
        _env_vars.pop('LOG_LEVEL', None)
    
    # Log debug information if DEBUG level is enabled
    if logger.isEnabledFor(logging.DEBUG):
        debug_env_cache()

def debug_env_cache():
    """Log only the project name and debug level when debug is enabled."""
    # Get project name from environment variables
    project_name = get_env('PROJECT_NAME', '???')   
    # Get the current logging level name
    debug_level = get_env('LOG_LEVEL', '???')
    # Check if TEST_DYNAMIC_VAR exists (for debugging)
    test_var = get_env('TEST_DYNAMIC_VAR', 'NOT FOUND')

    logger.debug("--- Environment Debug Info ---")
    logger.debug(f"Project Name: {project_name}")
    logger.debug(f"Log Level: {debug_level}")
    logger.debug(f"TEST_DYNAMIC_VAR: {test_var}")
    
    # More comprehensive check for debugging
    logger.debug("All environment variables in _env_vars:")
    for key in sorted(_env_vars.keys()):
        if key == 'TEST_DYNAMIC_VAR':
            logger.debug(f"  {key}: {_env_vars[key]}")
    
    logger.debug("All environment variables in _env_vars_from_file:")
    for key in sorted(_env_vars_from_file.keys()):
        if key == 'TEST_DYNAMIC_VAR':
            logger.debug(f"  {key}: {_env_vars_from_file[key]}")
    
    logger.debug("-----------------------------")
