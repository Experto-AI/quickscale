"""Control cases for the webhooks module-convention rules."""

from __future__ import annotations

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    _golden_module,
    _violations,
    _webhook_module,
    _with_files,
)


def test_webhook_with_statement_return_control() -> None:
    broken = _webhook_module(
        "import hmac\n"
        "from contextlib import nullcontext\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        with nullcontext():\n"
        "            return body\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_false_else_return_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        if False:\n"
        "            pass\n"
        "        else:\n"
        "            return body\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_true_pass_guard_still_verifies() -> None:
    good = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        if True:\n"
        "            pass\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert _violations(checker.rule_26_webhooks, good) == []


def test_webhook_return_before_guard_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    return body\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_swallowed_guard_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    try:\n"
        "        if not hmac.compare_digest(signature, 'expected'):\n"
        "            raise ValueError('bad signature')\n"
        "    except ValueError:\n"
        "        pass\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_loop_else_return_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        for _ in []:\n"
        "            pass\n"
        "        else:\n"
        "            return body\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_finally_return_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        try:\n"
        "            pass\n"
        "        finally:\n"
        "            return body\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_true_return_before_guard_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if True:\n"
        "        return body\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_unreachable_handler_raise_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    try:\n"
        "        if not hmac.compare_digest(signature, 'expected'):\n"
        "            raise ValueError('bad signature')\n"
        "    except ValueError:\n"
        "        if False:\n"
        "            raise\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_with_before_guard_control() -> None:
    broken = _webhook_module(
        "import hmac\n"
        "from contextlib import nullcontext\n\n\n"
        "def handle(*, body, signature):\n"
        "    with nullcontext():\n"
        "        return body\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_unreachable_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    return body\n"
        "    _verify(body=body, signature=signature)\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_finally_override_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    try:\n"
        "        if not hmac.compare_digest(signature, 'expected'):\n"
        "            raise ValueError('bad signature')\n"
        "    finally:\n"
        "        return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_optional_guard_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if signature == 'expected':\n"
        "        if not hmac.compare_digest(signature, 'expected'):\n"
        "            raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_conditional_return_before_guard_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if signature != 'expected':\n"
        "        return body\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_conditional_return_before_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    if signature != 'expected':\n"
        "        return body\n"
        "    _verify(body=body, signature=signature)\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_short_circuit_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n\n\n"
        "def handle(*, body, signature):\n"
        "    return body or _verify(body=body, signature=signature)\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_ignored_sentinel_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        return False\n"
        "    return True\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_nested_sentinel_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        if True:\n"
        "            return False\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_match_sentinel_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        match signature:\n"
        "            case _:\n"
        "                return False\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_early_sentinel_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if signature != 'expected':\n"
        "        return False\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_assert_only_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    assert hmac.compare_digest(signature, 'expected')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_early_return_view_control() -> None:
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
            "        return request.body\n"
            "        result = handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
            "        return Response({'status': 'accepted', 'duplicate': result.duplicate})\n"
        ),
    )
    assert any(
        "services.py function" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_conditional_bypass_view_control() -> None:
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
            "        if request.headers.get('X-Signature'):\n"
            "            result = handle(\n"
            "                body=request.body,\n"
            "                signature=request.headers.get('X-Signature', ''),\n"
            "            )\n"
            "        return Response({'status': 'accepted'})\n"
        ),
    )
    assert any(
        "services.py function" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_signature_unused_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(body, b'x'):\n"
        "        raise ValueError('bad body')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_conditional_accepting_return_control() -> None:
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
            "        if not request.headers.get('X-Signature'):\n"
            "            return request.body\n"
            "        return handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
    )
    assert any(
        "services.py function" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_constant_signature_propagation_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=body, signature='expected')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_signature_wrong_argument_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=signature, signature='expected')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_unused_signature_parameter_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature, backup_signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=body, signature='expected', backup_signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_entry_alternate_parameter_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature, backup_signature='expected'):\n"
        "    if not hmac.compare_digest(backup_signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_overwritten_signature_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    signature = 'expected'\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_entry_overwrite_before_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    signature = 'expected'\n"
        "    _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_compound_overwrite_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if True:\n"
        "        signature = 'expected'\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_compound_overwrite_before_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n"
        "from contextlib import nullcontext\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    with nullcontext():\n"
        "        signature = 'expected'\n"
        "    _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_nonconstant_overwrite_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature, flag=False):\n"
        "    if flag:\n"
        "        signature = 'expected'\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_short_circuit_return_view_control() -> None:
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
            "        return request.body or handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
    )
    assert any(
        "services.py function" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_with_before_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n"
        "from contextlib import nullcontext\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    with nullcontext():\n"
        "        return body\n"
        "    _verify(body=body, signature=signature)\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_true_return_before_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    if True:\n"
        "        return body\n"
        "    _verify(body=body, signature=signature)\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_finally_helper_override_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    try:\n"
        "        _verify(body=body, signature=signature)\n"
        "    finally:\n"
        "        return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_optional_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    if signature == 'expected':\n"
        "        _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_returned_helper_is_credited() -> None:
    good = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n\n\n"
        "def handle(*, body, signature):\n"
        "    return _verify(body=body, signature=signature)\n"
    )
    assert _violations(checker.rule_26_webhooks, good) == []
