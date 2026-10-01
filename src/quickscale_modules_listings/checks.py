"""Startup checks for the QuickScale listings module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime``.  The listings module's declared options are
validated by the generic settings check
(``register_module_settings_check``); this module carries the retired setting
names that check refuses (rule 6).
"""

from __future__ import annotations

from collections.abc import Mapping

#: Retired setting names refused at startup, each naming its replacement
#: (rule 6).  The declaration lives here, with the module's other checks,
#: because the refusal must work before the project is re-applied: the
#: settings a previous release wrote are exactly the ones still carrying
#: these names.
RETIRED_SETTINGS: Mapping[str, str] = {
    "LISTINGS_PER_PAGE": (
        "Legacy setting 'LISTINGS_PER_PAGE' is no longer supported. "
        "Use 'QUICKSCALE_LISTINGS_PER_PAGE' instead."
    ),
}
