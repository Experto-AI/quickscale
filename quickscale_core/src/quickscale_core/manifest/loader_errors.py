"""Manifest error types for the module-manifest loader.

Split out of :mod:`quickscale_core.manifest.loader` so the loader's parsing
modules can raise the same error types without importing the loader facade
back.  :mod:`quickscale_core.manifest.loader` re-exports both classes, so
imports from that path keep working.
"""

from __future__ import annotations


class ManifestError(Exception):
    """Error loading or validating a module manifest"""

    def __init__(self, message: str, module_name: str | None = None):
        self.message = message
        self.module_name = module_name
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with module name"""
        if self.module_name:
            return f"[{self.module_name}] {self.message}"
        return self.message


class ModuleVersionMismatchError(RuntimeError):
    """Raised when an embedded module's manifest version predates the current
    core version, indicating the module content is too old to wire safely.

    This error is intentionally a plain ``RuntimeError`` subclass — **not**
    ``ManifestError`` — so that callers can catch it independently from
    structural manifest loading/validation errors.  The stable message
    format is::

        Module '{module_name}' version mismatch: found {found};
        expected core version {core_version}.
    """
