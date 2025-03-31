"""QuickScale - A Django SaaS Starter Kit for Python-First Developers."""
from typing import Optional

__version__: str = "0.4.0"

try:
    from importlib.metadata import version
    __version__ = version("quickscale")
except ImportError:
    # Package not installed in environment
    pass