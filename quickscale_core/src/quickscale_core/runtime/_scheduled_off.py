"""Rule 17's one scheduled-off refusal, split from the conventions facade.

The helper sits beside :mod:`quickscale_core.runtime.conventions` — which
re-exports it and is the import path every module uses — so the facade stays
inside the repository's fixed file-length ceiling while the refusal keeps one
implementation.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import CommandError


def require_scheduled_module_enabled(trigger: str, *, module_name: str) -> None:
    """Refuse a scheduled command run while its module is switched off.

    Rule 17's one scheduled-off refusal: a command whose invocation provenance
    is ``scheduled`` refuses before doing any work when its module's
    ``QUICKSCALE_<MODULE>_ENABLED`` setting is false or not supplied;
    ``manual`` and ``admin`` runs stay available, like the retained admin
    (rule 1).  A command with a ``--trigger`` option calls this before any
    other work, so the refusal reads the same everywhere and no command
    module spells its own.

    Args:
        trigger: The command's resolved ``--trigger`` value.
        module_name: The module whose ``_ENABLED`` setting gates the run.

    Raises:
        ValueError: when *module_name* is not a non-empty string.
        CommandError: when *trigger* is ``scheduled`` and the module is
            switched off, naming the setting an operator must turn back on.
    """
    if not isinstance(module_name, str) or not module_name:
        raise ValueError(
            "require_scheduled_module_enabled() requires a non-empty module name."
        )
    if trigger != "scheduled":
        return
    setting_name = f"QUICKSCALE_{module_name.upper()}_ENABLED"
    if not bool(getattr(settings, setting_name, False)):
        raise CommandError(
            f"The {module_name} module is disabled ({setting_name} is False); "
            "scheduled runs do not run."
        )
