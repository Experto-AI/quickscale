"""The auth views logger, shared by the views facade and its private siblings.

The account-deletion boundary's test suite asserts on the
``quickscale_modules_auth.views`` log channel, so the private
account-deletion modules log under this logger rather than one named for
their own file (Module Conventions rule 28).
"""

import logging

logger = logging.getLogger("quickscale_modules_auth.views")
