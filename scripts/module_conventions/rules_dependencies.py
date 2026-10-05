"""Dependency, secret, type-check, and module-dependency rules."""

from __future__ import annotations

import ast
import configparser
import os
import re

from scripts.module_conventions.core import (
    MODULE_LAYERS,
    SNAKE_CASE,
    Corpus,
    _attribute_chain,
    _cross_module_imports,
    _literal,
    _parse,
    _same_layer_cycles,
    _setting_name_module,
    _settings_attribute_reads,
)

# Rule 35's one listed exception: orgs' RLS boot guard reads core's runtime-role
# variables before settings load.
CORE_RUNTIME_ROLE_ENV_VARS = (
    "QUICKSCALE_ALLOW_BYPASSRLS",
    "QUICKSCALE_PRIVILEGED_COMMAND",
)

# Rule 36's bounded relaxations: the section may turn off the three standard
# strictness flags and disable only the ``var-annotated`` error code.  Any
# other setting is allowed when it is not a relaxation — "stricter is allowed"
# — so the known relaxation forms below are rejected and unlisted settings are
# treated as stricter or neutral.  ``ignore_missing_imports`` stays an explicit
# prohibition, and an additional section targeting the module is rejected.
RULE_36_ALLOWED_RELAXATION_KEYS = (
    "disallow_untyped_defs",
    "warn_return_any",
    "warn_unused_ignores",
)

RULE_36_ALLOWED_DISABLED_CODES = frozenset({"var-annotated"})

RULE_36_FORBIDDEN_SECTION_KEYS = frozenset({"ignore_missing_imports"})

RULE_36_FALSE_VALUES = frozenset({"false", "no", "0", "off"})

RULE_36_TRUE_VALUES = frozenset({"true", "yes", "1", "on"})

#: mypy's per-module options that relax checking at the listed effective
#: value.  A section may relax at most the three standard flags and the
#: ``var-annotated`` code, so any other effective lenient value is a
#: violation, whether or not it matches a mypy default; the permitted
#: relaxations are exempted before this table is consulted.
RULE_36_RELAXED_VALUES: dict[str, str] = {
    "allow_redefinition": "true",
    "allow_redefinition_old": "true",
    "allow_untyped_globals": "true",
    "check_untyped_defs": "false",
    "disallow_any_decorated": "false",
    "disallow_any_explicit": "false",
    "disallow_any_expr": "false",
    "disallow_any_generics": "false",
    "disallow_any_unimported": "false",
    "disallow_incomplete_defs": "false",
    "disallow_subclassing_any": "false",
    "disallow_untyped_calls": "false",
    "disallow_untyped_decorators": "false",
    "disallow_untyped_defs": "false",
    "extra_checks": "false",
    "follow_untyped_imports": "true",
    "ignore_errors": "true",
    "ignore_missing_imports": "true",
    "implicit_optional": "true",
    "implicit_reexport": "true",
    "local_partial_types": "false",
    "strict_concatenate": "false",
    "strict_equality": "false",
    "strict_equality_for_none": "false",
    "strict_optional": "false",
    "warn_no_return": "false",
    "warn_return_any": "false",
    "warn_unreachable": "false",
    "warn_unused_ignores": "false",
}

#: ``follow_imports`` relaxes checking on these values.
RULE_36_RELAXED_FOLLOW_IMPORTS = frozenset({"silent", "skip"})

#: The effective option names the alias spellings invert.
RULE_36_KNOWN_EFFECTIVE_KEYS = frozenset({*RULE_36_RELAXED_VALUES, "follow_imports"})

RULE_36_SECTION_TEMPLATE = "mypy-quickscale_modules_{module}.*"

#: The module pattern mypy matches after it strips the section's ``mypy-``
#: marker once and splits the remainder on commas.
RULE_36_MODULE_GLOB = "quickscale_modules_{module}"


def rule_5_dependency_direction(corpus: Corpus) -> list[str]:
    """Enforce the layer table and acyclic same-layer imports (rule 5)."""
    violations: list[str] = []
    edges: dict[str, set[str]] = {}
    for module in corpus.modules:
        layer = MODULE_LAYERS.get(module.name)
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            in_migrations = rel.startswith("migrations/")
            for other, path, names, lineno, _kind in _cross_module_imports(_parse(text)):
                if other == module.name or layer is None:
                    continue
                if in_migrations and path[:1] == ("models",):
                    continue
                other_layer = MODULE_LAYERS.get(other)
                if other_layer is None:
                    continue
                for component in (path[0],) if path else names:
                    if in_migrations and component == "models":
                        continue
                    if other_layer > layer:
                        violations.append(
                            f"rule 5: {module.name}: {rel}:{lineno} imports upward from "
                            f"{other}:{component} (layer {other_layer} above layer {layer})"
                        )
                    elif other_layer == layer:
                        edges.setdefault(module.name, set()).add(other)
    for cycle in _same_layer_cycles(edges):
        violations.append(f"rule 5: same-layer import cycle: {' -> '.join(cycle)}")
    for rel, text in corpus.core_files.items():
        if not rel.endswith(".py"):
            continue
        for attribute, lineno in _settings_attribute_reads(_parse(text)):
            if _setting_name_module(attribute) is not None:
                violations.append(f"rule 5: core {rel}:{lineno} names module setting {attribute}")
    return violations


