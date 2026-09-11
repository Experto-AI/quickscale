"""Structural and contract tests for first-party request identity consumers."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from django.test import override_settings

from quickscale_modules_orgs.current_org import ClientIPThrottleMixin, get_client_ip


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_SOURCE_ROOT = REPO_ROOT / "quickscale_modules"
GENERATED_SETTINGS_ROOT = (
    REPO_ROOT
    / "quickscale_core"
    / "src"
    / "quickscale_core"
    / "generator"
    / "templates"
)
DRF_THROTTLE_BASES = {
    "BaseThrottle",
    "SimpleRateThrottle",
    "AnonRateThrottle",
    "UserRateThrottle",
    "ScopedRateThrottle",
}


@dataclass(frozen=True)
class ClassRecord:
    path: Path
    name: str
    qualname: str
    bases: tuple[str, ...]
    node: ast.ClassDef
    drf_aliases: dict[str, str]


@dataclass(frozen=True)
class RegistrationRecord:
    path: Path
    owner: str
    names: tuple[str, ...]
    line: int


@dataclass(frozen=True)
class ResolverCallRecord:
    path: Path
    owner: str
    line: int


class _SourceInventory(ast.NodeVisitor):
    """Collect class, registration, alias, and resolver-call topology."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.class_stack: list[str] = []
        self.function_stack: list[str] = []
        self.drf_aliases: dict[str, str] = {}
        self.get_client_ip_aliases: set[str] = set()
        self.current_org_module_aliases: set[str] = set()
        self.classes: list[ClassRecord] = []
        self.aliases: list[tuple[str, str, int]] = []
        self.registrations: list[RegistrationRecord] = []
        self.resolver_calls: list[ResolverCallRecord] = []

    def _owner(self) -> str:
        return ".".join(self.class_stack + self.function_stack) or "<module>"

    @staticmethod
    def _expression_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ast.unparse(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if module == "rest_framework.throttling":
            for imported in node.names:
                if imported.name == "*":
                    continue
                local_name = imported.asname or imported.name
                self.drf_aliases[local_name] = imported.name
                if imported.asname:
                    self.aliases.append((local_name, imported.name, node.lineno))
        elif module == "quickscale_modules_orgs.current_org":
            for imported in node.names:
                if imported.name == "get_client_ip":
                    self.get_client_ip_aliases.add(imported.asname or imported.name)
        elif module == "quickscale_modules_orgs":
            for imported in node.names:
                if imported.name == "current_org":
                    self.current_org_module_aliases.add(
                        imported.asname or imported.name
                    )
        if module.endswith("throttles"):
            for imported in node.names:
                if imported.name.endswith("Throttle") and imported.asname:
                    self.aliases.append((imported.asname, imported.name, node.lineno))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for imported in node.names:
            if imported.name == "rest_framework.throttling":
                local_name = imported.asname or imported.name.split(".")[-1]
                self.drf_aliases[local_name] = "*"
                if imported.asname:
                    self.aliases.append((local_name, imported.name, node.lineno))
            if imported.name == "quickscale_modules_orgs.current_org":
                self.current_org_module_aliases.add(
                    imported.asname or imported.name.split(".")[-1]
                )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualname = ".".join(self.class_stack + [node.name])
        self.classes.append(
            ClassRecord(
                path=self.path,
                name=node.name,
                qualname=qualname,
                bases=tuple(self._expression_name(base) for base in node.bases),
                node=node,
                drf_aliases=dict(self.drf_aliases),
            )
        )
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            throttle_target = (
                isinstance(target, ast.Name) and target.id == "throttle_classes"
            ) or (
                isinstance(target, ast.Attribute) and target.attr == "throttle_classes"
            )
            if throttle_target:
                names: tuple[str, ...] = ()
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    names = tuple(
                        self._expression_name(item) for item in node.value.elts
                    )
                self.registrations.append(
                    RegistrationRecord(
                        path=self.path,
                        owner=self._owner(),
                        names=names,
                        line=node.lineno,
                    )
                )
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Name):
                if target.id.endswith("Throttle") or node.value.id.endswith("Throttle"):
                    self.aliases.append((target.id, node.value.id, node.lineno))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        direct_call = isinstance(node.func, ast.Name) and (
            node.func.id in self.get_client_ip_aliases
        )
        module_call = (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "get_client_ip"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in self.current_org_module_aliases
        )
        if direct_call or module_call:
            self.resolver_calls.append(
                ResolverCallRecord(
                    path=self.path,
                    owner=self._owner(),
                    line=node.lineno,
                )
            )
        self.generic_visit(node)


def _runtime_sources() -> list[Path]:
    return sorted(MODULE_SOURCE_ROOT.glob("*/src/**/*.py"))


def _collect_inventory() -> tuple[
    list[ClassRecord],
    list[tuple[str, str, int]],
    list[RegistrationRecord],
    list[ResolverCallRecord],
]:
    classes: list[ClassRecord] = []
    aliases: list[tuple[str, str, int]] = []
    registrations: list[RegistrationRecord] = []
    resolver_calls: list[ResolverCallRecord] = []
    for path in _runtime_sources():
        visitor = _SourceInventory(path)
        visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
        classes.extend(visitor.classes)
        aliases.extend(
            (
                str(path.relative_to(REPO_ROOT)),
                f"{local_name}={imported_name}",
                line,
            )
            for local_name, imported_name, line in visitor.aliases
        )
        registrations.extend(visitor.registrations)
        resolver_calls.extend(visitor.resolver_calls)
    return classes, aliases, registrations, resolver_calls


