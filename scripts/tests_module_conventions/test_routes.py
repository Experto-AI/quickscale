"""Control cases for the routes module-convention rules."""

from __future__ import annotations

import copy
from dataclasses import replace

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _seam_corpus,
    _violations,
    _webhook_module,
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


def test_url_prefix_collision_control() -> None:
    """Rule 41: two modules mounting one prefix with different targets fail."""
    alpha = _with_mount(_golden_module("alpha"), "shared/")
    beta = _with_mount(_golden_module("beta"), "shared/")

    violations = checker.rule_7_urls(_corpus(alpha, beta))
    assert any(
        "both mount URL prefix 'shared/' with different targets" in violation
        for violation in violations
    )

    # The identical (prefix, target) pair from two modules is the
    # equal-contribution merge rule 30 sanctions and must stay allowed.
    def _add_shared_include(module, own_mount):
        manifest = copy.deepcopy(module.manifest)
        for projection in manifest["derivation"]["wiring_projections"]:
            if projection.get("wiring_field") == "url_includes":
                projection["expression"]["value"] = [
                    [own_mount, f"quickscale_modules_{module.name}.urls"],
                    ["shared/", "quickscale_shared.urls"],
                ]
        return replace(module, manifest=manifest)

    equal_targets = _corpus(
        _add_shared_include(_golden_module("alpha"), "alpha/"),
        _add_shared_include(_golden_module("beta"), "beta/"),
    )
    assert checker.rule_7_urls(equal_targets) == []
    assert (
        checker.rule_7_urls(
            _corpus(
                _with_mount(_golden_module("alpha"), "alpha/"),
                _with_mount(_golden_module("beta"), "beta/"),
            )
        )
        == []
    )

    # One module may chain several targets under one prefix (auth composes
    # ``accounts/`` that way).
    def _chain_same_prefix(module):
        manifest = copy.deepcopy(module.manifest)
        for projection in manifest["derivation"]["wiring_projections"]:
            if projection.get("wiring_field") == "url_includes":
                projection["expression"]["value"] = [
                    ["shared/", f"quickscale_modules_{module.name}.urls"],
                    ["shared/", "quickscale_shared.urls"],
                ]
        return replace(module, manifest=manifest)

    assert checker.rule_7_urls(_corpus(_chain_same_prefix(_golden_module("alpha")))) == []


def test_theme_api_literal_control() -> None:
    """Rule 41: a /<mount>/api literal in the theme TypeScript fails."""
    module = _golden_module()
    theme_file = "generator/templates/themes/showcase_react/src/hooks/useDemo.ts"

    literal = replace(
        _corpus(module),
        core_files={theme_file: "export const base = '/demo/api/'\n"},
    )
    assert any(
        "module 'demo' API path '/demo/api' is written as a literal" in violation
        for violation in checker.rule_7_urls(literal)
    )

    interpolated = replace(
        _corpus(module),
        core_files={theme_file: "const base = `/demo/api/${slug}`\n"},
    )
    assert any(
        "written as a literal" in violation for violation in checker.rule_7_urls(interpolated)
    )

    # A route-pattern spelling of the mount is still the mount written by
    # hand; prose and patterns both fail.
    route_pattern = replace(
        _corpus(module),
        core_files={theme_file: "const help = 'through `/demo/api/:slug/` only'\n"},
    )
    assert any(
        "written as a literal" in violation for violation in checker.rule_7_urls(route_pattern)
    )

    # The theme's own test files build fetch targets by hand.
    test_file = replace(
        _corpus(module),
        core_files={
            "generator/templates/themes/showcase_react/src/test/useDemo.test.ts": (
                "const base = '/demo/api/'\n"
            )
        },
    )
    assert checker.rule_7_urls(test_file) == []

    # A TS file outside the theme is not the theme's client.
    outside_theme = replace(
        _corpus(module),
        core_files={
            "generator/templates/project_name/static/app.ts": "const base = '/demo/api/'\n"
        },
    )
    assert checker.rule_7_urls(outside_theme) == []
    assert checker.rule_7_urls(_corpus(module)) == []


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


