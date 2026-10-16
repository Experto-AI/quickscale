"""Shared test support for the QuickScale module suites.

The module-conventions harness (decisions rule 18) keeps every module's
``tests/settings.py`` on :mod:`quickscale_core.testing.settings` and every
module's ``tests/conftest.py`` on :mod:`quickscale_core.testing.pytest_plugin`.
The submodules are not imported here: the settings base must stay importable
without pytest, which only the test environments install.
"""

from __future__ import annotations
