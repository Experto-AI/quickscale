"""The generated React shell's ``window.__QUICKSCALE__`` seam content.

Module Conventions rule 31: ``templates/index.html.j2`` renders
``window.__QUICKSCALE__.modules`` from the shipped module inventory, so the
seam carries a key for every shipped module and a key is ``true`` only while
its module is installed and its ``QUICKSCALE_<MODULE>_ENABLED`` setting is on.
Each ``modulePaths`` entry is a Django ``{% url %}`` reference, never a mount
literal.  Rendering the content here keeps the producer template free of any
per-module line.
"""

from __future__ import annotations

from dataclasses import dataclass

from quickscale_core.contracts.module_catalog import MODULE_CATALOG


@dataclass(frozen=True)
class SeamModule:
    """One shipped module as the React seam reports it."""

    name: str
    app_label: str
    enabled_setting: str


#: ``orgs`` carries no ``modules`` flag: the theme reports its deployment mode
#: through ``owner.mode`` instead (rule 31).
_NON_SEAM_MODULES = frozenset({"orgs"})

#: The theme's server-resolved paths (rule 31): module name -> the Django
#: template expression its ``modulePaths`` entry renders.  Every expression
#: reverses named routes, never a mount literal.  These three names are the
#: theme's own module surface, which rule 37 lists as its allowed literal-name
#: exception; the mount a module actually uses stays in its manifest (rule 7).
_SEAM_MODULE_PATHS: tuple[tuple[str, str], ...] = (
    ("crm", "{% url 'quickscale_crm_shell' %}"),
    (
        "social",
        "{% if settings.QUICKSCALE_SOCIAL_LINK_TREE_ENABLED %}"
        "{% url 'social-link-tree' %}"
        "{% elif settings.QUICKSCALE_SOCIAL_EMBEDS_ENABLED %}"
        "{% url 'social-embeds' %}"
        "{% else %}{% url 'social-link-tree' %}{% endif %}",
    ),
    ("analytics", "{% url 'quickscale_analytics:dashboard' %}"),
)


def seam_modules() -> tuple[SeamModule, ...]:
    """Return every shipped module the seam reports, in inventory order.

    The set comes from core's declared release inventory (Module Conventions
    rule 37's allowed exception), which its consistency test keeps equal to
    ``quickscale_modules/*/module.yml`` discovery.  A selected subset must not
    shrink the set: the seam validator requires an own flag for every shipped
    module, present as ``false`` when the module is absent.
    """
    return tuple(
        SeamModule(
            name=entry.name,
            app_label=f"quickscale_modules_{entry.name}",
            enabled_setting=f"QUICKSCALE_{entry.name.upper()}_ENABLED",
        )
        for entry in MODULE_CATALOG
        if entry.name not in _NON_SEAM_MODULES
    )


def _installed_and_enabled(module: SeamModule) -> str:
    """Return the seam's installed-and-enabled template test for one module."""
    return (
        f"'{module.app_label}' in settings.INSTALLED_APPS "
        f"and settings.{module.enabled_setting}"
    )


def render_module_flags(indent: str = "          ") -> str:
    """Render the ``modules`` object's body: one flag per shipped module.

    Each key is ``true`` only while the module is installed and its enabled
    setting is on; a module that is not installed renders ``false``.
    """
    return "\n".join(
        f"{indent}{module.name}: "
        f"{{% if {_installed_and_enabled(module)} %}}"
        "true{% else %}false{% endif %},"
        for module in seam_modules()
    )


def render_module_paths(indent: str = "          ") -> str:
    """Render the ``modulePaths`` object's body: every path a ``{% url %}``.

    A path resolves from the module's named route only while the module is
    installed and enabled; otherwise it reverses the project's always-present
    ``home`` route, because the seam validator requires a non-empty string for
    every path field even when the flag above is ``false``.
    """
    modules = {module.name: module for module in seam_modules()}
    lines: list[str] = []
    for index, (name, url_reference) in enumerate(_SEAM_MODULE_PATHS):
        module = modules[name]
        comma = "," if index < len(_SEAM_MODULE_PATHS) - 1 else ""
        lines.append(
            f'{indent}{name}: "'
            f"{{% if {_installed_and_enabled(module)} %}}"
            f"{url_reference}"
            "{% else %}{% url 'home' %}{% endif %}\""
            f"{comma}"
        )
    return "\n".join(lines)
