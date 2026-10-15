"""
Behavioral controls for the ``rules_webhooks`` split (SA267).

The rule-26 mechanics live in private siblings (``_webhooks_routes``,
``_webhooks_views``, ``_webhooks_services``, ``_webhooks_signature``,
``_webhooks_flows``) behind the ``rules_webhooks`` facade.  SA267 has closed,
so SA279 retired the pre-split surface pins; these controls keep the split's
structural invariants and the exact ordered findings of representative corpora
captured from the pre-split module, so a later change cannot silently drop,
reorder, or reword them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts.check_module_conventions import Corpus, Module
from scripts.module_conventions import (
    _webhooks_flows,
    _webhooks_routes,
    _webhooks_services,
    _webhooks_signature,
    _webhooks_views,
    rules_webhooks,
)
from scripts.module_conventions.rules_identity import RULE_37_ALLOWED_LITERAL_FILES
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _with_files,
)

SPLIT_SIBLINGS = {
    "_webhooks_flows": _webhooks_flows,
    "_webhooks_routes": _webhooks_routes,
    "_webhooks_services": _webhooks_services,
    "_webhooks_signature": _webhooks_signature,
    "_webhooks_views": _webhooks_views,
}


def _urls(*patterns: str) -> str:
    """Return the golden urls.py with its urlpatterns replaced by *patterns*."""
    module = _golden_module()
    rendered = ",\n    ".join(patterns)
    return module.files["urls.py"].replace(
        "urlpatterns = [path('', views.IndexView.as_view(), name='index')]",
        f"urlpatterns = [\n    {rendered}\n]",
    )


def _module(*patterns: str, views: str, services: str) -> Module:
    """Build one golden module whose urls.py mounts *patterns*."""
    return _with_files(
        _golden_module(),
        urls=_urls(*patterns),
        views=views,
        **{"services.py": services},
    )


VALID_MOUNT = "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')"

VALID_VIEW = (
    "from rest_framework.views import APIView\n"
    "from quickscale_modules_demo.services import handle\n\n\n"
    "class IndexView(APIView):\n"
    "    authentication_classes = []\n"
    "    permission_classes = []\n"
    "    throttle_classes = []\n\n"
    "    def post(self, request):\n"
    "        return handle(\n"
    "            body=request.body,\n"
    "            signature=request.headers.get('X-Signature', ''),\n"
    "        )\n"
)

PARTIAL_VIEW = (
    "from rest_framework.views import APIView\n"
    "from quickscale_modules_demo.services import handle\n\n\n"
    "class IndexView(APIView):\n"
    "    authentication_classes = []\n"
    "    permission_classes = []\n\n"
    "    def post(self, request):\n"
    "        return handle(data=request.data, signature=request.headers.get('X-Sig', ''))\n"
)

NO_POST_VIEW = (
    "from quickscale_modules_demo.services import handle\n\n\n"
    "class IndexView:\n"
    "    authentication_classes = []\n"
)

MODULE_CALL_VIEW = (
    "from rest_framework.views import APIView\n"
    "from quickscale_modules_demo import services\n\n\n"
    "class IndexView(APIView):\n"
    "    authentication_classes = []\n"
    "    permission_classes = []\n"
    "    throttle_classes = []\n\n"
    "    def post(self, request):\n"
    "        return services.handle(\n"
    "            body=request.body,\n"
    "            signature=request.headers['X-Signature'],\n"
    "        )\n"
)

ALIAS_VIEW = (
    "from rest_framework.views import APIView\n"
    "from quickscale_modules_demo.services import handle as verify\n\n\n"
    "class IndexView(APIView):\n"
    "    authentication_classes = []\n"
    "    permission_classes = []\n"
    "    throttle_classes = []\n\n"
    "    def post(self, request):\n"
    "        return verify(\n"
    "            body=request.body,\n"
    "            signature=request.headers.getlist('X-Signature')[0],\n"
    "        )\n"
)

BRANCHY_VIEW = (
    "from rest_framework.views import APIView\n"
    "from quickscale_modules_demo.services import first, second\n\n\n"
    "class IndexView(APIView):\n"
    "    authentication_classes = []\n"
    "    permission_classes = []\n"
    "    throttle_classes = []\n\n"
    "    def post(self, request):\n"
    "        if request.method == 'POST':\n"
    "            return first(body=request.body, signature=request.headers.get('X-Sig'))\n"
    "        return second(body=request.body, signature=request.headers.get('X-Sig'))\n"
)

NO_VERIFICATION = "def handle(*, body, signature=None):\n    return body\n"

COMPARE_RAISE = (
    "import hmac\n\n\n"
    "def handle(*, body, signature):\n"
    "    if not hmac.compare_digest(signature, _expected(body)):\n"
    "        raise ValueError('bad signature')\n"
    "    return body\n"
)

LAUNDERED_CONSTANT = (
    "import hmac\n\n\n"
    "def handle(*, body, signature):\n"
    "    if not hmac.compare_digest(signature if False else 'fixed', _expected(body)):\n"
    "        raise ValueError('bad signature')\n"
    "    return body\n"
)

STATIC_TRUE_GUARD = (
    "import hmac\n\n\n"
    "def handle(*, body, signature):\n"
    "    if not hmac.compare_digest(signature, _expected(body)):\n"
    "        if True:\n"
    "            pass\n"
    "        raise ValueError('bad signature')\n"
    "    return body\n"
)

STATIC_FALSE_RETURN = (
    "import hmac\n\n\n"
    "def handle(*, body, signature):\n"
    "    if not hmac.compare_digest(signature, _expected(body)):\n"
    "        if False:\n"
    "            pass\n"
    "        else:\n"
    "            return body\n"
    "        raise ValueError('bad signature')\n"
    "    return body\n"
)

WITH_RETURN = (
    "import hmac\n"
    "from contextlib import nullcontext\n\n\n"
    "def handle(*, body, signature):\n"
    "    if not hmac.compare_digest(signature, _expected(body)):\n"
    "        with nullcontext():\n"
    "            return body\n"
    "        raise ValueError('bad signature')\n"
    "    return body\n"
)

DEAD_RETURN = (
    "import hmac\n\n\n"
    "def handle(*, body, signature):\n"
    "    if False:\n"
    "        return body\n"
    "    if not hmac.compare_digest(signature, _expected(body)):\n"
    "        raise ValueError('bad signature')\n"
    "    return body\n"
)

ENCODED_SIGNATURE = (
    "import hmac\n\n\n"
    "def handle(*, body, signature):\n"
    "    if not hmac.compare_digest((signature or '').encode('utf-8'), _expected(body)):\n"
    "        raise ValueError('bad signature')\n"
    "    return body\n"
)

BYTES_SIGNATURE = (
    "import hmac\n\n\n"
    "def handle(*, body, signature):\n"
    "    if not hmac.compare_digest(bytes(signature, 'utf-8'), _expected(body)):\n"
    "        raise ValueError('bad signature')\n"
    "    return body\n"
)

JOINED_SIGNATURE = (
    "import hmac\n\n\n"
    "def handle(*, body, signature):\n"
    "    if not hmac.compare_digest(signature.join(['a', 'b']), _expected(body)):\n"
    "        raise ValueError('bad signature')\n"
    "    return body\n"
)

OVERWRITTEN_SIGNATURE = (
    "import hmac\n\n\n"
    "def handle(*, body, signature):\n"
    "    signature = 'fixed'\n"
    "    if not hmac.compare_digest(signature, _expected(body)):\n"
    "        raise ValueError('bad signature')\n"
    "    return body\n"
)

SVIX_LOOP = (
    "import hmac\n\n\n"
    "def handle(*, body, signature):\n"
    "    for candidate in signature.split(' '):\n"
    "        if hmac.compare_digest(candidate, _expected(body)):\n"
    "            return body\n"
    "    raise ValueError('bad signature')\n"
)

SVIX_LOOP_NO_RAISE = (
    "import hmac\n\n\n"
    "def handle(*, body, signature):\n"
    "    for candidate in signature.split(' '):\n"
    "        if hmac.compare_digest(candidate, _expected(body)):\n"
    "            return body\n"
    "    return body\n"
)

SVIX_LOOP_ORELSE = (
    "import hmac\n\n\n"
    "def handle(*, body, signature):\n"
    "    for candidate in signature.split(' '):\n"
    "        if hmac.compare_digest(candidate, _expected(body)):\n"
    "            return body\n"
    "    else:\n"
    "        return None\n"
    "    raise ValueError('bad signature')\n"
)

CONSTRUCT_EVENT = (
    "import stripe\n\n\n"
    "def handle(*, body, signature):\n"
    "    return stripe.Webhook.construct_event(body, signature, 'secret')\n"
)

CONSTRUCT_EVENT_WRONG_SLOT = (
    "import stripe\n\n\n"
    "def handle(*, body, signature):\n"
    "    return stripe.Webhook.construct_event(signature, body, 'secret')\n"
)

LOCAL_CHAIN = (
    "import hmac\n\n\n"
    "def handle(*, body, signature):\n"
    "    return _verify(body=body, signature=signature)\n\n\n"
    "def _verify(*, body, signature):\n"
    "    if not hmac.compare_digest(signature, body):\n"
    "        raise ValueError('bad signature')\n"
    "    return body\n"
)

LOCAL_CHAIN_DROPPED = (
    "import hmac\n\n\n"
    "def handle(*, body, signature):\n"
    "    return _verify(body=body, signature='fixed')\n\n\n"
    "def _verify(*, body, signature):\n"
    "    if not hmac.compare_digest(signature, body):\n"
    "        raise ValueError('bad signature')\n"
    "    return body\n"
)


def _clean_corpus() -> Corpus:
    return _corpus(_golden_module())


def _routes_corpus() -> Corpus:
    return _corpus(
        _module(
            "path('webhooks/vendor/', name='vendor_webhook')",
            "path('webhooks/bare/', views.IndexView, name='bare_webhook')",
            "path('webhooks/bad/', views.IndexView['x'].as_view(), name='bad_webhook')",
            VALID_MOUNT,
            "path('inbound/retry/', views.IndexView.as_view(), name='retry_webhook')",
            views=PARTIAL_VIEW,
            services=COMPARE_RAISE,
        )
    )


def _view_guards_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=NO_POST_VIEW, services=COMPARE_RAISE))


def _no_verification_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=NO_VERIFICATION))


def _laundered_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=LAUNDERED_CONSTANT))


def _static_true_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=STATIC_TRUE_GUARD))


def _static_false_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=STATIC_FALSE_RETURN))


def _with_return_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=WITH_RETURN))


def _dead_return_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=DEAD_RETURN))


def _encoded_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=ENCODED_SIGNATURE))


def _bytes_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=BYTES_SIGNATURE))


def _joined_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=JOINED_SIGNATURE))


def _overwritten_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=OVERWRITTEN_SIGNATURE))


def _svix_loop_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=SVIX_LOOP))


def _svix_loop_no_raise_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=SVIX_LOOP_NO_RAISE))


def _svix_loop_orelse_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=SVIX_LOOP_ORELSE))


def _construct_event_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=CONSTRUCT_EVENT))


def _construct_event_wrong_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=CONSTRUCT_EVENT_WRONG_SLOT))


def _local_chain_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=LOCAL_CHAIN))


def _local_chain_dropped_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=VALID_VIEW, services=LOCAL_CHAIN_DROPPED))


def _module_call_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=MODULE_CALL_VIEW, services=COMPARE_RAISE))


def _alias_call_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=ALIAS_VIEW, services=COMPARE_RAISE))


def _branchy_corpus() -> Corpus:
    return _corpus(_module(VALID_MOUNT, views=BRANCHY_VIEW, services=COMPARE_RAISE))


CASE_BUILDERS = {
    "clean": _clean_corpus,
    "routes": _routes_corpus,
    "view_guards": _view_guards_corpus,
    "no_verification": _no_verification_corpus,
    "laundered": _laundered_corpus,
    "static_true": _static_true_corpus,
    "static_false": _static_false_corpus,
    "with_return": _with_return_corpus,
    "dead_return": _dead_return_corpus,
    "encoded": _encoded_corpus,
    "bytes": _bytes_corpus,
    "joined": _joined_corpus,
    "overwritten": _overwritten_corpus,
    "svix_loop": _svix_loop_corpus,
    "svix_loop_no_raise": _svix_loop_no_raise_corpus,
    "svix_loop_orelse": _svix_loop_orelse_corpus,
    "construct_event": _construct_event_corpus,
    "construct_event_wrong": _construct_event_wrong_corpus,
    "local_chain": _local_chain_corpus,
    "local_chain_dropped": _local_chain_dropped_corpus,
    "module_call": _module_call_corpus,
    "alias_call": _alias_call_corpus,
    "branchy": _branchy_corpus,
}

#: (case, detector, expected findings) captured from the pre-split module; the
#: list is exact, so order, wording, and duplicate findings are all pinned.
EXACT_FINDINGS = (
    ("clean", "rule_26_webhooks", ()),
    (
        "routes",
        "rule_26_webhooks",
        (
            "rule 26: demo: webhook route 'webhooks/vendor/' has no view",
            "rule 26: demo: webhook route 'webhooks/bare/' does not mount an "
            "APIView.as_view() callable",
            "rule 26: demo: webhook route 'webhooks/bad/' does not resolve to an APIView class",
            "rule 26: demo: IndexView does not declare empty throttle_classes",
            "rule 26: demo: IndexView does not pass request.body to a service",
            "rule 26: demo: IndexView does not declare empty throttle_classes",
            "rule 26: demo: IndexView does not pass request.body to a service",
        ),
    ),
    (
        "view_guards",
        "rule_26_webhooks",
        (
            "rule 26: demo: IndexView is not a DRF APIView",
            "rule 26: demo: IndexView does not declare empty permission_classes",
            "rule 26: demo: IndexView does not declare empty throttle_classes",
            "rule 26: demo: IndexView defines no post()",
        ),
    ),
    (
        "no_verification",
        "rule_26_webhooks",
        ("rule 26: demo: IndexView calls handle, which does not verify a signature",),
    ),
    (
        "laundered",
        "rule_26_webhooks",
        ("rule 26: demo: IndexView calls handle, which does not verify a signature",),
    ),
    ("static_true", "rule_26_webhooks", ()),
    (
        "static_false",
        "rule_26_webhooks",
        ("rule 26: demo: IndexView calls handle, which does not verify a signature",),
    ),
    (
        "with_return",
        "rule_26_webhooks",
        ("rule 26: demo: IndexView calls handle, which does not verify a signature",),
    ),
    ("dead_return", "rule_26_webhooks", ()),
    ("encoded", "rule_26_webhooks", ()),
    ("bytes", "rule_26_webhooks", ()),
    (
        "joined",
        "rule_26_webhooks",
        ("rule 26: demo: IndexView calls handle, which does not verify a signature",),
    ),
    (
        "overwritten",
        "rule_26_webhooks",
        ("rule 26: demo: IndexView calls handle, which does not verify a signature",),
    ),
    ("svix_loop", "rule_26_webhooks", ()),
    (
        "svix_loop_no_raise",
        "rule_26_webhooks",
        ("rule 26: demo: IndexView calls handle, which does not verify a signature",),
    ),
    (
        "svix_loop_orelse",
        "rule_26_webhooks",
        ("rule 26: demo: IndexView calls handle, which does not verify a signature",),
    ),
    ("construct_event", "rule_26_webhooks", ()),
    (
        "construct_event_wrong",
        "rule_26_webhooks",
        ("rule 26: demo: IndexView calls handle, which does not verify a signature",),
    ),
    ("local_chain", "rule_26_webhooks", ()),
    (
        "local_chain_dropped",
        "rule_26_webhooks",
        ("rule 26: demo: IndexView calls handle, which does not verify a signature",),
    ),
    ("module_call", "rule_26_webhooks", ()),
    ("alias_call", "rule_26_webhooks", ()),
    (
        "branchy",
        "rule_26_webhooks",
        ("rule 26: demo: IndexView does not call a services.py function",),
    ),
)


def test_rule_37_exempts_only_the_facade() -> None:
    """The split siblings stay inside rule 37's closed world."""
    assert ("scripts", "module_conventions/rules_webhooks.py") in RULE_37_ALLOWED_LITERAL_FILES
    for name in SPLIT_SIBLINGS:
        assert (
            "scripts",
            f"module_conventions/{name}.py",
        ) not in RULE_37_ALLOWED_LITERAL_FILES


def test_split_siblings_never_import_the_facade_or_registry() -> None:
    """Helpers reach their collaborators through siblings, never the facade."""
    for name, module in SPLIT_SIBLINGS.items():
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[-1] not in {"rules_webhooks", "registry"}, (
                    name,
                    node.lineno,
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] not in {"rules_webhooks", "registry"}, (
                        name,
                        node.lineno,
                    )


@pytest.mark.parametrize(
    ("case", "detector", "expected"),
    EXACT_FINDINGS,
    ids=[f"{case}-{detector}" for case, detector, _ in EXACT_FINDINGS],
)
def test_detector_findings_are_exact_and_ordered(
    case: str, detector: str, expected: tuple[str, ...]
) -> None:
    corpus = CASE_BUILDERS[case]()
    assert getattr(rules_webhooks, detector)(corpus) == list(expected)
