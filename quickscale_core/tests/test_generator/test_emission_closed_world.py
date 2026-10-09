"""Closed-world emission test: user-owned Django-side files carry no module wiring.

Module Conventions rule 37's literal-list check, applied to the generator's
emission mapping: no Django-side user-owned emitted file may enumerate module
names or name a module URL (a namespaced route name, a module-stemmed flat
name, or a mount/route alternation).  Module wiring (URL includes, shell
routes, template URLs) reaches a project only through the versioned
``quickscale_core.runtime`` library and the managed ``urls_modules.py`` /
``settings/modules.py`` files that ``apply`` regenerates, so a module release
changes no user-owned file.

The scanned set is derived from ``get_generator_emission_mapping`` (the
closed world), not a hand-maintained path list; the managed wiring files and
the frontend theme sources are the documented exclusions.  Each detector has
a control case below proving it rejects the wiring shapes it exists to catch.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from quickscale_core.contracts.module_catalog import MODULE_CATALOG
from quickscale_core.generator import ProjectGenerator, get_generator_emission_mapping

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


def _is_scanned(emitted_path: str, package_name: str) -> bool:
    """Return whether an emitted path is Django-side and user-owned.

    Django-side Python means every emitted ``.py`` file outside the two
    managed wiring files: the project package, ``manage.py``, and the test
    scaffold all count.  Django-side templates are the emitted HTML under
    ``templates/``.  The frontend theme sources are rule 31's named
    exception and stay out.
    """
    if emitted_path.endswith(".py"):
        if emitted_path.startswith("frontend/"):
            return False
        return emitted_path not in {
            f"{package_name}/{relative}" for relative in _MANAGED_PACKAGE_PATHS
        }
    return emitted_path.startswith("templates/") and emitted_path.endswith(".html")


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


# ---------------------------------------------------------------------------
# The closed-world emission check.
# ---------------------------------------------------------------------------


def test_user_owned_django_side_emissions_carry_no_module_wiring(
    tmp_path: Path,
) -> None:
    """No user-owned Django-side emitted file enumerates or names modules."""
    mapping = get_generator_emission_mapping(
        _TEMPLATE_ROOT, theme="showcase_react", package_name=_PROJECT_NAME
    )
    assert mapping, "the emission mapping must be non-empty"

    output_path = tmp_path / _PROJECT_NAME
    ProjectGenerator(theme="showcase_react").generate(_PROJECT_NAME, output_path)

    scanned: list[str] = []
    missing: list[str] = []
    violations: list[str] = []
    for emitted_path in sorted(mapping):
        if not _is_scanned(emitted_path, _PROJECT_NAME):
            continue
        scanned.append(emitted_path)
        file_path = output_path / emitted_path
        if not file_path.exists():
            missing.append(emitted_path)
            continue
        text = file_path.read_text()
        found = (
            _python_violations(text)
            if emitted_path.endswith(".py")
            else _template_violations(text)
        )
        violations.extend(f"{emitted_path}: {violation}" for violation in found)

    assert not missing, f"emitted files missing from the generated tree: {missing}"
    assert scanned, "the Django-side user-owned scan set must be non-empty"
    assert not violations, (
        "module wiring leaked into user-owned emissions:\n" + "\n".join(violations)
    )


def test_scan_set_excludes_managed_wiring_and_frontend() -> None:
    """The scan covers Django-side user-owned Python and templates only."""
    mapping = get_generator_emission_mapping(
        _TEMPLATE_ROOT, theme="showcase_react", package_name=_PROJECT_NAME
    )
    scanned = {path for path in mapping if _is_scanned(path, _PROJECT_NAME)}

    assert f"{_PROJECT_NAME}/urls_modules.py" not in scanned
    assert f"{_PROJECT_NAME}/settings/modules.py" not in scanned
    assert not any(path.startswith("frontend/") for path in scanned)
    assert f"{_PROJECT_NAME}/urls.py" in scanned
    assert f"{_PROJECT_NAME}/context_processors.py" in scanned
    assert "templates/index.html" in scanned
    # Root and test-scaffold Python are Django-side user-owned too.
    assert "manage.py" in scanned
    assert "tests/conftest.py" in scanned
    assert "tests/test_example.py" in scanned


@pytest.mark.parametrize("module_name", sorted(_MODULE_NAMES))
def test_module_url_name_detector_matches_each_module(module_name: str) -> None:
    """The URL-name detectors cover every shipped module's names."""
    assert _MODULE_URL_NAME.search(f"quickscale_{module_name}:route")
    assert _MODULE_FLAT_NAME.search(f"quickscale_{module_name}_shell")