def _base_is_drf_throttle(record: ClassRecord) -> bool:
    for base in record.bases:
        if base in DRF_THROTTLE_BASES:
            return True
        if record.drf_aliases.get(base) in DRF_THROTTLE_BASES:
            return True
    return False


def _is_drf_throttle_class(record: ClassRecord, classes: list[ClassRecord]) -> bool:
    if _base_is_drf_throttle(record):
        return True

    class_by_name: dict[str, list[ClassRecord]] = {}
    for candidate in classes:
        class_by_name.setdefault(candidate.name, []).append(candidate)

    visiting: set[tuple[Path, str]] = set()

    def inherits(candidate: ClassRecord) -> bool:
        key = (candidate.path, candidate.qualname)
        if key in visiting:
            return False
        visiting.add(key)
        try:
            if _base_is_drf_throttle(candidate):
                return True
            for base in candidate.bases:
                for parent in class_by_name.get(base, []):
                    if inherits(parent):
                        return True
            return False
        finally:
            visiting.remove(key)

    return inherits(record)


def test_client_ip_throttle_mixin_delegates_without_framework_coupling() -> None:
    """The reusable mixin delegates identity and does not import DRF."""
    current_org_path = (
        MODULE_SOURCE_ROOT
        / "orgs"
        / "src"
        / "quickscale_modules_orgs"
        / "current_org.py"
    )
    tree = ast.parse(current_org_path.read_text(encoding="utf-8"))
    framework_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and (
            (
                isinstance(node, ast.ImportFrom)
                and (node.module or "").startswith("rest_framework")
            )
            or (
                isinstance(node, ast.Import)
                and any(alias.name.startswith("rest_framework") for alias in node.names)
            )
        )
    ]
    assert framework_imports == []
    assert "djangorestframework" not in (
        MODULE_SOURCE_ROOT.joinpath("orgs", "pyproject.toml")
        .read_text(encoding="utf-8")
        .lower()
    )

    request = SimpleNamespace(
        META={
            "REMOTE_ADDR": "10.0.0.9",
            "HTTP_X_FORWARDED_FOR": "198.51.100.9, 10.0.0.9",
        }
    )
    with override_settings(USE_X_FORWARDED_FOR=True, TRUSTED_PROXY_COUNT=1):
        assert ClientIPThrottleMixin().get_ident(request) == get_client_ip(request)


def test_first_party_drf_throttle_inventory_is_closed_and_compliant() -> None:
    """Discover aliases, indirect subclasses, registrations, and callers."""
    classes, aliases, registrations, resolver_calls = _collect_inventory()
    throttle_classes = sorted(
        (str(record.path.relative_to(REPO_ROOT)), record.name)
        for record in classes
        if _is_drf_throttle_class(record, classes)
    )
    assert throttle_classes == [
        (
            "quickscale_modules/forms/src/quickscale_modules_forms/throttles.py",
            "FormSubmitThrottle",
        )
    ], f"Unexpected first-party throttle inventory: {throttle_classes!r}"

    form_throttle = next(
        record for record in classes if record.name == "FormSubmitThrottle"
    )
    assert form_throttle.bases == ("ClientIPThrottleMixin", "ScopedRateThrottle")
    assert [
        node.name
        for node in form_throttle.node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ] == ["get_rate", "get_cache_key"]

    relative_forms_views = (
        "quickscale_modules/forms/src/quickscale_modules_forms/views.py"
    )
    assert [
        (
            str(record.path.relative_to(REPO_ROOT)),
            record.owner,
            record.names,
        )
        for record in registrations
    ] == [(relative_forms_views, "FormSubmitAPIView", ("FormSubmitThrottle",))]

    assert aliases == [], f"Unexpected first-party throttle aliases: {aliases!r}"

    expected_resolver_calls = sorted(
        [
            (
                "quickscale_modules/forms/src/quickscale_modules_forms/views.py",
                "FormSubmitAPIView.create",
                293,
            ),
            (
                "quickscale_modules/forms/src/quickscale_modules_forms/views.py",
                "FormSubmitAPIView.create",
                319,
            ),
            (
                "quickscale_modules/blog/src/quickscale_modules_blog/views.py",
                "_get_blog_api_rate_limit_ident",
                290,
            ),
        ]
    )
    actual_resolver_calls = sorted(
        (
            str(record.path.relative_to(REPO_ROOT)),
            record.owner,
            record.line,
        )
        for record in resolver_calls
    )
    assert actual_resolver_calls == expected_resolver_calls

    generated_default_hits = [
        str(path.relative_to(REPO_ROOT))
        for path in GENERATED_SETTINGS_ROOT.rglob("*")
        if path.is_file()
        and "DEFAULT_THROTTLE_CLASSES" in path.read_text(encoding="utf-8")
    ]
    assert generated_default_hits == []
