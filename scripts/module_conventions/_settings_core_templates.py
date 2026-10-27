"""
Rule 30's core-template settings scan (SA320).

Rule 30 says a module's wiring writes its own settings and the Django or
third-party settings it needs; core's ``collect_wiring`` enforces the merge and
names no module.  The generator templates are the other half: a core template
that reads ``QUICKSCALE_<MODULE>_*`` (or otherwise names a module's setting)
carries that module's settings contract in the wrong home, so a rename or a
provider change needs a core edit and does not reach an existing project.

This detector reads every core generator template (``generator/templates/**``
ending ``.j2``) outside the theme tree and reports a ``QUICKSCALE_<module>_*``
token.  The theme's own templates are rule 31's declared module surface: they
read the live settings the seam publishes, so they are not core wiring.
Collected wiring itself is the passing control:
``globals().update(MODULE_SETTINGS)`` and ``compose_rest_framework(...)`` carry
no module name.
"""

from __future__ import annotations

import re

from scripts.module_conventions.core import GENERATOR_TEMPLATE_ROOT, Corpus

#: The theme tree under the generator templates; rule 31 owns its module surface.
_THEME_TEMPLATE_ROOT = f"{GENERATOR_TEMPLATE_ROOT}themes/"

#: A ``QUICKSCALE_<MODULE>_*`` setting token in template text.
_SETTING_TOKEN = re.compile(r"QUICKSCALE_[A-Z0-9_]+")


def rule_30_settings_composition(corpus: Corpus) -> list[str]:
    """Rule 30: no core generator template reads a module's own setting."""
    uppercase_modules = {module.name.upper(): module.name for module in corpus.modules}
    violations: list[str] = []
    for rel, text in corpus.core_files.items():
        if not (rel.startswith(GENERATOR_TEMPLATE_ROOT) and rel.endswith(".j2")):
            continue
        if rel.startswith(_THEME_TEMPLATE_ROOT):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            reported: set[str] = set()
            for match in _SETTING_TOKEN.finditer(line):
                token = match.group(0)
                for upper, module_name in uppercase_modules.items():
                    if token == f"QUICKSCALE_{upper}" or token.startswith(f"QUICKSCALE_{upper}_"):
                        if token in reported:
                            break
                        reported.add(token)
                        violations.append(
                            f"rule 30: core/{rel}:{lineno} core template reads "
                            f"module setting {token} ({module_name})"
                        )
                        break
    return violations
