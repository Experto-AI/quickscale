"""Command runner utilities for end-to-end tests."""
import subprocess
from pathlib import Path
import os

def run_quickscale_command(*args, capture_output=True, check=False):
    """
    Run a QuickScale command with the given arguments.
    
    Args:
        *args: Command arguments to pass to QuickScale
        capture_output: Whether to capture command output (default: True)
        check: Whether to check the return code (default: False)
    
    Returns:
        CompletedProcess instance with command result
    """
    cmd = ['quickscale'] + list(args)
    
    # Handle capture_output for different Python versions
    kwargs = {}
    if capture_output:
        kwargs['stdout'] = subprocess.PIPE
        kwargs['stderr'] = subprocess.PIPE
        kwargs['universal_newlines'] = True
    
    result = subprocess.run(cmd, **kwargs, check=check)
    return result
