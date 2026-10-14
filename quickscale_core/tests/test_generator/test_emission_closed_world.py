"""Closed-world emission test: user-owned emitted files carry no module wiring.

Module Conventions rule 37's literal-list check, applied to the generator's
emission mapping: no Django-side user-owned emitted file may enumerate module
names or name a module URL (a namespaced route name, a module-stemmed flat
name, or a mount/route alternation), and no user-owned emitted TypeScript file
may declare the shipped module set (a typed key block, a quoted name list, a
union, or a complete flag object) or name a module route — the set lives in
the generated managed seam declaration and key manifest
(``frontend/src/quickscaleSeam.d.ts`` and ``frontend/src/quickscaleSeam.keys.ts``),
and the theme's hooks import its types from there (SA276).  A single module
reference — a gate, a card entry, a navigation key — is rule 37's allowed
theme surface and is not flagged.  Module wiring (URL includes, shell routes,
template URLs) reaches a project only through the versioned
``quickscale_core.runtime`` library and the managed ``urls_modules.py`` /
``settings/modules.py`` files that ``apply`` regenerates, so a module release
changes no user-owned file.

The scanned set is derived from ``get_generator_emission_mapping`` (the closed
world), not a hand-maintained path list; the managed wiring files and the
generated seam files are the documented exclusions.  Each detector has a
control case below proving it rejects the wiring shapes it exists to catch.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from quickscale_core.contracts.module_catalog import MODULE_CATALOG
from quickscale_core.generator import ProjectGenerator, get_generator_emission_mapping
from quickscale_core.runtime.seam import (
    SEAM_DECLARATION_RELATIVE_PATH,
    SEAM_KEY_MANIFEST_RELATIVE_PATH,
    seam_modules,
)

_PROJECT_NAME = "emission_closed_world"
_TEMPLATE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "quickscale_core"
    / "generator"
    / "templates"
)

#: The managed wiring files ``apply`` regenerates: they own the module
#: wiring by design and are not user-owned.
_MANAGED_PACKAGE_PATHS = frozenset({"settings/modules.py", "urls_modules.py"})

_MODULE_NAMES = frozenset(entry.name for entry in MODULE_CATALOG)

#: The shipped module flag set: every catalog module the seam reports as a
#: boolean flag (``orgs`` carries none; rule 31).
_MODULE_FLAG_KEYS = frozenset(module.name for module in seam_modules())

#: The generated managed seam files: the module set lives there by design.
_MANAGED_SEAM_PATHS = frozenset(
    {SEAM_DECLARATION_RELATIVE_PATH, SEAM_KEY_MANIFEST_RELATIVE_PATH}
)

#: A module's namespaced URL name (``quickscale_billing:pricing_page``).
_MODULE_URL_NAME = re.compile(
    r"quickscale_(?:modules_)?(?:" + "|".join(sorted(_MODULE_NAMES)) + r"):"
)

#: A module-stemmed flat name (``quickscale_crm_shell``, a shell route, and
#: likewise a command, cache key, or event name carrying the module stem).
_MODULE_FLAT_NAME = re.compile(
    r"quickscale_(?:" + "|".join(sorted(_MODULE_NAMES)) + r")_[a-z]"
)

_TEMPLATE_BRACKET_LITERAL = re.compile(r"[\[(]([^\])]*)[\])]")
_TEMPLATE_QUOTED_NAME = re.compile(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]")
_TEMPLATE_PIPE_GROUP = re.compile(r"\((?:\?:)?([A-Za-z0-9_|]+)\)")

#: A TypeScript type declaration whose body can enumerate module keys
#: (``interface QuickScaleModules {``, ``type Seam = {``).
_TS_TYPE_BLOCK = re.compile(r"(?:interface|type)\s+\w+(?:\s*=\s*)?\s*\{")

#: One typed module-key member inside such a block (``auth: boolean``).
_TS_MEMBER = re.compile(
    r"^\s*(?:readonly\s+)?(" + "|".join(sorted(_MODULE_NAMES)) + r")\s*\??\s*:\s*"
    r"(?:boolean|string)\b",
    re.MULTILINE,
)

#: Two or more quoted module names joined by commas or pipes in one literal
#: run (``['auth', 'blog']``, ``'crm' | 'forms'``).
_TS_QUOTED_NAME = "['\"](?:" + "|".join(sorted(_MODULE_NAMES)) + ")['\"]"
_TS_NAME_RUN = re.compile(_TS_QUOTED_NAME + r"(?:\s*[,|]\s*" + _TS_QUOTED_NAME + r")+")

#: A key in a TypeScript object or type literal (``auth: false``,
#: ``'crm': '/crm'``), including members that open a line.
_TS_LITERAL_KEY = re.compile(
    r"(?:^|[,{;])\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*[?:]",
    re.MULTILINE,
)


def _scan_kind(emitted_path: str, package_name: str) -> str | None:
    """Return the detector kind for an emitted path, or ``None`` when unscanned.

    Django-side Python means every emitted ``.py`` file outside the two
    managed wiring files: the project package, ``manage.py``, and the test
    scaffold all count.  Django-side templates are the emitted HTML under
    ``templates/``.  User-owned TypeScript is every emitted ``.ts``/``.tsx``
    file under ``frontend/`` except the generated managed seam files, which
    carry the module set by design (SA276).
    """
    if emitted_path in _MANAGED_SEAM_PATHS:
        return None
    if emitted_path.endswith((".ts", ".tsx")):
        return "typescript" if emitted_path.startswith("frontend/") else None
    if emitted_path.endswith(".py"):
        if emitted_path.startswith("frontend/"):
            return None
        if emitted_path in {
            f"{package_name}/{relative}" for relative in _MANAGED_PACKAGE_PATHS
        }:
            return None
        return "python"
    if emitted_path.startswith("templates/") and emitted_path.endswith(".html"):
        return "template"
    return None


def _line_number(text: str, index: int) -> int:
    """Return the 1-based line number of an offset in *text*."""
    return text.count(chr(10), 0, index) + 1


def _string_violations(value: str, lineno: int) -> list[str]:
    """Return the module-wiring shapes inside one string constant."""
    violations: list[str] = []
    if _MODULE_URL_NAME.search(value):
        violations.append(f"line {lineno}: module URL name {value!r}")
    elif _MODULE_FLAT_NAME.search(value):
        violations.append(f"line {lineno}: module-stemmed name {value!r}")
    for match in _TEMPLATE_PIPE_GROUP.finditer(value):
        names = sorted(
            part for part in match.group(1).split("|") if part in _MODULE_NAMES
        )
        if len(names) >= 2:
            violations.append(
                f"line {lineno}: pipe alternation enumerates module names: "
                f"{', '.join(names)}"
            )
    return violations


def _python_violations(text: str) -> list[str]:
    """Return module-wiring violations in a Python source's string constants."""
    violations: list[str] = []
    tree = ast.parse(text)
    assigned_collections: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            assigned_collections.add(id(node.value))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            assigned_collections.add(id(node.value))
        elif isinstance(node, ast.Return) and node.value is not None:
            assigned_collections.add(id(node.value))

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            violations.extend(_string_violations(node.value, node.lineno))
            continue
        if not isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
            continue
        names = sorted(
            {
                inner.value
                for inner in ast.walk(node)
                if isinstance(inner, ast.Constant)
                and isinstance(inner.value, str)
                and inner.value in _MODULE_NAMES
            }
        )
        if len(names) >= 2 or (names and id(node) in assigned_collections):
            violations.append(
                f"line {node.lineno}: literal collection enumerates module "
                f"names: {', '.join(names)}"
            )
    return violations