def _environ_references(tree: ast.Module) -> list[tuple[int, str | None]]:
    """
    Rule 35: every ``os.getenv`` / ``os.environ`` use and its literal name.

    Import aliases of ``os``, ``os.environ``, and ``os.getenv`` are followed.
    A use whose variable name is not a string literal records ``None``.  A
    call or subscript marks the receiver it belongs to, so one use is reported
    once.
    """
    references: list[tuple[int, str | None]] = []
    handled: set[int] = set()
    os_names = {"os"}
    environ_names = {"environ"}
    getenv_names = {"getenv"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "os":
                    os_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            for alias in node.names:
                if alias.name == "environ":
                    environ_names.add(alias.asname or alias.name)
                elif alias.name == "getenv":
                    getenv_names.add(alias.asname or alias.name)

    def record(node: ast.AST, literal: object) -> None:
        handled.add(id(node))
        references.append((node.lineno, literal if isinstance(literal, str) else None))

    def is_environ_path(chain: tuple[str, ...]) -> bool:
        return (len(chain) == 1 and chain[0] in environ_names) or (
            len(chain) == 2 and chain[0] in os_names and chain[1] == "environ"
        )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        chain = _attribute_chain(node.func)
        if chain is None:
            continue
        getenv_call = (len(chain) == 1 and chain[0] in getenv_names) or (
            len(chain) == 2 and chain[0] in os_names and chain[1] == "getenv"
        )
        environ_get_call = (
            len(chain) == 2 and chain[0] in environ_names and chain[1] == "get"
        ) or (len(chain) == 3 and chain[0] in os_names and chain[1:] == ("environ", "get"))
        if getenv_call or environ_get_call:
            literal = _literal(node.args[0]) if node.args else None
            record(node, literal)
            if isinstance(node.func, ast.Attribute):
                handled.add(id(node.func))
                handled.add(id(node.func.value))
    for node in ast.walk(tree):
        if id(node) in handled:
            continue
        if isinstance(node, ast.Subscript):
            chain = _attribute_chain(node.value)
            if chain is not None and is_environ_path(chain):
                record(node, _literal(node.slice))
                handled.add(id(node.value))
        elif isinstance(node, ast.Attribute) and node.attr == "environ":
            chain = _attribute_chain(node)
            if chain is not None and is_environ_path(chain):
                record(node, None)
        elif isinstance(node, ast.Name) and node.id in environ_names:
            record(node, None)
    return references


def rule_35_secrets(corpus: Corpus) -> list[str]:
    """
    Rule 35: secrets reach module code as applied settings, not os.environ.

    The statically checkable clause: module code calls neither ``os.getenv``
    nor ``os.environ``; orgs' RLS boot guard reading core's two runtime-role
    variables in ``checks.py`` is the one listed exception (it runs before
    settings load).
    """
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            for lineno, variable in _environ_references(_parse(text)):
                if (
                    module.name == "orgs"
                    and rel == "checks.py"
                    and variable in CORE_RUNTIME_ROLE_ENV_VARS
                ):
                    continue
                detail = f" ({variable})" if variable else ""
                violations.append(
                    f"rule 35: {module.name}: {rel}:{lineno} uses os.getenv/os.environ"
                    f"{detail} instead of an applied setting"
                )
    return violations


def rule_39_module_dependencies(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    known = {module.name for module in corpus.modules}
    for module in corpus.modules:
        if "implies" in module.manifest:
            violations.append(f"rule 39: {module.name}: retired implies key present")
        required = module.manifest.get("required_modules", [])
        if not isinstance(required, list):
            violations.append(f"rule 39: {module.name}: required_modules must be a list")
            continue
        for entry in required:
            if not isinstance(entry, str) or not SNAKE_CASE.match(entry):
                violations.append(
                    f"rule 39: {module.name}: required module {entry!r} is not a bare name"
                )
            elif entry not in known:
                violations.append(f"rule 39: {module.name}: unknown required module {entry!r}")
    return violations


def _mypy_effective_option(key: str, value: str) -> tuple[str, str]:
    """
    Return mypy's effective option key and value for an alias spelling.

    mypy maps ``allow_redefinition_new`` to ``allow_redefinition`` and inverts
    ``no_<x>``, ``allow<X>`` (when ``disallow<X>`` exists), and ``disallow<X>``
    spellings, so the detector classifies the effective form, not the spelling.
    """
    lowered = value.strip().lower()

    def _canonical() -> str:
        if lowered in RULE_36_TRUE_VALUES:
            return "true"
        if lowered in RULE_36_FALSE_VALUES:
            return "false"
        return lowered

    def _inverted() -> str:
        canonical = _canonical()
        if canonical == "true":
            return "false"
        if canonical == "false":
            return "true"
        return canonical

    if key == "allow_redefinition_new":
        return "allow_redefinition", _canonical()
    if key.startswith("no_") and key[3:] in RULE_36_KNOWN_EFFECTIVE_KEYS:
        return key[3:], _inverted()
    if key.startswith("allow") and f"dis{key}" in RULE_36_KNOWN_EFFECTIVE_KEYS:
        return f"dis{key}", _inverted()
    if key.startswith("disallow") and key[3:] in RULE_36_KNOWN_EFFECTIVE_KEYS:
        return key[3:], _inverted()
    return key, _canonical()


def _mypy_glob_targets_module(glob: str, package: str) -> bool:
    """
    Return whether a mypy per-module glob applies to a package's code.

    Mirrors mypy's two matching paths: a well-structured pattern (a concrete
    name or a trailing ``.*``) matches its own module and submodules, while an
    unstructured pattern containing ``*`` is a regex over dotted components
    (``*`` matches zero or more components).  Path separators normalize to
    dots, as mypy's parser does.
    """
    glob = glob.replace(os.sep, ".")
    if os.altsep:
        glob = glob.replace(os.altsep, ".")
    package_parts = package.split(".")
    if "*" not in glob[:-1]:
        # Structured: exact entries match themselves; ``prefix.*`` matches the
        # prefix and every submodule.
        if glob.endswith(".*"):
            prefix_parts = glob[:-2].split(".")
            return (
                package_parts[: len(prefix_parts)] == prefix_parts
                or prefix_parts[: len(package_parts)] == package_parts
            )
        return glob == package or glob.startswith(f"{package}.")

    parts = glob.split(".")

    def matches(path_parts: list[str]) -> bool:
        def rec(pattern_index: int, path_index: int) -> bool:
            if pattern_index == len(parts):
                return path_index == len(path_parts)
            part = parts[pattern_index]
            if part == "*":
                return any(
                    rec(pattern_index + 1, path_index + consumed)
                    for consumed in range(len(path_parts) - path_index + 1)
                )
            return (
                path_index < len(path_parts)
                and path_parts[path_index] == part
                and rec(pattern_index + 1, path_index + 1)
            )

        return rec(0, 0)

    if matches(package_parts):
        return True

    def prefix_matches(length: int) -> bool:
        def rec(pattern_index: int, path_index: int) -> bool:
            if pattern_index == length:
                return path_index == len(package_parts)
            part = parts[pattern_index]
            if part == "*":
                return any(
                    rec(pattern_index + 1, path_index + consumed)
                    for consumed in range(len(package_parts) - path_index + 1)
                )
            return (
                path_index < len(package_parts)
                and package_parts[path_index] == part
                and rec(pattern_index + 1, path_index + 1)
            )

        return rec(0, 0)

    for split in range(len(parts)):
        if not prefix_matches(split):
            continue
        suffix = [part if part != "*" else "probe" for part in parts[split:]]
        if matches([*package_parts, *suffix]):
            return True
    return False


def rule_36_typecheck_config(corpus: Corpus) -> list[str]:
    """Rule 36: one root mypy.ini section per module, within the allowed set."""
    violations: list[str] = []
    parser = configparser.RawConfigParser()
    if corpus.mypy_ini.strip():
        parser.read_string(corpus.mypy_ini)
    for module in corpus.modules:
        section = RULE_36_SECTION_TEMPLATE.format(module=module.name)
        module_glob = RULE_36_MODULE_GLOB.format(module=module.name)
        targeting: list[str] = []
        for name in parser.sections():
            if not name.startswith("mypy-"):
                continue
            globs = [glob.strip() for glob in name[5:].split(",")]
            if any(_mypy_glob_targets_module(glob, module_glob) for glob in globs):
                targeting.append(name)
        for extra in sorted(name for name in targeting if name != section):
            violations.append(
                f"rule 36: {module.name}: mypy.ini declares an extra section [{extra}]"
            )
        if section not in targeting:
            violations.append(f"rule 36: {module.name}: mypy.ini has no [{section}] section")
            continue
        for key, value in parser.items(section):
            if key in RULE_36_FORBIDDEN_SECTION_KEYS:
                violations.append(
                    f"rule 36: {module.name}: mypy.ini section key {key!r} is not allowed"
                )
                continue
            if key == "disable_error_code":
                codes = {code.strip() for code in re.split(r"[,\n]", value) if code.strip()}
                unexpected = sorted(codes - RULE_36_ALLOWED_DISABLED_CODES)
                if unexpected:
                    violations.append(
                        f"rule 36: {module.name}: mypy.ini disables {', '.join(unexpected)}"
                    )
                continue
            effective_key, effective_value = _mypy_effective_option(key, value)
            if effective_key in RULE_36_ALLOWED_RELAXATION_KEYS:
                continue
            if RULE_36_RELAXED_VALUES.get(effective_key) == effective_value or (
                effective_key == "follow_imports"
                and effective_value in RULE_36_RELAXED_FOLLOW_IMPORTS
            ):
                violations.append(
                    f"rule 36: {module.name}: mypy.ini section {key!r} relaxes "
                    "outside the allowed set"
                )
    return violations
