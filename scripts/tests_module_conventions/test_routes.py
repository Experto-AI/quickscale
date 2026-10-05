"""Control cases for the routes module-convention rules."""

from __future__ import annotations

from dataclasses import replace

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _seam_corpus,
    _violations,
    _with_files,
    _with_mount,
)


def test_url_route_name_control() -> None:
    module = _golden_module()
    broken = _with_files(module, urls=module.files["urls.py"].replace("'index'", "'demo_list'"))
    violations = _violations(checker.rule_7_urls, broken)
    assert any("repeats the module" in violation for violation in violations)
    assert _violations(checker.rule_7_urls, module) == []


def test_url_mount_control() -> None:
    module = _golden_module()
    manifest = dict(module.manifest)
    manifest["derivation"] = {"wiring_projections": []}
    assert _violations(checker.rule_7_urls, replace(module, manifest=manifest))


def test_url_include_literal_control() -> None:
    module = _golden_module()
    broken_keyword = _with_files(
        module,
        adapter=(
            "def build():\n"
            "    return Wiring(url_includes=[['demo/', 'quickscale_modules_demo.urls']])\n"
        ),
    )
    assert any(
        "literal url_includes" in violation
        for violation in _violations(checker.rule_7_urls, broken_keyword)
    )
    broken_assignment = _with_files(
        module,
        adapter=(
            "def build():\n"
            "    url_includes = [['demo/', 'quickscale_modules_demo.urls']]\n"
            "    return url_includes\n"
        ),
    )
    assert any(
        "literal url_includes" in violation
        for violation in _violations(checker.rule_7_urls, broken_assignment)
    )
    broken_annotated = _with_files(
        module,
        adapter=(
            "def build():\n"
            "    url_includes: list = [['demo/', 'quickscale_modules_demo.urls']]\n"
            "    return url_includes\n"
        ),
    )
    assert any(
        "literal url_includes" in violation
        for violation in _violations(checker.rule_7_urls, broken_annotated)
    )
    empty_literals = _with_files(
        module,
        adapter=(
            "def build():\n"
            "    url_includes = ()\n"
            "    if not url_includes:\n"
            "        return Wiring(url_includes=[])\n"
            "    return url_includes\n"
        ),
    )
    assert _violations(checker.rule_7_urls, empty_literals) == []
    annotated_empty = _with_files(
        module,
        adapter=("def build():\n    url_includes: list = []\n    return url_includes\n"),
    )
    assert _violations(checker.rule_7_urls, annotated_empty) == []