def _template_violations(text: str) -> list[str]:
    """Return module-wiring violations found in a Django template's text."""
    violations: list[str] = []
    for match in _MODULE_URL_NAME.finditer(text):
        violations.append(
            f"line {_line_number(text, match.start())}: module URL name "
            f"{match.group(0)!r}"
        )
    for match in _MODULE_FLAT_NAME.finditer(text):
        violations.append(
            f"line {_line_number(text, match.start())}: module-stemmed name "
            f"{match.group(0)!r}"
        )
    for match in _TEMPLATE_BRACKET_LITERAL.finditer(text):
        names = sorted(
            {
                quoted.group(1)
                for quoted in _TEMPLATE_QUOTED_NAME.finditer(match.group(1))
                if quoted.group(1) in _MODULE_NAMES
            }
        )
        if len(names) >= 2:
            violations.append(
                f"line {_line_number(text, match.start())}: literal "
                f"collection enumerates module names: {', '.join(names)}"
            )
    for match in _TEMPLATE_PIPE_GROUP.finditer(text):
        names = sorted(
            part for part in match.group(1).split("|") if part in _MODULE_NAMES
        )
        if len(names) >= 2:
            violations.append(
                f"line {_line_number(text, match.start())}: pipe "
                f"alternation enumerates module names: {', '.join(names)}"
            )
    return violations


def _strip_ts_comments(text: str) -> str:
    """Return *text* with line and block comments removed.

    The detector reads declarations, not prose: a control documents the
    ignored comment shapes.  The heuristic is deliberately simple — it can
    strip the tail of a string literal containing ``//``, which only removes
    text from the scan, never adds any.
    """
    without_line_comments = re.sub(r"//[^\n]*", "", text)
    return re.sub(r"/\*.*?\*/", "", without_line_comments, flags=re.DOTALL)