def test_throttle_classes_closed_world_controls() -> None:
    """Rule 32: throttle_classes appears only empty, and only on a webhook."""
    module = _golden_module()
    assert _violations(checker.rule_32_throttles, module) == []

    class_registration = _with_files(
        module,
        views=(
            "from rest_framework.views import APIView\n\n\n"
            "class IndexView(APIView):\n"
            "    throttle_classes = [DemoThrottle]\n"
            "    throttle_scope = 'quickscale_demo_api'\n"
        ),
    )
    assert any(
        "a throttle attaches through throttle_scope only" in violation
        for violation in _violations(checker.rule_32_throttles, class_registration)
    )

    empty_non_webhook = _with_files(
        module,
        views=(
            "from rest_framework.views import APIView\n\n\n"
            "class IndexView(APIView):\n"
            "    throttle_classes = []\n"
        ),
    )
    assert any(
        "a throttle attaches through throttle_scope only" in violation
        for violation in _violations(checker.rule_32_throttles, empty_non_webhook)
    )

    module_level = _with_files(
        module,
        views="throttle_classes = []\n",
    )
    assert any(
        "outside a view class" in violation
        for violation in _violations(checker.rule_32_throttles, module_level)
    )

    webhook = _webhook_module("def handle(body, signature):\n    return None\n")
    assert not any(
        "throttle_classes" in violation
        for violation in _violations(checker.rule_32_throttles, webhook)
    )

    webhook_with_class = _with_files(
        webhook,
        views=webhook.files["views.py"].replace(
            "throttle_classes = []", "throttle_classes = [DemoThrottle]"
        ),
    )
    assert any(
        "declares a non-empty throttle_classes" in violation
        for violation in _violations(checker.rule_32_throttles, webhook_with_class)
    )

    as_view_override = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "views.IndexView.as_view()",
            "views.IndexView.as_view(throttle_classes=[])",
        ),
    )
    assert any(
        "as_view() supplies throttle_classes" in violation
        for violation in _violations(checker.rule_32_throttles, as_view_override)
    )

    webhook_as_view = _with_files(
        webhook,
        urls=webhook.files["urls.py"].replace(
            "views.IndexView.as_view()",
            "views.IndexView.as_view(throttle_classes=[])",
        ),
    )
    assert not any(
        "throttle_classes" in violation
        for violation in _violations(checker.rule_32_throttles, webhook_as_view)
    )


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


def test_session_authentication_subclass_control() -> None:
    module = _golden_module()
    assert _violations(checker.rule_9_http_apis, module) == []
    broken = _with_files(
        module,
        views=(
            "from rest_framework.authentication import SessionAuthentication\n\n\n"
            "class DemoSessionAuthentication(SessionAuthentication):\n"
            "    def authenticate_header(self, request):\n"
            "        return 'Session'\n"
        ),
    )
    assert any(
        "SessionAuthentication subclass" in violation
        for violation in _violations(checker.rule_9_http_apis, broken)
    )


