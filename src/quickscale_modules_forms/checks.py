"""Startup checks for the QuickScale Forms module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime``.  The Forms module's declared options are validated
by the generic settings check (``register_module_settings_check``); this
module carries the retired setting names that check refuses (rule 6).
"""

from __future__ import annotations

from collections.abc import Mapping

#: Retired setting names refused at startup, each naming its replacement
#: (rule 6).  The declaration lives here, with the module's other checks,
#: because the refusal must work before the project is re-applied: the
#: settings a previous release wrote are exactly the ones still carrying
#: these names.
RETIRED_SETTINGS: Mapping[str, str] = {
    "FORMS_DATA_RETENTION_DAYS": (
        "Legacy setting 'FORMS_DATA_RETENTION_DAYS' is no longer supported. "
        "Use 'QUICKSCALE_FORMS_RETENTION_DAYS' instead."
    ),
    "FORMS_PER_PAGE": (
        "Legacy setting 'FORMS_PER_PAGE' is no longer supported. "
        "Use 'QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE' instead."
    ),
    "FORMS_RATE_LIMIT": (
        "Legacy setting 'FORMS_RATE_LIMIT' is no longer supported. "
        "Use 'QUICKSCALE_FORMS_RATE_LIMIT' instead."
    ),
    "FORMS_SPAM_PROTECTION": (
        "Legacy setting 'FORMS_SPAM_PROTECTION' is no longer supported. "
        "Use 'QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED' instead."
    ),
    "FORMS_SUBMISSIONS_API": (
        "Legacy setting 'FORMS_SUBMISSIONS_API' is no longer supported. "
        "Use 'QUICKSCALE_FORMS_API_ENABLED' instead."
    ),
}
