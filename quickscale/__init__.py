"""QuickScale - A Django SaaS Starter Kit for Python-First Developers."""

__version__: str = "0.41.0"

try:
    from importlib.metadata import version
    __version__ = version("quickscale")
except ImportError:
    # Package not installed in environment
    pass
