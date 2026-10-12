"""
Rule 31's theme-seam producer mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_routes`; that
module re-exports the seam constants and the detector, so existing import
paths (``check_module_conventions``) keep working.
"""

from __future__ import annotations

import re

from scripts.module_conventions.core import Corpus, Module, _declared_mounts

# Rule 31's seam producers, relative to the core package.  The templates render
# the discovered module set at request time through the runtime tag library; the
# theme's TypeScript may still name its own React surfaces (rule 37's allowlist).
THEME_SEAM_TEMPLATE = "generator/templates/themes/showcase_react/templates/index.html.j2"

THEME_SEAM_TEMPLATES: tuple[str, ...] = (
    THEME_SEAM_TEMPLATE,
    "generator/templates/themes/showcase_react/templates/social/link_tree.html.j2",
    "generator/templates/themes/showcase_react/templates/social/embeds.html.j2",
)

#: Rule 31's runtime seam library: every producer loads it, and its tags
#: resolve the flags and paths from the shipped inventory and live settings
#: (``quickscale_core.runtime.seam_tags``).
SEAM_LIBRARY_LOAD = re.compile(r"{%\s*load\b[^%]*\bquickscale_seam\b[^%]*%}")


def _seam_tag_violations(rel: str, template: str) -> list[str]:
    """Return rule 31's missing-tag and missing-library violations for one producer."""
    violations: list[str] = []
    for tag in (
        "{% seam_module_flags %}",
        "{% seam_module_paths %}",
        "{% seam_module_api_paths %}",
    ):
        if tag not in template:
            violations.append(f"rule 31: {rel} does not render {tag}")
    if SEAM_LIBRARY_LOAD.search(template) is None:
        violations.append(f"rule 31: {rel} does not load the quickscale_seam tag library")
    return violations


def _seam_module_violations(rel: str, template: str, module: Module) -> list[str]:
    """Return rule 31's per-module literal violations for one producer."""
    violations: list[str] = []
    name = module.name
    for mount in _declared_mounts(module):
        if not mount:
            continue
        for literal in (f'"{mount}"', f"'{mount}'", f'"/{mount}"', f"'/{mount}'"):
            if literal in template:
                violations.append(f"rule 31: {rel} writes {name}'s mount {mount!r} literally")
    if rel != THEME_SEAM_TEMPLATE:
        for literal in (f'"{name}":', f"'{name}':"):
            if literal in template:
                violations.append(f"rule 31: {rel} writes module {name!r} as a key")
    if re.search(rf"(?m)^\s*{re.escape(name)}\s*:", template):
        violations.append(f"rule 31: {rel} writes module {name!r} as a bare key")
    return violations


def _index_module_literal_violations(index_template: str, module: Module) -> list[str]:
    """Return rule 31's literal module-name violations for the theme index."""
    violations: list[str] = []
    name = module.name
    literals = (
        f'"{name}"',
        f"'{name}'",
        f'"/{name}/"',
        f"'/{name}/'",
        f'"{name}/"',
        f"'{name}/'",
    )
    for literal in literals:
        if literal in index_template:
            violations.append(f"rule 31: the theme's index.html.j2 names module {name!r} literally")
    return violations


def rule_31_theme_seam(corpus: Corpus) -> list[str]:
    """
    Rule 31: the seam producer renders discovery at request time.

    The statically checkable clauses of the seam's producers, the theme's
    ``index.html.j2`` and its two public social pages: each loads the
    ``quickscale_seam`` runtime tag library and renders the discovered flags,
    paths, and module API bases (rule 41) through its tags instead of literal
    module lines or mount paths, and the index template carries no
    ``INSTALLED_APPS`` test (the runtime library holds it).  A loaded core
    tree without the template fails; an empty synthetic corpus does not.
    """
    violations: list[str] = []
    index_template = corpus.core_files.get(THEME_SEAM_TEMPLATE)
    if index_template is None:
        if corpus.core_files:
            violations.append("rule 31: the core tree carries no theme index.html.j2 seam producer")
        return violations
    for rel in THEME_SEAM_TEMPLATES:
        template = corpus.core_files.get(rel)
        if template is None:
            continue
        violations.extend(_seam_tag_violations(rel, template))
        for module in corpus.modules:
            violations.extend(_seam_module_violations(rel, template, module))
    for module in corpus.modules:
        violations.extend(_index_module_literal_violations(index_template, module))
    if "INSTALLED_APPS" in index_template:
        violations.append("rule 31: the theme's index.html.j2 carries an INSTALLED_APPS test")
    return violations