def _ts_type_blocks(text: str) -> Iterator[str]:
    """Yield each ``interface``/``type`` brace block's full text."""
    for match in _TS_TYPE_BLOCK.finditer(text):
        depth = 0
        for index in range(match.end() - 1, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    yield text[match.start() : index + 1]
                    break


def _ts_brace_spans(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(offset, span_text)`` for every brace span, nested included."""
    stack: list[int] = []
    for index, char in enumerate(text):
        if char == "{":
            stack.append(index)
        elif char == "}" and stack:
            start = stack.pop()
            yield start, text[start : index + 1]


def _typescript_violations(text: str) -> list[str]:
    """Return module-wiring violations in one TypeScript source file."""
    violations: list[str] = []
    clean = _strip_ts_comments(text)
    for match in _MODULE_URL_NAME.finditer(clean):
        violations.append(
            f"line {_line_number(clean, match.start())}: module URL name "
            f"{match.group(0)!r}"
        )
    for match in _MODULE_FLAT_NAME.finditer(clean):
        violations.append(
            f"line {_line_number(clean, match.start())}: module-stemmed name "
            f"{match.group(0)!r}"
        )
    for match in _TS_NAME_RUN.finditer(clean):
        violations.append(
            f"line {_line_number(clean, match.start())}: literal list "
            f"enumerates module names: {match.group(0)!r}"
        )
    for block in _ts_type_blocks(clean):
        names = sorted({member.group(1) for member in _TS_MEMBER.finditer(block)})
        if len(names) >= 2:
            violations.append("type block enumerates module names: " + ", ".join(names))
    for offset, span in _ts_brace_spans(clean):
        keys = {match.group(1) for match in _TS_LITERAL_KEY.finditer(span)}
        if _MODULE_FLAG_KEYS <= keys:
            violations.append(
                f"line {_line_number(clean, offset)}: literal duplicates the "
                "shipped module flag set"
            )
    return violations


# ---------------------------------------------------------------------------
# Controls: each detector rejects the wiring shape it exists to catch.
# ---------------------------------------------------------------------------


def test_python_detector_rejects_a_module_name_collection() -> None:
    assert _python_violations('BUCKETS = ["blog", "forms"]\n')


def test_python_detector_rejects_a_singleton_registry() -> None:
    assert _python_violations('MODULE_URLS = {"billing": "/billing/"}\n')


def test_python_detector_rejects_a_module_url_name() -> None:
    assert _python_violations('reverse("quickscale_billing:pricing_page")\n')
    assert _python_violations('reverse("quickscale_crm_shell")\n')


def test_python_detector_rejects_a_namespaced_f_string() -> None:
    assert _python_violations('reverse(f"quickscale_blog:{name}")\n')


def test_python_detector_rejects_a_module_alternation() -> None:
    assert _python_violations(
        're_path(r"^orgs/(?!api(?:/|$))[^/]+/(blog|listings|members|settings)/?$", v)\n'
    )


def test_python_detector_accepts_single_references() -> None:
    # A single module name inside a call is a reference, not an enumeration;
    # a dotted package path and a bare app label are not URL names.
    assert not _python_violations('label = getattr(services, "blog")\n')
    assert not _python_violations('include("quickscale_modules_blog.urls")\n')
    assert not _python_violations('APP_LABEL = "quickscale_modules_blog"\n')


def test_template_detector_rejects_a_name_literal_collection() -> None:
    assert _template_violations('{% if kind in ["blog", "forms"] %}\n')


def test_template_detector_rejects_a_pipe_alternation() -> None:
    assert _template_violations('{% if kind in "(auth|billing)" %}\n')


def test_template_detector_rejects_a_module_url_name() -> None:
    assert _template_violations("{% url 'quickscale_blog:post_list' %}\n")
    assert _template_violations("{% url 'quickscale_crm_shell' %}\n")


def test_template_detector_accepts_single_references() -> None:
    assert not _template_violations("{% if kind == 'blog' %}\n")
    assert not _template_violations(
        "{% if 'quickscale_modules_social' in settings.INSTALLED_APPS %}\n"
    )


def test_typescript_detector_rejects_a_module_name_list() -> None:
    assert _typescript_violations("const KEYS = ['auth', 'blog']\n")


def test_typescript_detector_rejects_a_module_name_union() -> None:
    assert _typescript_violations("type SeamName = 'crm' | 'forms'\n")


def test_typescript_detector_rejects_a_typed_module_key_block() -> None:
    assert _typescript_violations(
        "interface QuickScaleModules {\n  auth: boolean\n  blog: boolean\n}\n"
    )


def test_typescript_detector_rejects_a_module_url_name() -> None:
    assert _typescript_violations("const route = 'quickscale_billing:pricing_page'\n")
    assert _typescript_violations("const shell = 'quickscale_crm_shell'\n")


def test_typescript_detector_rejects_a_complete_flag_object() -> None:
    body = "\n".join(f"    {name}: false," for name in sorted(_MODULE_FLAG_KEYS))
    assert _typescript_violations("const config = {\n" + body + "\n}\n")


def test_typescript_detector_accepts_single_references() -> None:
    # One module named at a time is a reference — a gate, a card entry, or a
    # query key — not a seam enumeration.
    assert not _typescript_violations("const card = { key: 'auth', label: 'Auth' }\n")
    assert not _typescript_violations("if (modules.crm) { openCrm() }\n")
    assert not _typescript_violations("const flags = { auth: false, blog: false }\n")
    # A path table's value overrides carry entries, not the module flag set.
    assert not _typescript_violations(
        "const paths = modulePaths({ crm: '/crm/', social: '/social',"
        " analytics: '/analytics/' })\n"
    )


def test_typescript_detector_ignores_comments() -> None:
    assert not _typescript_violations("// ['auth', 'blog']\n/* 'crm' | 'forms' */\n")


# ---------------------------------------------------------------------------
# The closed-world emission check.
# ---------------------------------------------------------------------------


def test_user_owned_emissions_carry_no_module_wiring(tmp_path: Path) -> None:
    """No user-owned emitted file enumerates or names modules."""
    mapping = get_generator_emission_mapping(
        _TEMPLATE_ROOT, theme="showcase_react", package_name=_PROJECT_NAME
    )
    assert mapping, "the emission mapping must be non-empty"

    output_path = tmp_path / _PROJECT_NAME
    ProjectGenerator(theme="showcase_react").generate(_PROJECT_NAME, output_path)

    detectors = {
        "python": _python_violations,
        "template": _template_violations,
        "typescript": _typescript_violations,
    }
    scanned: list[str] = []
    missing: list[str] = []
    violations: list[str] = []
    for emitted_path in sorted(mapping):
        kind = _scan_kind(emitted_path, _PROJECT_NAME)
        if kind is None:
            continue
        scanned.append(emitted_path)
        file_path = output_path / emitted_path
        if not file_path.exists():
            missing.append(emitted_path)
            continue
        found = detectors[kind](file_path.read_text())
        violations.extend(f"{emitted_path}: {violation}" for violation in found)

    assert not missing, f"emitted files missing from the generated tree: {missing}"
    assert scanned, "the user-owned scan set must be non-empty"
    assert not violations, (
        "module wiring leaked into user-owned emissions:\n" + "\n".join(violations)
    )


def test_scan_set_excludes_only_the_managed_files() -> None:
    """The scan covers user-owned emissions; managed files stay out."""
    mapping = get_generator_emission_mapping(
        _TEMPLATE_ROOT, theme="showcase_react", package_name=_PROJECT_NAME
    )
    kinds = {path: _scan_kind(path, _PROJECT_NAME) for path in mapping}

    assert kinds.get(f"{_PROJECT_NAME}/urls_modules.py") is None
    assert kinds.get(f"{_PROJECT_NAME}/settings/modules.py") is None
    assert kinds.get(SEAM_DECLARATION_RELATIVE_PATH) is None
    assert kinds.get(SEAM_KEY_MANIFEST_RELATIVE_PATH) is None
    assert SEAM_DECLARATION_RELATIVE_PATH in mapping
    assert SEAM_KEY_MANIFEST_RELATIVE_PATH in mapping

    assert kinds.get(f"{_PROJECT_NAME}/urls.py") == "python"
    assert kinds.get(f"{_PROJECT_NAME}/context_processors.py") == "python"
    assert kinds.get("templates/index.html") == "template"
    # Root and test-scaffold Python are Django-side user-owned too.
    assert kinds.get("manage.py") == "python"
    assert kinds.get("tests/conftest.py") == "python"
    assert kinds.get("tests/test_example.py") == "python"
    # The theme's TypeScript is user-owned and scanned, tests included.
    assert kinds.get("frontend/src/hooks/useModules.ts") == "typescript"
    assert kinds.get("frontend/src/lib/validateQuickScaleSeam.ts") == "typescript"
    assert kinds.get("frontend/src/test/useModules.test.tsx") == "typescript"


@pytest.mark.parametrize("module_name", sorted(_MODULE_NAMES))
def test_module_url_name_detector_matches_each_module(module_name: str) -> None:
    """The URL-name detectors cover every shipped module's names."""
    assert _MODULE_URL_NAME.search(f"quickscale_{module_name}:route")
    assert _MODULE_FLAT_NAME.search(f"quickscale_{module_name}_shell")