def test_url_mount_template_literal_control() -> None:
    """A mount literal in a generator `.j2` file fails rule 7 (gap 13)."""
    module = _golden_module()
    template = replace(
        _corpus(module),
        core_files={
            "generator/templates/project_name/sample.j2": ('re_path(r"^demo/?$", demo_shell)\n')
        },
    )
    assert any(
        "mount 'demo/' is written as a literal" in violation
        for violation in checker.rule_7_urls(template)
    )
    outside_root = replace(
        _corpus(module),
        core_files={"generator/notes.j2": 're_path(r"^demo/?$", demo_shell)\n'},
    )
    assert checker.rule_7_urls(outside_root) == []
    assert checker.rule_7_urls(_corpus(module)) == []
    single_quoted = replace(
        _corpus(module),
        core_files={
            "generator/templates/project_name/sample.j2": ("re_path(r'^demo/?$', demo_shell)\n")
        },
    )
    assert any(
        "mount 'demo/' is written as a literal" in violation
        for violation in checker.rule_7_urls(single_quoted)
    )
    ordinary_string = replace(
        _corpus(module),
        core_files={
            "generator/templates/project_name/sample.j2": ('re_path("^demo/?$", demo_shell)\n')
        },
    )
    assert any(
        "mount 'demo/' is written as a literal" in violation
        for violation in checker.rule_7_urls(ordinary_string)
    )
    # A route whose path only shares the mount's prefix is not a copy of the
    # mount and must stay allowed.
    longer_prefix = replace(
        _corpus(module),
        core_files={
            "generator/templates/project_name/sample.j2": (
                're_path("^demographics/?$", demographics_shell)\n'
            )
        },
    )
    assert checker.rule_7_urls(longer_prefix) == []
    hyphenated_prefix = replace(
        _corpus(module),
        core_files={
            "generator/templates/project_name/sample.j2": (
                're_path("^demo-roll/?$", demo_roll_shell)\n'
                "re_path(r'^demo-roll/?$', demo_roll_shell)\n"
            )
        },
    )
    assert checker.rule_7_urls(hyphenated_prefix) == []
    html_literal = replace(
        _corpus(module),
        core_files={"generator/templates/project_name/sample.j2": '<a href="/demo/">Demo</a>\n'},
    )
    assert any(
        "mount 'demo/' is written as a literal" in violation
        for violation in checker.rule_7_urls(html_literal)
    )
    # A quoted path beneath the mount repeats the mount too.
    html_subpath_literal = replace(
        _corpus(module),
        core_files={
            "generator/templates/project_name/sample.j2": ('<a href="/demo/thanks/">Thanks</a>\n')
        },
    )
    assert any(
        "mount 'demo/' is written as a literal" in violation
        for violation in checker.rule_7_urls(html_subpath_literal)
    )
    quoted_longer_prefix = replace(
        _corpus(module),
        core_files={
            "generator/templates/project_name/sample.j2": (
                '<a href="/demographics/list/">Demographics</a>\n'
            )
        },
    )
    assert checker.rule_7_urls(quoted_longer_prefix) == []


def test_template_page_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{"templates/quickscale_demo/page.html": "<html><body>page</body></html>\n"},
    )
    violations = _violations(checker.rule_8_templates, broken)
    assert any("does not extend" in violation for violation in violations)
    assert any("emits <html>" in violation for violation in violations)
    assert _violations(checker.rule_8_templates, module) == []


def test_json_api_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.http import JsonResponse\n\n\ndef index():\n    return JsonResponse({})\n"
        ),
    )
    assert _violations(checker.rule_9_http_apis, broken)


def test_error_body_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views='def index():\n    return {"error": {"code": "x", "message": "y"}}\n',
    )
    assert _violations(checker.rule_9_http_apis, broken)


def test_throttle_scope_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{
            "throttles.py": ("class DemoThrottle:\n    scope = 'demo_api'\n    rate = '5/hour'\n"),
        },
    )
    violations = _violations(checker.rule_32_throttles, broken)
    assert any("scope" in violation for violation in violations)
    assert any("rate" in violation for violation in violations)


def test_template_assets_checked_without_pages() -> None:
    module = _golden_module()
    stripped = replace(
        module,
        files={
            key: value for key, value in module.files.items() if not key.startswith("templates/")
        }
        | {"static/demo/css/a.css": "body {}\n"},
    )
    assert any("root" in violation for violation in _violations(checker.rule_8_templates, stripped))


def test_page_must_fill_module_content_block() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{"templates/quickscale_demo/page.html": '{% extends "quickscale_demo/base.html" %}\n'},
    )
    assert any(
        "demo_content" in violation for violation in _violations(checker.rule_8_templates, broken)
    )


def test_page_may_not_extend_project_base_directly() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{
            "templates/quickscale_demo/page.html": (
                '{% extends "base.html" %}\n{% block demo_content %}{% endblock %}\n'
            )
        },
    )
    assert any(
        "does not extend" in violation
        for violation in _violations(checker.rule_8_templates, broken)
    )


