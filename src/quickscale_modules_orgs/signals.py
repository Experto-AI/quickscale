"""Signal definitions for the QuickScale organizations module.

SA7.1 — ``organization_created`` is the canonical extension seam for
cross-module behavior on org creation.  Receivers are connected by the
consuming module's ``AppConfig.ready()``, not by the orgs package.

Future org lifecycle events (purge, rename, archive) should follow the
same pattern — define here and let consuming modules connect their own
receivers.
"""

from django.dispatch import Signal

organization_created = Signal()