def test_authentication_classes_closed_world_controls() -> None:
    """Rule 9 admits core's class and the empty literal only."""
    module = _golden_module()
    drf_class = _with_files(
        module,
        views=(
            "from rest_framework.authentication import SessionAuthentication\n"
            "from rest_framework.views import APIView\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = [SessionAuthentication]\n"
        ),
    )
    assert any(
        "names DRF's SessionAuthentication directly" in violation
        for violation in _violations(checker.rule_9_http_apis, drf_class)
    )
    qualified_drf_class = _with_files(
        module,
        views=(
            "import rest_framework.authentication\n"
            "from rest_framework.views import APIView\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = "
            "[rest_framework.authentication.SessionAuthentication]\n"
        ),
    )
    assert any(
        "names DRF's SessionAuthentication directly" in violation
        for violation in _violations(checker.rule_9_http_apis, qualified_drf_class)
    )
    other_class = _with_files(
        module,
        views=(
            "from rest_framework.permissions import AllowAny\n"
            "from rest_framework.views import APIView\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = [AllowAny]\n"
        ),
    )
    assert any(
        "not core's session authentication class" in violation
        for violation in _violations(checker.rule_9_http_apis, other_class)
    )
    core_class = _with_files(
        module,
        views=(
            "from quickscale_core.runtime import QuickscaleSessionAuthentication\n"
            "from rest_framework.views import APIView\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = [QuickscaleSessionAuthentication]\n"
        ),
    )
    assert _violations(checker.rule_9_http_apis, core_class) == []
    aliased_core_namespace = _with_files(
        module,
        views=(
            "import quickscale_core.runtime as runtime\n"
            "from rest_framework.views import APIView\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = [runtime.QuickscaleSessionAuthentication]\n"
        ),
    )
    assert _violations(checker.rule_9_http_apis, aliased_core_namespace) == []
    webhook_like = _with_files(
        module,
        views=(
            "from rest_framework.views import APIView\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
        ),
    )
    assert _violations(checker.rule_9_http_apis, webhook_like) == []


_SEAM = (
    "{% load static quickscale_seam %}\n"
    "{% seam_module_flags %}\n"
    "{% seam_module_paths %}\n"
    "{% seam_module_api_paths %}\n"
)


def test_theme_seam_control() -> None:
    good = _SEAM
    assert checker.rule_31_theme_seam(_seam_corpus(good)) == []
    missing = _seam_corpus("{% load static quickscale_seam %}\n{% seam_module_flags %}\n")
    assert any("does not render" in violation for violation in checker.rule_31_theme_seam(missing))
    missing_api_paths = _seam_corpus(
        "{% load static quickscale_seam %}\n{% seam_module_flags %}\n{% seam_module_paths %}\n"
    )
    assert any(
        "does not render {% seam_module_api_paths %}" in violation
        for violation in checker.rule_31_theme_seam(missing_api_paths)
    )
    unloaded = _seam_corpus("{% seam_module_flags %}\n{% seam_module_paths %}\n")
    assert any(
        "does not load the quickscale_seam tag library" in violation
        for violation in checker.rule_31_theme_seam(unloaded)
    )
    literal_line = _seam_corpus('{% seam_module_flags %}\n"demo": true,\n{% seam_module_paths %}\n')
    assert any(
        "names module 'demo' literally" in violation
        for violation in checker.rule_31_theme_seam(literal_line)
    )
    bare_key = _seam_corpus("{% seam_module_flags %}\ndemo: true,\n{% seam_module_paths %}\n")
    assert any("bare key" in violation for violation in checker.rule_31_theme_seam(bare_key))
    absolute_mount = _seam_corpus("{% seam_module_flags %}\n{% seam_module_paths %}\n'/demo/'")
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
        _SEAM + '<a href="/accounts/">Accounts</a>\n',
        auth,
    )
    assert any(
        "mount 'accounts/'" in violation
        for violation in checker.rule_31_theme_seam(accounts_literal)
    )
    named_url = _seam_corpus(
        _SEAM + "{% url 'quickscale_auth:login' %}\n",
        auth,
    )
    assert checker.rule_31_theme_seam(named_url) == []


def test_theme_seam_social_producer_control() -> None:
    """The public social producers carry the runtime seam, not module lines."""
    social_template = checker.THEME_SEAM_TEMPLATES[1]
    corpus = replace(
        _corpus(_golden_module()),
        core_files={
            checker.THEME_SEAM_TEMPLATE: _SEAM,
            social_template: (
                "{% load static quickscale_seam %}\n"
                "{% seam_module_flags %}\ndemo: true,\n{% seam_module_paths %}\n"
            ),
        },
    )
    violations = checker.rule_31_theme_seam(corpus)
    assert any(social_template in violation and "bare key" in violation for violation in violations)
    clean = replace(
        corpus,
        core_files={
            checker.THEME_SEAM_TEMPLATE: _SEAM,
            social_template: _SEAM,
        },
    )
    assert checker.rule_31_theme_seam(clean) == []
    override = replace(
        corpus,
        core_files={
            checker.THEME_SEAM_TEMPLATE: _SEAM,
            social_template: (
                "{% load static quickscale_seam %}\n"
                '{% seam_module_flags %}\n"demo": "/demo/",\n{% seam_module_paths %}\n'
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
    unguarded_view = _with_files(
        module,
        views=(
            "from django.views.generic import TemplateView\n\n"
            "class MountPageView(TemplateView):\n"
            "    pass\n"
        ),
    )
    assert any(
        "declares no authorization guard" in violation
        for violation in _violations(checker.rule_19_authorization, unguarded_view)
    )
    guarded_views = _with_files(
        module,
        views=(
            "from django.contrib.auth.mixins import LoginRequiredMixin\n"
            "from django.views.generic import TemplateView\n"
            "from quickscale_modules_orgs.permissions import OrgRoleMixin\n"
            "from rest_framework.permissions import IsAuthenticated\n"
            "from rest_framework.views import APIView\n\n\n"
            "class DashboardPageView(LoginRequiredMixin, TemplateView):\n"
            "    pass\n\n\n"
            "class SecureAPIView(APIView):\n"
            "    permission_classes = [IsAuthenticated]\n\n\n"
            "class OrgPageView(OrgRoleMixin, TemplateView):\n"
            "    min_org_role = 'viewer'\n\n\n"
            "class DynamicAPIView(APIView):\n"
            "    def get_permissions(self):\n"
            "        return [IsAuthenticated()]\n"
        ),
    )
    assert _violations(checker.rule_19_authorization, guarded_views) == []
    inert_role_attribute = _with_files(
        module,
        views=(
            "from django.views.generic import TemplateView\n\n"
            "class InertRolePageView(TemplateView):\n"
            "    min_org_role = 'viewer'\n"
        ),
    )
    assert any(
        "declares no authorization guard" in violation
        for violation in _violations(checker.rule_19_authorization, inert_role_attribute)
    )
    inert_page_permission_classes = _with_files(
        module,
        views=(
            "from django.views.generic import TemplateView\n"
            "from rest_framework.permissions import IsAuthenticated\n\n"
            "class DashboardPageView(TemplateView):\n"
            "    permission_classes = [IsAuthenticated]\n"
        ),
    )
    assert any(
        "declares no authorization guard" in violation
        for violation in _violations(checker.rule_19_authorization, inert_page_permission_classes)
    )
    aliased_allow_any = _with_files(
        module,
        views=(
            "from rest_framework.permissions import AllowAny as PublicAccess\n"
            "from rest_framework.views import APIView\n\n"
            "class PublicAPIView(APIView):\n"
            "    permission_classes = [PublicAccess]\n\n"
            "    def get(self, request):\n"
            "        if not request.user.is_authenticated:\n"
            "            raise PermissionError\n"
            "        return None\n"
        ),
    )
    assert any(
        "reads request.user.is_authenticated" in violation
        for violation in _violations(checker.rule_19_authorization, aliased_allow_any)
    )
    wrapper_mixin_guard = _with_files(
        module,
        views=(
            "from django.contrib.auth.mixins import LoginRequiredMixin\n"
            "from django.views.generic import TemplateView\n\n"
            "class SecureMixin(LoginRequiredMixin):\n"
            "    pass\n\n"
            "class DashboardView(SecureMixin, TemplateView):\n"
            "    pass\n"
        ),
    )
    assert _violations(checker.rule_19_authorization, wrapper_mixin_guard) == []
    sibling_alias_isolation = _with_files(
        _with_files(
            module,
            views=(
                "from rest_framework.permissions import AllowAny as AccessPermission\n"
                "from rest_framework.views import APIView\n\n"
                "class PublicAPIView(APIView):\n"
                "    permission_classes = [AccessPermission]\n\n"
                "    def get(self, request):\n"
                "        if not request.user.is_authenticated:\n"
                "            raise PermissionError\n"
                "        return None\n"
            ),
        ),
        **{
            "_private_views.py": (
                "from rest_framework.permissions import IsAuthenticated as AccessPermission\n"
                "from rest_framework.views import APIView\n\n"
                "class PrivateAPIView(APIView):\n"
                "    permission_classes = [AccessPermission]\n"
            )
        },
    )
    assert any(
        "PublicAPIView" in violation
        for violation in _violations(checker.rule_19_authorization, sibling_alias_isolation)
    )
    inherited_handler = _with_files(
        module,
        views=(
            "from rest_framework.permissions import AllowAny, IsAuthenticated\n"
            "from rest_framework.views import APIView\n\n\n"
            "class BaseAPIView(APIView):\n"
            "    permission_classes = [IsAuthenticated]\n\n"
            "    def get(self, request):\n"
            "        if not request.user.is_authenticated:\n"
            "            raise PermissionError\n"
            "        return None\n\n\n"
            "class PublicAPIView(BaseAPIView):\n"
            "    permission_classes = [AllowAny]\n"
        ),
    )
    assert any(
        "PublicAPIView" in violation
        for violation in _violations(checker.rule_19_authorization, inherited_handler)
    )
    sibling_helper = _with_files(
        _with_files(
            module,
            views=(
                "from rest_framework.permissions import AllowAny\n"
                "from rest_framework.views import APIView\n\n"
                "from ._auth import require_authenticated\n\n\n"
                "class PublicAPIView(APIView):\n"
                "    permission_classes = [AllowAny]\n\n"
                "    def get(self, request):\n"
                "        require_authenticated(request)\n"
                "        return None\n"
            ),
        ),
        **{
            "_auth.py": (
                "def require_authenticated(request):\n"
                "    if not request.user.is_authenticated:\n"
                "        raise PermissionError\n"
            )
        },
    )
    assert any(
        "require_authenticated" in violation
        for violation in _violations(checker.rule_19_authorization, sibling_helper)
    )
    inherited_local_helper = _with_files(
        _with_files(
            module,
            views=(
                "from rest_framework.permissions import AllowAny\n"
                "from rest_framework.views import APIView\n\n"
                "from ._base import BaseAPIView\n\n\n"
                "class PublicAPIView(BaseAPIView):\n"
                "    permission_classes = [AllowAny]\n"
            ),
        ),
        **{
            "_base.py": (
                "from rest_framework.permissions import IsAuthenticated\n"
                "from rest_framework.views import APIView\n\n\n"
                "def _require_authenticated(request):\n"
                "    if not request.user.is_authenticated:\n"
                "        raise PermissionError\n\n\n"
                "class BaseAPIView(APIView):\n"
                "    permission_classes = [IsAuthenticated]\n\n"
                "    def get(self, request):\n"
                "        _require_authenticated(request)\n"
                "        return None\n"
            ),
        },
    )
    assert any(
        "_require_authenticated" in violation
        for violation in _violations(checker.rule_19_authorization, inherited_local_helper)
    )
    inherited_imported_helper = _with_files(
        _with_files(
            module,
            views=(
                "from rest_framework.permissions import AllowAny\n"
                "from rest_framework.views import APIView\n\n"
                "from ._base import BaseAPIView\n\n\n"
                "class PublicAPIView(BaseAPIView):\n"
                "    permission_classes = [AllowAny]\n"
            ),
        ),
        **{
            "_base.py": (
                "from rest_framework.permissions import IsAuthenticated\n"
                "from rest_framework.views import APIView\n\n"
                "from ._auth import require_authenticated\n\n\n"
                "class BaseAPIView(APIView):\n"
                "    permission_classes = [IsAuthenticated]\n\n"
                "    def get(self, request):\n"
                "        require_authenticated(request)\n"
                "        return None\n"
            ),
            "_auth.py": (
                "def require_authenticated(request):\n"
                "    if not request.user.is_authenticated:\n"
                "        raise PermissionError\n"
            ),
        },
    )
    assert any(
        "require_authenticated" in violation
        for violation in _violations(checker.rule_19_authorization, inherited_imported_helper)
    )
    dynamic_allow_any = _with_files(
        module,
        views=(
            "from rest_framework.permissions import AllowAny\n"
            "from rest_framework.views import APIView\n\n"
            "class PublicAPIView(APIView):\n"
            "    def get_permissions(self):\n"
            "        return [AllowAny()]\n\n"
            "    def get(self, request):\n"
            "        if not request.user.is_authenticated:\n"
            "            raise PermissionError\n"
            "        return None\n"
        ),
    )
    assert any(
        "reads request.user.is_authenticated" in violation
        for violation in _violations(checker.rule_19_authorization, dynamic_allow_any)
    )
    unclassifiable_override = _with_files(
        module,
        views=(
            "from rest_framework.views import APIView\n\n"
            "class ComputedAPIView(APIView):\n"
            "    def get_permissions(self):\n"
            "        return [permission() for permission in self.permission_classes]\n"
        ),
    )
    assert any(
        "declares no authorization guard" in violation
        for violation in _violations(checker.rule_19_authorization, unclassifiable_override)
    )
    computed_override_with_local_declaration = _with_files(
        module,
        views=(
            "from rest_framework.permissions import AllowAny\n"
            "from rest_framework.views import APIView\n\n"
            "class ComputedAPIView(APIView):\n"
            "    permission_classes = [AllowAny]\n\n"
            "    def get_permissions(self):\n"
            "        return [permission() for permission in self.permission_classes]\n"
        ),
    )
    assert any(
        "declares no authorization guard" in violation
        for violation in _violations(
            checker.rule_19_authorization, computed_override_with_local_declaration
        )
    )
    computed_override_with_inherited_declaration = _with_files(
        module,
        views=(
            "from rest_framework.permissions import AllowAny\n"
            "from rest_framework.views import APIView\n\n\n"
            "class BaseAPIView(APIView):\n"
            "    permission_classes = [AllowAny]\n\n\n"
            "class ChildAPIView(BaseAPIView):\n"
            "    def get_permissions(self):\n"
            "        return [permission() for permission in self.permission_classes]\n"
        ),
    )
    assert any(
        "ChildAPIView" in violation
        for violation in _violations(
            checker.rule_19_authorization, computed_override_with_inherited_declaration
        )
    )
    public_read_mixin = _with_files(
        module,
        views=(
            "from django.views.generic import TemplateView\n\n"
            "class DemoPublicReadMixin:\n"
            "    pass\n\n"
            "class PublicPageView(DemoPublicReadMixin, TemplateView):\n"
            "    pass\n"
        ),
    )
    assert _violations(checker.rule_19_authorization, public_read_mixin) == []
    public_catalog = _with_files(
        module,
        views=(
            "from rest_framework.permissions import AllowAny\n"
            "from rest_framework.views import APIView\n\n"
            "class CatalogAPIView(APIView):\n"
            "    permission_classes = [AllowAny]\n\n"
            "    def get(self, request):\n"
            "        return None\n"
        ),
    )
    assert _violations(checker.rule_19_authorization, public_catalog) == []
    allow_any_direct_read = _with_files(
        module,
        views=(
            "from rest_framework.permissions import AllowAny\n"
            "from rest_framework.views import APIView\n\n"
            "class PublicAPIView(APIView):\n"
            "    permission_classes = [AllowAny]\n\n"
            "    def get(self, request):\n"
            "        if not request.user.is_authenticated:\n"
            "            raise PermissionError\n"
            "        return None\n"
        ),
    )
    assert any(
        "reads request.user.is_authenticated" in violation
        for violation in _violations(checker.rule_19_authorization, allow_any_direct_read)
    )
    allow_any_helper_call = _with_files(
        module,
        views=(
            "from rest_framework.permissions import AllowAny\n"
            "from rest_framework.views import APIView\n\n\n"
            "def _require_authenticated(request):\n"
            "    if not request.user.is_authenticated:\n"
            "        raise PermissionError\n\n\n"
            "class CheckoutAPIView(APIView):\n"
            "    permission_classes = [AllowAny]\n\n"
            "    def post(self, request):\n"
            "        _require_authenticated(request)\n"
            "        return None\n"
        ),
    )
    assert any(
        "_require_authenticated" in violation
        for violation in _violations(checker.rule_19_authorization, allow_any_helper_call)
    )
    inherited_allow_any = _with_files(
        module,
        views=(
            "from rest_framework.permissions import AllowAny\n"
            "from rest_framework.views import APIView\n\n\n"
            "def _require_authenticated(request):\n"
            "    if not request.user.is_authenticated:\n"
            "        raise PermissionError\n\n\n"
            "class BillingAPIView(APIView):\n"
            "    permission_classes = [AllowAny]\n\n\n"
            "class CheckoutAPIView(BillingAPIView):\n"
            "    def post(self, request):\n"
            "        _require_authenticated(request)\n"
            "        return None\n"
        ),
    )
    assert any(
        "CheckoutAPIView" in violation
        for violation in _violations(checker.rule_19_authorization, inherited_allow_any)
    )
    guarded_read = _with_files(
        module,
        views=(
            "from rest_framework.permissions import IsAuthenticated\n"
            "from rest_framework.views import APIView\n\n"
            "class SecureAPIView(APIView):\n"
            "    permission_classes = [IsAuthenticated]\n\n"
            "    def get(self, request):\n"
            "        return request.user.is_authenticated\n"
        ),
    )
    assert _violations(checker.rule_19_authorization, guarded_read) == []


def test_template_folder_depth_control() -> None:
    module = _golden_module()
    for folder in ("demo", "reports"):
        nested = _with_files(
            module,
            **{
                f"templates/quickscale_demo/{folder}/page.html": (
                    '{% extends "quickscale_demo/base.html" %}\n'
                    "{% block demo_content %}{% endblock %}\n"
                )
            },
        )
        assert any(
            "is not flat under" in violation
            for violation in _violations(checker.rule_8_templates, nested)
        )


def test_admin_override_path_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{
            "admin.py": (
                "class WidgetAdmin:\n"
                "    change_list_template = 'quickscale_demo/admin/widget/change_list.html'\n"
            )
        },
    )
    assert any(
        "admin override" in violation for violation in _violations(checker.rule_8_templates, broken)
    )
    bare = _with_files(
        module,
        **{
            "admin.py": (
                "class WidgetAdmin:\n    change_list_template = 'admin/change_list.html'\n"
            )
        },
    )
    assert any(
        "admin override" in violation for violation in _violations(checker.rule_8_templates, bare)
    )


def test_pagination_closed_world_controls() -> None:
    """Rule 9 admits subclasses of core's one list paginator only."""
    module = _golden_module()
    assert _violations(checker.rule_9_http_apis, module) == []

    drf_subclass = _with_files(
        module,
        views=(
            "from rest_framework.pagination import PageNumberPagination\n\n\n"
            "class DemoPagination(PageNumberPagination):\n"
            "    page_size_query_param = None\n"
        ),
    )
    assert any(
        "outside core" in violation
        for violation in _violations(checker.rule_9_http_apis, drf_subclass)
    )

    core_subclass = _with_files(
        module,
        views=(
            "from quickscale_core.runtime import PlainListPagination\n\n\n"
            "class DemoPagination(PlainListPagination):\n"
            "    page_size_setting = 'QUICKSCALE_DEMO_PER_PAGE'\n"
        ),
    )
    assert _violations(checker.rule_9_http_apis, core_subclass) == []

    missing_setting = _with_files(
        module,
        views=(
            "from quickscale_core.runtime import PlainListPagination\n\n\n"
            "class DemoPagination(PlainListPagination):\n"
            "    page_size_query_param = None\n"
        ),
    )
    assert any(
        "must declare page_size_setting" in violation
        for violation in _violations(checker.rule_9_http_apis, missing_setting)
    )

    literal_page_size = _with_files(
        module,
        views=(
            "from quickscale_core.runtime import PlainListPagination\n\n\n"
            "class DemoPagination(PlainListPagination):\n"
            "    page_size = 25\n"
            "    page_size_setting = 'QUICKSCALE_DEMO_PER_PAGE'\n"
        ),
    )
    assert any(
        "literal page_size" in violation
        for violation in _violations(checker.rule_9_http_apis, literal_page_size)
    )

    names_a_drf_class = _with_files(
        module,
        views=(
            "from rest_framework.pagination import PageNumberPagination\n"
            "from rest_framework.views import APIView\n\n\n"
            "class IndexView(APIView):\n"
            "    pagination_class = PageNumberPagination\n"
        ),
    )
    assert any(
        "pagination_class must name a subclass" in violation
        for violation in _violations(checker.rule_9_http_apis, names_a_drf_class)
    )

    names_a_local_core_subclass = _with_files(
        module,
        views=(
            "from quickscale_core.runtime import PlainListPagination\n"
            "from rest_framework.views import APIView\n\n\n"
            "class DemoPagination(PlainListPagination):\n"
            "    page_size_setting = 'QUICKSCALE_DEMO_PER_PAGE'\n\n\n"
            "class IndexView(APIView):\n"
            "    pagination_class = DemoPagination\n"
        ),
    )
    assert _violations(checker.rule_9_http_apis, names_a_local_core_subclass) == []


def test_rendered_managed_json_control(monkeypatch) -> None:
    """Rule 9 covers core-rendered managed views (render once, then parse)."""
    module = _golden_module()
    assert _violations(checker.rule_9_http_apis, module) == []

    from quickscale_core.manifest import social_manifest

    def _legacy_render(**_kwargs: object) -> str:
        return (
            "from django.http import JsonResponse\n\n\n"
            "def social_link_tree_payload(request):\n"
            "    return JsonResponse({'error': {'code': 'x'}})\n"
        )

    monkeypatch.setattr(social_manifest, "render_social_managed_views_module", _legacy_render)
    violations = _violations(checker.rule_9_http_apis, module)
    assert any("JsonResponse" in violation for violation in violations)
    assert any("error body" in violation for violation in violations)


def test_pagination_sibling_import_controls() -> None:
    """A paginator imported from a private sibling file resolves (rule 28)."""
    module = _golden_module()
    sibling_core = _with_files(
        module,
        **{
            "_pagination.py": (
                "from quickscale_core.runtime import PlainListPagination\n\n\n"
                "class DemoPagination(PlainListPagination):\n"
                "    page_size_setting = 'QUICKSCALE_DEMO_PER_PAGE'\n"
            ),
            "views.py": (
                "from rest_framework.views import APIView\n\n"
                "from ._pagination import DemoPagination\n\n\n"
                "class IndexView(APIView):\n"
                "    pagination_class = DemoPagination\n"
            ),
        },
    )
    assert _violations(checker.rule_9_http_apis, sibling_core) == []

    sibling_drf = _with_files(
        module,
        **{
            "_pagination.py": (
                "from rest_framework.pagination import PageNumberPagination\n\n\n"
                "class DemoPagination(PageNumberPagination):\n"
                "    page_size_query_param = None\n"
            ),
            "views.py": (
                "from rest_framework.views import APIView\n\n"
                "from ._pagination import DemoPagination\n\n\n"
                "class IndexView(APIView):\n"
                "    pagination_class = DemoPagination\n"
            ),
        },
    )
    violations = _violations(checker.rule_9_http_apis, sibling_drf)
    assert any("pagination_class must name a subclass" in violation for violation in violations)
    assert any("outside core" in violation for violation in violations)
