# QuickScale - A Django SaaS Starter Kit for Python-First Developers

# Single source of truth for package version
__version__ = "0.1.1"

try:
    from importlib.metadata import version
    __version__ = version("quickscale")
except ImportError:
    # Package is not installed
    pass