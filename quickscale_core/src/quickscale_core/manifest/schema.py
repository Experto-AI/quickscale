"""Module Manifest Schema

Dataclasses for module manifest (module.yml) configuration.
Defines mutable vs immutable config options for modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

#: Root prefix that all manifest-declared managed-file output paths must
#: resolve under.  This is the single source of truth for the write
#: boundary enforced by the loader and assembler.
MANAGED_FILE_ROOT_PREFIX = "quickscale_managed/"


@dataclass(frozen=True)
class ManagedFileDeclaration:
    """Declarative description of a single module-owned managed file.

    Managed files are generated artifacts that a module contributes to the
    generated project.  The declaration is intentionally minimal: a renderer
    identifier and a rooted output path.  Content generation is deferred to
    a later phase; this dataclass captures only the structural contract.

    Attributes:
        key: The YAML key identifying this managed file within the
            module's ``managed_files`` section.
        renderer: Renderer identifier (e.g. a template path or renderer
            name) that describes how the file content is produced.
        output_path: Destination path for the generated file, relative
            to the project root.  Must start with
            ``quickscale_managed/`` to enforce the write boundary.
    """

    key: str
    renderer: str
    output_path: str

    @property
    def is_within_managed_root(self) -> bool:
        """Return True when the output_path is under the managed root prefix."""
        return self.output_path.startswith(MANAGED_FILE_ROOT_PREFIX)


@dataclass
class ConfigOption:
    """Configuration option for a module"""

    name: str
    option_type: str  # boolean, string, integer, list
    default: Any = None
    django_setting: str | None = None  # Only for mutable options
    description: str = ""
    mutability: Literal["mutable", "immutable"] = "immutable"
    validation: dict[str, Any] = field(default_factory=dict)

    @property
    def is_mutable(self) -> bool:
        """Check if this option is mutable (can be changed after embed)"""
        return self.mutability == "mutable" and self.django_setting is not None


def parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """Parse a dotted version string into a comparable integer tuple.

    Strips pre-release suffixes (e.g. ``"0.87.0-alpha"`` → ``"0.87.0"``)
    and maps each numeric component.  Returns ``(0,)`` for unparseable
    input so callers can fail safe (unknown < known) rather than raise.

    Example::

        >>> parse_version_tuple("0.87.0")
        (0, 87, 0)
        >>> parse_version_tuple(None)  # legacy / unknown
        (0,)
    """
    if not version_str or not isinstance(version_str, str):
        return (0,)
    try:
        core = version_str.split("-")[0]
        return tuple(int(p) for p in core.split("."))
    except ValueError, AttributeError:
        return (0,)


@dataclass
class ContractVintage:
    """Declares a module's contract-vintage step and adoption boundary.

    Every declared vintage carries an ``id`` — the loader refuses a
    shipped vintage without one; a generated project's embedded copy of an
    older release is the explicit exception — and the step is satisfied
    only while the project records that id in its
    ``adopted_contract_steps``.  A project that has not recorded it is
    behind the module's contract and should follow
    ``manual_adoption_steps`` before the module is fully supported.

    This is the additive metadata block that powers SA10.2 detection:
    ``quickscale status`` compares each installed module's declared step
    id against the project's recorded ids and surfaces the gap.

    Attributes:
        minimum: The QuickScale release that introduced the contract.
            Projects behind the declared step are flagged with it so the
            operator can place the change in a release.
        manual_adoption_steps: Human-readable list of steps an existing
            project must follow to catch up to the module's current
            contract.  Empty when no specific manual action is required.
        id: The step's stable identity in the one adopted-step namespace.
            A declared vintage must carry one: the loader refuses a
            missing id (only an embedded historical copy may omit the
            key) and any present id that is not a non-empty string.  The
            step is satisfied only while the id is recorded in the
            project's ``adopted_contract_steps``.
    """

    minimum: str
    manual_adoption_steps: list[str] = field(default_factory=list)
    id: str | None = None


@dataclass
class ProjectContractStep:
    """One generated-project contract change and its adoption steps.

    SA207 declares every template contract change once, at the project
    level, instead of copying adoption prose into each module manifest.

    Attributes:
        id: Stable identifier for the change (e.g. ``"sa201-throttling"``).
        minimum: Minimum ``project_contract`` version that satisfies the
            step.  A project below it is behind this step.
        title: One-line summary shown before the adoption steps.
        manual_adoption_steps: Human-readable steps an existing project
            follows to catch up.
    """

    id: str
    minimum: str
    title: str
    manual_adoption_steps: list[str] = field(default_factory=list)


@dataclass
class ProjectContractVintage:
    """The generated-project contract vintage declaration (SA207).

    Declares each template contract change once, with its adoption steps.
    Loaded from the packaged ``data/project_contract.yml``.

    Attributes:
        steps: Ordered declared contract steps.
    """

    steps: list[ProjectContractStep] = field(default_factory=list)


@dataclass
class ModuleOperations:
    """A module's own operations text (SA286).

    Populated from the top-level ``operations`` section: the module names the
    operator-facing section (``title``), authors its Markdown body (``text``),
    and declares the module-owned values the text references (``values``,
    keyed by the ``{name}`` token the text uses).  The generated project's
    managed ``quickscale-operations.md`` page renders these sections, and the
    user-owned ``OPERATIONS.md`` links that page once, so the module owns its
    operations contract and a module release changes no user-owned file.

    The ``text`` may also reference a declared option's resolved value or a
    core contract token (see
    ``quickscale_core.contracts.module_options.ADOPTION_STEP_TOKENS``); both
    resolve when the page renders.

    Attributes:
        title: The section heading rendered on the managed page.
        text: The module-owned Markdown body.
        values: Module-owned values keyed by token name; the text references
            each as ``{name}``.  A value is a string, or a tuple of strings
            for a declared group (rendered comma-separated, each entry
            guarded as its own module-owned value).
    """

    title: str
    text: str
    values: dict[str, str | tuple[str, ...]] = field(default_factory=dict)


@dataclass
class FrontendResources:
    """A module's frontend resource contract for the managed theme hook.

    Populated from the top-level ``frontend_resources`` section.  ``paths``
    maps a resource name the theme may reference (``stats``) to that
    resource's module-relative API subpath (``stats/``), and ``payload_types``
    maps a response type name (``CrmStats``) to its fields and TypeScript
    types (``contacts: number``).

    A path may carry ``{parameter}`` placeholders (``members/{membershipId}/role/``);
    the managed hook renders a typed builder for it instead of a string, so a
    path with a runtime identifier has one generated home too.  A payload type
    is either a field mapping (rendered as an interface) or a union expression
    string (rendered as a type alias); a field maps a field name to a scalar,
    a declared type name, an array of either, or a nullable form, and an
    optional field appends ``?`` to its name.

    The generated project's managed ``frontend/src/quickscaleSeam.hooks.ts``
    renders these declarations for the shipped module set, so a module
    resource path or payload shape has one generated home and a module release
    that changes one changes no user-owned theme file.

    Attributes:
        paths: Resource name -> module-relative API subpath, in declaration
            order.  A subpath is appended to the module's ``moduleApiPaths``
            base, never written by a user-owned file.  A value with a
            ``{parameter}`` placeholder renders as a builder function.
        payload_types: Type name -> ordered field name/type pairs, or a
            union expression string, in declaration order.  A field type is a
            scalar (``string``, ``number``, ``boolean``), a declared type
            name, an array of either (``OrgSummary[]``), or a nullable form
            (``string | null``).
    """

    paths: dict[str, str] = field(default_factory=dict)
    payload_types: dict[str, dict[str, str] | str] = field(default_factory=dict)


@dataclass(frozen=True)
class MakeTarget:
    """One generated-project ``make`` target a module declares.

    The generated ``Makefile`` carries a managed region in which every
    installed module's targets render under their declared name and help
    text, so a module release changes no user-owned ``Makefile`` line and a
    new module adds a target with no core edit.

    Attributes:
        name: The make target name (``check-tenant-isolation``).  A name
            colliding with a core target or another module's target fails
            at load or generation.
        help: The one-line help text rendered after ``##``.
        recipe: Ordered shell lines, each rendered with a leading tab; a
            line is one shell invocation.
    """

    name: str
    help: str
    recipe: tuple[str, ...]


@dataclass
class ProjectBlocks:
    """A module's generated-project blocks outside its Django package.

    Populated from the top-level ``project_blocks`` section.  Each field is a
    contribution the generated project's user-owned root files carry inside
    one managed region, so a module owns the behavior and core names no
    module:

    * ``ci_steps`` renders inside the test job's ``steps`` in
      ``.github/workflows/ci.yml``;
    * ``ci_jobs`` renders inside the workflow's ``jobs`` mapping;
    * ``make_targets`` and ``make_test_env`` render inside the generated
      ``Makefile``;
    * ``compose_env`` names options whose resolved environment-variable names
      pass through the backend service environment in ``docker-compose.yml``.

    Text blocks may carry the project-context tokens
    ``{package_name}``, ``{postgres_version}``,
    ``{postgres_patch_version}``, ``{python_patch_version}``, and
    ``{django_ci_version}``; an unknown token fails generation.
    """

    ci_steps: str | None = None
    ci_jobs: str | None = None
    make_targets: tuple[MakeTarget, ...] = ()
    make_test_env: dict[str, str] = field(default_factory=dict)
    compose_env: tuple[str, ...] = ()
    ci_test_env: dict[str, str] = field(default_factory=dict)


@dataclass
class ModuleManifest:
    """Complete module manifest from module.yml"""

    name: str
    version: str
    description: str = ""
    mutable_options: dict[str, ConfigOption] = field(default_factory=dict)
    immutable_options: dict[str, ConfigOption] = field(default_factory=dict)
    required_modules: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    managed_files: dict[str, ManagedFileDeclaration] = field(default_factory=dict)

    operations: ModuleOperations | None = None
    """The module's operations declaration, or ``None`` when absent.

    The generated project's managed ``quickscale-operations.md`` page renders
    it; see :class:`ModuleOperations`."""

    frontend_resources: FrontendResources | None = None
    """The module's frontend resource contract, or ``None`` when absent.

    The generated project's managed ``quickscaleSeam.hooks.ts`` renders it;
    see :class:`FrontendResources`."""

    project_blocks: ProjectBlocks | None = None
    """The module's declared generated-project blocks, or ``None`` when absent.

    The generated Makefile, CI workflow, and Compose file carry one managed
    region per block; see :class:`ProjectBlocks`."""

    ci_env: dict[str, str] = field(default_factory=dict)
    """Non-live CI environment placeholders keyed by declaring option name.

    Populated from the top-level ``ci_env`` section: each key names a
    declared string option whose resolved value is the environment-variable
    name the module's startup check reads, and the value is the placeholder
    CI sets under that name.  The generated project's managed
    ``.github/quickscale-ci-env`` renders from these declarations, so the
    module owns its CI credential contract and a module release changes no
    user-owned file.
    """

    # ------------------------------------------------------------------ #
    # Derivation metadata (T2.3+)
    #
    # These optional fields carry the derivation/validation rules that
    # instruct the resolver how to normalise, validate, project settings,
    # and wire the module from declarative ``module.yml`` data.  They are
    # populated when the loader encounters a ``derivation`` section in the
    # manifest YAML.  Existing ``module.yml`` files without a derivation
    # section leave these fields as their default empty values.
    # ------------------------------------------------------------------ #
    derivation_rules: list[dict[str, Any]] = field(default_factory=list)
    """Retained derivation metadata field; the loader refuses top-level
    ``normalization_rules`` authoring, so a loaded manifest leaves this empty."""
    validation_rules: list[dict[str, Any]] = field(default_factory=list)
    """Retained derivation metadata field; the loader refuses manifest
    ``validation_rules`` authoring, so a loaded manifest leaves this empty."""
    legacy_aliases: list[dict[str, Any]] = field(default_factory=list)
    """Retained derivation metadata field; the loader refuses manifest alias
    authoring (rule 6), so a loaded manifest leaves this empty."""
    derived_settings: list[dict[str, Any]] = field(default_factory=list)
    """Derived Django settings declared in the manifest derivation section."""
    wiring_projections: list[dict[str, Any]] = field(default_factory=list)
    """Wiring projections declared in the manifest derivation section."""
    option_derivations: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Per-option derivation metadata keyed by option name. Each value is a
    raw dict with optional ``normalization_rules``, ``derived_settings``, and
    ``wiring_projections`` sub-lists; the loader refuses a ``validation_rules``
    or ``legacy_aliases`` declaration.  Populated from the
    ``derivation.option_derivations`` section in the manifest YAML."""

    retired_options: dict[str, str] = field(default_factory=dict)
    """Retired option keys mapped to the message naming their removal.

    Populated when the loader encounters a top-level ``retired_options``
    section.  The option-validation engine reports every supplied retired
    key with its declared message, and ``sanitize_module_options`` refuses
    them on the config and state paths, so ``module.yml`` is the single home
    of a retired key's refusal."""

    retired_settings: dict[str, str] = field(default_factory=dict)
    """Retired Django setting names mapped to the message naming their replacement.

    Populated when the loader encounters a top-level ``retired_settings``
    section.  The generic startup settings check reads the map from the
    module's shipped manifest and refuses every retired name the project's
    settings still define, so ``module.yml`` is the single home of a retired
    setting's refusal."""

    throttle_scopes: dict[str, str] = field(default_factory=dict)
    """Declared DRF throttle scopes mapped to the option carrying their rate.

    Populated when the loader encounters a top-level ``throttle_scopes``
    section: each key is a ``quickscale_<module>_<purpose>`` DRF scope
    (Module Conventions rules 2 and 32) and each value names a declared
    string option whose resolved value is that scope's rate (rule 1's
    ``_RATE_LIMIT`` option).  The resolver projects the resolved rates into
    ``ModuleWiringSpec.throttle_scopes``, so no adapter writes the rate
    map and ``module.yml`` is the single home of a module's throttle
    scopes."""

    # ------------------------------------------------------------------ #
    # Contract-vintage metadata (SA10.2)
    #
    # This optional field carries the module's contract-vintage step —
    # its id, minimum, and the manual-adoption steps an existing project
    # must follow when its generation contract predates the module's
    # current vintage.  Populated when the loader encounters a
    # ``contract_vintage`` section in the manifest YAML; a shipped section
    # must carry a non-empty ``id`` — the loader refuses a missing one
    # unless the read is the explicit embedded-historical-copy opt-out,
    # and refuses any present id that is null, empty, or not a string.
    # Existing ``module.yml`` files without that section leave this field
    # as ``None``.
    # ------------------------------------------------------------------ #
    contract_vintage: ContractVintage | None = None
    """Optional contract-vintage declaration for this module.
    ``None`` when the module has not declared a vintage boundary; a
    shipped section must carry a non-empty id."""

    # ------------------------------------------------------------------ #
    # Readiness / lifecycle metadata
    # ------------------------------------------------------------------ #
    ready: bool = True
    """Whether the module is considered publicly ready.  Modules discovered
    from a valid ``module.yml`` default to ``True``."""

    def get_option(self, option_name: str) -> ConfigOption | None:
        """Get a config option by name from either mutable or immutable"""
        if option_name in self.mutable_options:
            return self.mutable_options[option_name]
        if option_name in self.immutable_options:
            return self.immutable_options[option_name]
        return None

    def is_option_mutable(self, option_name: str) -> bool:
        """Check if a specific option is mutable"""
        return option_name in self.mutable_options

    def get_all_options(self) -> dict[str, ConfigOption]:
        """Get all config options (mutable and immutable)"""
        return {**self.mutable_options, **self.immutable_options}

    def get_defaults(self) -> dict[str, Any]:
        """Get default values for all options"""
        defaults = {}
        for name, option in self.mutable_options.items():
            defaults[name] = option.default
        for name, option in self.immutable_options.items():
            defaults[name] = option.default
        return defaults

    def get_django_settings_mapping(self) -> dict[str, str]:
        """Get mapping from option names to Django settings keys (mutable only)"""
        mapping = {}
        for name, option in self.mutable_options.items():
            if option.django_setting:
                mapping[name] = option.django_setting
        return mapping