def test_documentation_only_mentions_are_not_violations() -> None:
    module = _golden_module()
    documented = _with_files(
        module,
        views=(
            '"""Use DRF rather than JsonResponse, timezone.now() rather than '
            "datetime.now(), and never django.core.mail or send_mail here. "
            'Do not use gettext, RunSQL, or django.db.models.Index()."""\n'
        ),
    )
    assert _violations(checker.rule_9_http_apis, documented) == []
    assert _violations(checker.rule_14_model_basics, documented) == []
    assert _violations(checker.rule_20_email, documented) == []
    assert _violations(checker.rule_24_small_conventions, documented) == []
    assert _violations(checker.rule_32_throttles, documented) == []


def test_error_body_with_nonliteral_key_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "def index():\n    return {key: 1, 'error': {'code': 'invalid', 'message': 'bad'}}\n"
        ),
    )
    assert any(
        "error body" in violation for violation in _violations(checker.rule_9_http_apis, broken)
    )


def test_theme_seam_control() -> None:
    good = "{{ seam_module_flags }}\n{{ seam_module_paths }}\n"
    assert checker.rule_31_theme_seam(_seam_corpus(good)) == []
    missing = _seam_corpus("{{ seam_module_flags }}\n")
    assert any("does not render" in violation for violation in checker.rule_31_theme_seam(missing))
    literal_line = _seam_corpus('{{ seam_module_flags }}\n"demo": true,\n{{ seam_module_paths }}\n')
    assert any(
        "names module 'demo' literally" in violation
        for violation in checker.rule_31_theme_seam(literal_line)
    )
    bare_key = _seam_corpus("{{ seam_module_flags }}\ndemo: true,\n{{ seam_module_paths }}\n")
    assert any("bare key" in violation for violation in checker.rule_31_theme_seam(bare_key))
    absolute_mount = _seam_corpus("{{ seam_module_flags }}\n{{ seam_module_paths }}\n'/demo/'")
    assert any(
        "names module 'demo' literally" in violation
        for violation in checker.rule_31_theme_seam(absolute_mount)
    )
    empty_core = _corpus(_golden_module())
    assert checker.rule_31_theme_seam(empty_core) == []
    missing_template = replace(empty_core, core_files={"other.py": "x\n"})
    assert any(
        "carries no theme index.html.j2" in violation
        for violation in checker.rule_31_theme_seam(missing_template)
    )
    auth = _with_mount(_golden_module("auth"), "accounts/")
    accounts_literal = _seam_corpus(
        '{{ seam_module_flags }}\n{{ seam_module_paths }}\n<a href="/accounts/">Accounts</a>\n',
        auth,
    )
    assert any(
        "mount 'accounts/'" in violation
        for violation in checker.rule_31_theme_seam(accounts_literal)
    )
    named_url = _seam_corpus(
        "{{ seam_module_flags }}\n{{ seam_module_paths }}\n{% url 'quickscale_auth:login' %}\n",
        auth,
    )
    assert checker.rule_31_theme_seam(named_url) == []


def test_theme_seam_social_producer_control() -> None:
    """The public social producers carry the rendered seam, not module lines."""
    social_template = checker.THEME_SEAM_TEMPLATES[1]
    corpus = replace(
        _corpus(_golden_module()),
        core_files={
            checker.THEME_SEAM_TEMPLATE: ("{{ seam_module_flags }}\n{{ seam_module_paths }}\n"),
            social_template: ("{{ seam_module_flags }}\ndemo: true,\n{{ seam_module_paths }}\n"),
        },
    )
    violations = checker.rule_31_theme_seam(corpus)
    assert any(social_template in violation and "bare key" in violation for violation in violations)
    clean = replace(
        corpus,
        core_files={
            checker.THEME_SEAM_TEMPLATE: ("{{ seam_module_flags }}\n{{ seam_module_paths }}\n"),
            social_template: ("{{ seam_module_flags }}\n{{ seam_module_paths }}\n"),
        },
    )
    assert checker.rule_31_theme_seam(clean) == []
    override = replace(
        corpus,
        core_files={
            checker.THEME_SEAM_TEMPLATE: ("{{ seam_module_flags }}\n{{ seam_module_paths }}\n"),
            social_template: (
                '{{ seam_module_flags }}\n"demo": "/demo/",\n{{ seam_module_paths }}\n'
            ),
        },
    )
    assert any(
        "writes demo's mount 'demo/' literally" in violation
        for violation in checker.rule_31_theme_seam(override)
    )


