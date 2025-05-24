"""QuickScale - A Django SaaS Starter Kit for Python-First Developers."""
from typing import Optional

__version__: str = "0.14.0"

try:
    from importlib.metadata import version
    __version__ = version("quickscale")
except ImportError:
    # Package not installed in environment
    pass

# Import the initialize_env function to make it available at the package level
from quickscale.utils.env_utils import initialize_env