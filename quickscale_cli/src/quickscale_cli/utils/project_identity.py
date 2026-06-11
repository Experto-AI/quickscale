"""Backward-compatible shim for the relocated project_identity module.

The project identity helpers now live at :mod:`quickscale_core.utils.project_identity`.
This module re-exports the same public surface from its original location so that
existing CLI imports (``from quickscale_cli.utils.project_identity import ...``)
keep working without modification.
"""

from quickscale_core.utils.project_identity import (  # noqa: F401
    ProjectIdentity,
    ProjectIdentityResolutionError,
    derive_package_from_slug,
    identity_from_config,
    identity_from_state,
    load_identity_from_config_file,
    load_identity_from_state_file,
    resolve_project_identity,
)