def test_authorization_controls() -> None:
    module = _golden_module()
    assert _violations(checker.rule_19_authorization, module) == []
    staff = _with_files(module, views="def index(request, user):\n    return user.is_staff\n")
    assert any(
        "is_staff" in violation for violation in _violations(checker.rule_19_authorization, staff)
    )
    flag = _with_files(
        module,
        views='def index(request, user):\n    return getattr(user, "is_superuser", False)\n',
    )
    assert any(
        "is_superuser" in violation
        for violation in _violations(checker.rule_19_authorization, flag)
    )
    admin = _with_files(
        module,
        views=(
            "from rest_framework.permissions import IsAdminUser\n"
            "from rest_framework.views import APIView\n\n"
            "class IndexView(APIView):\n    permission_classes = [IsAdminUser]\n"
        ),
    )
    assert any(
        "IsAdminUser" in violation
        for violation in _violations(checker.rule_19_authorization, admin)
    )
    aliased_admin = _with_files(
        module,
        views=(
            "from rest_framework.permissions import IsAdminUser as AdminOnly\n"
            "from rest_framework.views import APIView\n\n"
            "class IndexView(APIView):\n    permission_classes = [AdminOnly]\n"
        ),
    )
    assert any(
        "IsAdminUser" in violation
        for violation in _violations(checker.rule_19_authorization, aliased_admin)
    )
    aliased_login = _with_files(
        module,
        views=(
            "from django.contrib.auth.views import redirect_to_login as login_redirect\n\n"
            "def index(request):\n    return login_redirect(request.get_full_path())\n"
        ),
    )
    assert any(
        "redirect_to_login" in violation
        for violation in _violations(checker.rule_19_authorization, aliased_login)
    )
    login = _with_files(
        module,
        views=(
            "from django.contrib.auth.views import redirect_to_login\n\n"
            "def index(request):\n    return redirect_to_login(request.get_full_path())\n"
        ),
    )
    assert any(
        "redirect_to_login" in violation
        for violation in _violations(checker.rule_19_authorization, login)
    )
    private_sibling = _with_files(
        module,
        **{
            "_view_invitation.py": (
                "from django.contrib.auth.views import redirect_to_login\n\n"
                "def index(request):\n"
                "    return redirect_to_login(request.get_full_path())\n"
            )
        },
    )
    assert any(
        "redirect_to_login" in violation
        for violation in _violations(checker.rule_19_authorization, private_sibling)
    )
    operator = _with_files(
        _golden_module("orgs"),
        **{
            "_view_context.py": (
                'def index(request, user):\n    return getattr(user, "is_superuser", False)\n'
            )
        },
    )
    assert _violations(checker.rule_19_authorization, operator) == []
    suffix_sibling = _with_files(
        module,
        **{
            "_profile_views.py": (
                "from rest_framework.permissions import IsAdminUser\n"
                "from rest_framework.views import APIView\n\n"
                "class IndexView(APIView):\n    permission_classes = [IsAdminUser]\n"
            )
        },
    )
    assert any(
        "IsAdminUser" in violation
        for violation in _violations(checker.rule_19_authorization, suffix_sibling)
    )
    unscanned_class = _with_files(
        module,
        **{
            "_helpers.py": (
                "from rest_framework.permissions import IsAdminUser\n"
                "from rest_framework.views import APIView\n\n"
                "class ProfileAdminView(APIView):\n"
                "    permission_classes = [IsAdminUser]\n"
            )
        },
    )
    assert any(
        "IsAdminUser" in violation
        for violation in _violations(checker.rule_19_authorization, unscanned_class)
    )
    namespace_view = _with_files(
        module,
        **{
            "_handlers.py": (
                "import rest_framework.views as drf_views\n"
                "from rest_framework.permissions import IsAdminUser\n\n"
                "class ProfileAdminView(drf_views.APIView):\n"
                "    permission_classes = [IsAdminUser]\n"
            )
        },
    )
    assert any(
        "IsAdminUser" in violation
        for violation in _violations(checker.rule_19_authorization, namespace_view)
    )
    qualified_view = _with_files(
        module,
        **{
            "_handlers.py": (
                "import rest_framework.views\n"
                "from rest_framework.permissions import IsAdminUser\n\n"
                "class ProfileAdminView(rest_framework.views.APIView):\n"
                "    permission_classes = [IsAdminUser]\n"
            )
        },
    )
    assert any(
        "IsAdminUser" in violation
        for violation in _violations(checker.rule_19_authorization, qualified_view)
    )
    from_namespace_view = _with_files(
        module,
        **{
            "_handlers.py": (
                "from rest_framework import generics\n"
                "from rest_framework.permissions import IsAdminUser\n\n"
                "class ProfileAdminView(generics.ListAPIView):\n"
                "    permission_classes = [IsAdminUser]\n"
            )
        },
    )
    assert any(
        "IsAdminUser" in violation
        for violation in _violations(checker.rule_19_authorization, from_namespace_view)
    )
    django_namespace_view = _with_files(
        module,
        **{
            "_handlers.py": (
                "from django.views import generic\n\n"
                "class StaffOnlyPageView(generic.View):\n"
                '    allowed_flag = "is_staff"\n'
            )
        },
    )
    assert any(
        "is_staff" in violation
        for violation in _violations(checker.rule_19_authorization, django_namespace_view)
    )
    auth_namespace_view = _with_files(
        module,
        **{
            "_handlers.py": (
                "from django.contrib.auth import views\n\n"
                "class StaffOnlyLoginView(views.LoginView):\n"
                '    allowed_flag = "is_staff"\n'
            )
        },
    )
    assert any(
        "is_staff" in violation
        for violation in _violations(checker.rule_19_authorization, auth_namespace_view)
    )
    auth_view = _with_files(
        module,
        **{
            "_handlers.py": (
                "from django.contrib.auth.views import LoginView\n\n"
                "class StaffOnlyLoginView(LoginView):\n"
                '    allowed_flag = "is_staff"\n'
            )
        },
    )
    assert any(
        "is_staff" in violation
        for violation in _violations(checker.rule_19_authorization, auth_view)
    )
    unscanned_function = _with_files(
        module,
        **{
            "_handlers.py": (
                "from django.contrib.auth.views import redirect_to_login\n\n"
                "def index(request):\n"
                "    return redirect_to_login(request.get_full_path())\n"
            )
        },
    )
    assert any(
        "redirect_to_login" in violation
        for violation in _violations(checker.rule_19_authorization, unscanned_function)
    )
    non_view = _with_files(
        module,
        **{"_helpers.py": "def helper(user):\n    return user.is_staff\n"},
    )
    assert _violations(checker.rule_19_authorization, non_view) == []
    operator_helper = _with_files(
        _golden_module("orgs"),
        **{
            "permissions.py": (
                "def resolve_request_org(request, route_kwargs):\n"
                '    if getattr(request.user, "is_superuser", False):\n'
                "        return None\n"
                "    return route_kwargs\n"
            )
        },
    )
    assert _violations(checker.rule_19_authorization, operator_helper) == []
    traffic_filter = _with_files(
        _golden_module("analytics"),
        services=(
            "def _request_is_staff(request):\n"
            '    return bool(getattr(request.user, "is_staff", False))\n'
        ),
    )
    assert _violations(checker.rule_19_authorization, traffic_filter) == []
    documented = _with_files(
        module,
        views=('def index(request):\n    """redirect_to_login"""\n    return None\n'),
    )
    assert _violations(checker.rule_19_authorization, documented) == []
