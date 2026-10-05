"""Control cases for the webhooks verification module-convention rules."""

from __future__ import annotations

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    _golden_module,
    _violations,
    _webhook_module,
    _with_files,
)


def test_webhook_view_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "class IndexView:\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(body=request.body)\n"
        ),
    )
    assert any(
        "throttle_classes" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_requires_drf_base() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView:\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(body=request.body)\n"
        ),
    )
    assert any(
        "not a DRF APIView" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_requires_service_call() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(body=request.body)\n"
        ),
    )
    assert any(
        "services.py function" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_aliased_service_import_control() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle as verify\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return verify(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected'):\n"
                "        raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert _violations(checker.rule_26_webhooks, good) == []


def test_webhook_constant_signature_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(body=request.body, signature='x')\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected'):\n"
                "        raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "request headers" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_ignored_verification_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
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
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    hmac.compare_digest(signature, 'expected')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_sdk_constant_signature_control() -> None:
    broken = _webhook_module(
        "import stripe\n\n\n"
        "def handle(*, body, signature):\n"
        "    return stripe.Webhook.construct_event(body, 'fixed', 'secret')\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_sdk_incoming_signature_control() -> None:
    positional = _webhook_module(
        "import stripe\n\n\n"
        "def handle(*, body, signature):\n"
        "    return stripe.Webhook.construct_event(body, signature, 'secret')\n"
    )
    assert _violations(checker.rule_26_webhooks, positional) == []
    keyword = _webhook_module(
        "import stripe\n\n\n"
        "def handle(*, body, signature):\n"
        "    return stripe.Webhook.construct_event(\n"
        "        payload=body, sig_header=signature, secret='secret'\n"
        "    )\n"
    )
    assert _violations(checker.rule_26_webhooks, keyword) == []
    wrapper = _webhook_module(
        "def handle(*, body, signature):\n"
        "    return client.construct_event(\n"
        "        body=body, signature=signature, webhook_secret='secret'\n"
        "    )\n"
    )
    assert _violations(checker.rule_26_webhooks, wrapper) == []


def test_webhook_sdk_wrong_signature_slot_control() -> None:
    broken = _webhook_module(
        "import stripe\n\n\n"
        "def handle(*, body, signature):\n"
        "    return stripe.Webhook.construct_event(signature, 'fixed', 'secret')\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_sdk_conditional_signature_control() -> None:
    dead_branch = _webhook_module(
        "import stripe\n\n\n"
        "def handle(*, body, signature):\n"
        "    return stripe.Webhook.construct_event(\n"
        "        body, signature if False else 'fixed', 'secret'\n"
        "    )\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, dead_branch)
    )
    unknown = _webhook_module(
        "import stripe\n\n\n"
        "def handle(*, body, signature, flag):\n"
        "    return stripe.Webhook.construct_event(\n"
        "        body, signature if flag else 'fixed', 'secret'\n"
        "    )\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, unknown)
    )
    selected = _webhook_module(
        "import stripe\n\n\n"
        "def handle(*, body, signature):\n"
        "    return stripe.Webhook.construct_event(\n"
        "        body, signature if True else 'fixed', 'secret'\n"
        "    )\n"
    )
    assert _violations(checker.rule_26_webhooks, selected) == []


def test_webhook_derived_signature_control() -> None:
    good = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    expected = 'expected'.encode('utf-8')\n"
        "    if not hmac.compare_digest((signature or '').encode('utf-8'), expected):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert _violations(checker.rule_26_webhooks, good) == []
    masked = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature and 'expected', 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, masked)
    )
    masked_falsy = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature and '', ''):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, masked_falsy)
    )
    constant_prefix = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest('' and signature, ''):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, constant_prefix)
    )


def test_webhook_discarding_call_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest((lambda ignored: 'expected')(signature), 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )
    derived = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature.strip().encode('utf-8'), b'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert _violations(checker.rule_26_webhooks, derived) == []
    constant = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(str('expected'), 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, constant)
    )
    constructed = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(str(signature), 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert _violations(checker.rule_26_webhooks, constructed) == []
    discarding_method = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature.join(['expected']), 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, discarding_method)
    )


def test_webhook_self_comparison_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
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
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, signature):\n"
                "        raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_success_value_return_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
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
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected'):\n"
                "        return body\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_inverted_guard_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
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
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if hmac.compare_digest(signature, 'expected'):\n"
                "        raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_unreachable_rejection_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
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
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected'):\n"
                "        if False:\n"
                "            raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_unsupported_polarity_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
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
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected') == False:\n"
                "        raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_return_before_raise_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
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
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected'):\n"
                "        return body\n"
                "        raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_unreachable_guard_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
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
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if False:\n"
                "        if not hmac.compare_digest(signature, 'expected'):\n"
                "            raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_inverted_assert_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
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
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    assert not hmac.compare_digest(signature, 'expected')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_nested_executed_return_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
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
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected'):\n"
                "        if True:\n"
                "            return body\n"
                "        raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_function_view_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.webhook, name='vendor_webhook')",
        ),
        views="def webhook(request):\n    return request.body\n",
    )
    assert any(
        "APIView.as_view()" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_unsigned_service_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(body=request.body, signature='x')\n"
        ),
        **{"services.py": "def handle(*, body, signature):\n    return body\n"},
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_pass_body_verification_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
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
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected'):\n"
                "        pass\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )
