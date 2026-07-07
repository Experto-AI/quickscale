"""
Focused regression tests for the SA46 CSRF-exempt AST gate.

These tests validate that the tightened AST gate correctly:

* **rejects** false positives (helper calls nested in dead code, helper
  calls in unrelated sibling methods),
* **accepts** all current real-world call-sites (billing, notifications,
  blog),
* **rejects** missing helper calls.

Each test exercises the module's internal helpers or the full
``_CsrfExemptVisitor`` with synthetic AST trees constructed from source
strings — no filesystem fixtures required.
"""

from __future__ import annotations

import ast

from scripts.check_csrf_exempt_gate import (
    _body_contains_helper_call,
    _CsrfExemptVisitor,
    _extract_method_decorator_name,
    _is_csrf_exempt_decorator,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_body(source: str) -> list[ast.stmt]:
    """Parse *source* into a function body (list of statements)."""
    tree = ast.parse(source)
    assert isinstance(tree, ast.Module)
    assert len(tree.body) == 1
    func = tree.body[0]
    assert isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef))
    return func.body


def _iter_decorators(source: str) -> list[ast.expr]:
    """Return the decorator list from a function or class definition."""
    tree = ast.parse(source)
    assert isinstance(tree, ast.Module)
    assert len(tree.body) == 1
    node = tree.body[0]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.decorator_list
    raise TypeError(f"unexpected node type: {type(node).__name__}")


def _get_violation_count(source: str) -> int:
    """Parse *source* as a module and return the violation count."""
    tree = ast.parse(source)
    visitor = _CsrfExemptVisitor()
    visitor.visit(tree)
    return len(visitor.violations)


# ---------------------------------------------------------------------------
# _node_walks_helper_call  —  surface-only traversal
# ---------------------------------------------------------------------------


class TestNodeWalksHelperCall:
    """``_node_walks_helper_call`` skips nested scope boundaries."""

    def test_direct_call_found(self) -> None:
        """A direct helper call at the surface is found."""
        body = _parse_body("def f():\n    _enforce_csrf(request)\n    return\n")
        assert _body_contains_helper_call(body)

    def test_call_in_if_branch_found(self) -> None:
        """A helper call inside an ``if`` (same scope) is found."""
        body = _parse_body("def f():\n    if True:\n        _enforce_csrf(request)\n    return\n")
        assert _body_contains_helper_call(body)

    def test_call_in_try_found(self) -> None:
        """A helper call inside a ``try`` (same scope) is found."""
        body = _parse_body(
            "def f():\n"
            "    try:\n"
            "        _enforce_csrf(request)\n"
            "    except Exception:\n"
            "        pass\n"
            "    return\n"
        )
        assert _body_contains_helper_call(body)

    def test_call_in_with_found(self) -> None:
        """A helper call inside a ``with`` block (same scope) is found."""
        body = _parse_body(
            "def f():\n    with mock():\n        _enforce_csrf(request)\n    return\n"
        )
        assert _body_contains_helper_call(body)

    def test_nested_function_def_skipped(self) -> None:
        """A helper call inside a nested ``def`` is NOT found."""
        body = _parse_body(
            "def f():\n    def inner():\n        _enforce_csrf(request)\n    return\n"
        )
        assert not _body_contains_helper_call(body)

    def test_nested_async_function_def_skipped(self) -> None:
        """A helper call inside a nested ``async def`` is NOT found."""
        body = _parse_body(
            "def f():\n    async def inner():\n        _enforce_csrf(request)\n    return\n"
        )
        assert not _body_contains_helper_call(body)

    def test_nested_class_def_skipped(self) -> None:
        """A helper call inside a nested class is NOT found."""
        body = _parse_body(
            "def f():\n    class Inner:\n        _enforce_csrf(request)\n    return\n"
        )
        assert not _body_contains_helper_call(body)

    def test_lambda_skipped(self) -> None:
        """A helper call inside a ``lambda`` is NOT found."""
        body = _parse_body("def f():\n    cb = lambda req: _enforce_csrf(req)\n    return\n")
        assert not _body_contains_helper_call(body)

    def test_deeply_nested_function_def_skipped(self) -> None:
        """A helper two levels deep is NOT found."""
        body = _parse_body(
            "def f():\n"
            "    def outer():\n"
            "        def inner():\n"
            "            _enforce_csrf(request)\n"
            "        return\n"
            "    return\n"
        )
        assert not _body_contains_helper_call(body)

    def test_multiple_nested_function_defs_skipped(self) -> None:
        """Helpers in multiple nested functions are all skipped."""
        body = _parse_body(
            "def f():\n"
            "    def a():\n"
            "        _enforce_csrf(request)\n"
            "    def b():\n"
            "        authenticate_blog_api_request(request)\n"
            "    return\n"
        )
        assert not _body_contains_helper_call(body)

    def test_mixed_surface_and_nested(self) -> None:
        """A surface helper is still found even when nested helpers exist."""
        body = _parse_body(
            "def f():\n"
            "    _enforce_csrf(request)\n"
            "    if True:\n"
            "        def inner():\n"
            "            pass\n"
            "    return\n"
        )
        assert _body_contains_helper_call(body)


# ---------------------------------------------------------------------------
# _is_csrf_exempt_decorator
# ---------------------------------------------------------------------------


class TestIsCsrfExemptDecorator:
    """Decorator recognition for ``csrf_exempt`` and ``_typed_csrf_exempt``."""

    def test_direct_csrf_exempt(self) -> None:
        """``@csrf_exempt`` is recognized."""
        decos = _iter_decorators("@csrf_exempt\ndef f():\n    pass\n")
        assert _is_csrf_exempt_decorator(decos[0])

    def test_direct_typed_csrf_exempt(self) -> None:
        """``@_typed_csrf_exempt`` is recognized."""
        decos = _iter_decorators("@_typed_csrf_exempt\ndef f():\n    pass\n")
        assert _is_csrf_exempt_decorator(decos[0])

    def test_method_decorator_with_csrf_exempt(self) -> None:
        """``@method_decorator(csrf_exempt, name='dispatch')`` is recognized."""
        decos = _iter_decorators(
            "@method_decorator(csrf_exempt, name='dispatch')\nclass Cls:\n    pass\n"
        )
        assert _is_csrf_exempt_decorator(decos[0])

    def test_other_decorator_not_recognized(self) -> None:
        """An unrelated decorator is not recognized."""
        decos = _iter_decorators("@login_required\ndef f():\n    pass\n")
        assert not _is_csrf_exempt_decorator(decos[0])

    def test_method_decorator_with_other_name_not_recognized(self) -> None:
        """``@method_decorator(login_required, name='dispatch')`` is not."""
        decos = _iter_decorators(
            "@method_decorator(login_required, name='dispatch')\nclass Cls:\n    pass\n"
        )
        assert not _is_csrf_exempt_decorator(decos[0])


# ---------------------------------------------------------------------------
# _extract_method_decorator_name
# ---------------------------------------------------------------------------


class TestExtractMethodDecoratorName:
    """Extract the ``name=`` value from ``@method_decorator`` calls."""

    def test_name_keyword_found(self) -> None:
        decos = _iter_decorators(
            "@method_decorator(csrf_exempt, name='dispatch')\nclass Cls:\n    pass\n"
        )
        name = _extract_method_decorator_name(decos[0])
        assert name == "dispatch"

    def test_double_quoted_name(self) -> None:
        decos = _iter_decorators(
            '@method_decorator(csrf_exempt, name="dispatch")\nclass Cls:\n    pass\n'
        )
        name = _extract_method_decorator_name(decos[0])
        assert name == "dispatch"

    def test_no_name_keyword(self) -> None:
        decos = _iter_decorators("@method_decorator(csrf_exempt)\nclass Cls:\n    pass\n")
        name = _extract_method_decorator_name(decos[0])
        assert name is None

    def test_not_a_method_decorator(self) -> None:
        decos = _iter_decorators("@csrf_exempt\ndef f():\n    pass\n")
        name = _extract_method_decorator_name(decos[0])
        assert name is None


# ---------------------------------------------------------------------------
# _CsrfExemptVisitor  —  class-level scans (sibling-method gate)
# ---------------------------------------------------------------------------


class TestCsrfExemptVisitorClassLevel:
    """Class-level csrf_exempt scans must reject sibling-method bypasses."""

    PASS_CLASS_WITH_HELPER_IN_POST = (
        "@method_decorator(csrf_exempt, name='dispatch')\n"
        "class MyView(View):\n"
        "    def post(self, request):\n"
        "        _enforce_csrf(request)\n"
        "        return JsonResponse({})\n"
        "    def _helper(self):\n"
        "        pass\n"
    )

    FAIL_CLASS_HELPER_ONLY_IN_SIBLING = (
        "@method_decorator(csrf_exempt, name='dispatch')\n"
        "class MyView(View):\n"
        "    def post(self, request):\n"
        "        return JsonResponse({})\n"
        "    def _helper(self, request):\n"
        "        _enforce_csrf(request)\n"
    )

    FAIL_CLASS_HELPER_ONLY_IN_NESTED_DEF = (
        "@method_decorator(csrf_exempt, name='dispatch')\n"
        "class MyView(View):\n"
        "    def post(self, request):\n"
        "        def inner():\n"
        "            _enforce_csrf(request)\n"
        "        return JsonResponse({})\n"
    )

    FAIL_CLASS_NO_HELPER_AT_ALL = (
        "@method_decorator(csrf_exempt, name='dispatch')\n"
        "class MyView(View):\n"
        "    def post(self, request):\n"
        "        return JsonResponse({})\n"
    )

    def test_helper_in_post_passes(self) -> None:
        """Helper call in ``post`` satisfies the check."""
        assert _get_violation_count(self.PASS_CLASS_WITH_HELPER_IN_POST) == 0

    def test_helper_only_in_sibling_non_handler_fails(self) -> None:
        """Helper only in ``_helper`` (not a handler) is rejected."""
        assert _get_violation_count(self.FAIL_CLASS_HELPER_ONLY_IN_SIBLING) == 1

    def test_helper_only_in_nested_def_fails(self) -> None:
        """Helper only in a nested ``def`` inside handler is rejected."""
        assert _get_violation_count(self.FAIL_CLASS_HELPER_ONLY_IN_NESTED_DEF) == 1

    def test_no_helper_at_all_fails(self) -> None:
        """No helper anywhere in the class is rejected."""
        assert _get_violation_count(self.FAIL_CLASS_NO_HELPER_AT_ALL) == 1

    def test_mixed_sibling_with_surface_billing_pattern_passes(self) -> None:
        """Real billing-style: post() has _enforce_csrf, sibling helpers ignored."""
        source = (
            "from django.utils.decorators import method_decorator\n"
            "from django.views.decorators.csrf import csrf_exempt\n"
            "from django.views import View\n"
            "from django.http import JsonResponse\n"
            "\n"
            "@method_decorator(csrf_exempt, name='dispatch')\n"
            "class BillingStyleView(View):\n"
            "    http_method_names = ['post']\n"
            "\n"
            "    def post(self, request):\n"
            "        csrf_response = _enforce_csrf(request)\n"
            "        if csrf_response is not None:\n"
            "            return csrf_response\n"
            "        return JsonResponse({'ok': True})\n"
            "\n"
            "    def _unrelated_helper(self):\n"
            "        _enforce_csrf(request)\n"
        )
        assert _get_violation_count(source) == 0

    def test_notifications_webhook_pattern_passes(self) -> None:
        """Real notifications-style: post() has ingest_webhook_event."""
        source = (
            "@method_decorator(csrf_exempt, name='dispatch')\n"
            "class NotificationWebhookView(View):\n"
            "    http_method_names = ['post']\n"
            "\n"
            "    def post(self, request):\n"
            "        result = ingest_webhook_event(\n"
            "            body=request.body,\n"
            "            payload={},\n"
            "            signature='',\n"
            "            timestamp='',\n"
            "        )\n"
            "        return JsonResponse({'status': 'accepted'})\n"
        )
        assert _get_violation_count(source) == 0

    def test_sibling_handler_with_helper_passes(self) -> None:
        """Helper in ``dispatch`` itself also satisfies the check."""
        source = (
            "@method_decorator(csrf_exempt, name='dispatch')\n"
            "class MyView(View):\n"
            "    def dispatch(self, request, *args, **kwargs):\n"
            "        _enforce_csrf(request)\n"
            "        return super().dispatch(request, *args, **kwargs)\n"
            "    def post(self, request):\n"
            "        return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 0

    # ------------------------------------------------------------------
    # http_method_names constraint: only allowed handlers are checked
    # ------------------------------------------------------------------

    FAIL_CLASS_HELPER_ONLY_IN_DISALLOWED_HANDLER = (
        "@method_decorator(csrf_exempt, name='dispatch')\n"
        "class MyView(View):\n"
        "    http_method_names = ['get']\n"
        "    def get(self, request):\n"
        "        return JsonResponse({})\n"
        "    def post(self, request):\n"
        "        _enforce_csrf(request)\n"  # unreachable — post not allowed
    )

    PASS_CLASS_HELPER_IN_ALLOWED_HANDLER = (
        "@method_decorator(csrf_exempt, name='dispatch')\n"
        "class MyView(View):\n"
        "    http_method_names = ['post']\n"
        "    def post(self, request):\n"
        "        _enforce_csrf(request)\n"
        "        return JsonResponse({})\n"
        "    def get(self, request):\n"
        "        return JsonResponse({})\n"
    )

    def test_helper_only_in_disallowed_handler_fails(self) -> None:
        """Helper only in a handler excluded by ``http_method_names`` fails."""
        assert _get_violation_count(self.FAIL_CLASS_HELPER_ONLY_IN_DISALLOWED_HANDLER) == 1

    def test_helper_in_allowed_handler_passes(self) -> None:
        """Helper in a handler allowed by ``http_method_names`` passes."""
        assert _get_violation_count(self.PASS_CLASS_HELPER_IN_ALLOWED_HANDLER) == 0

    def test_helper_after_return_in_handler_unreachable_fails(self) -> None:
        """Helper after unconditional return in a handler body is unreachable."""
        source = (
            "@method_decorator(csrf_exempt, name='dispatch')\n"
            "class MyView(View):\n"
            "    http_method_names = ['post']\n"
            "    def post(self, request):\n"
            "        return JsonResponse({})\n"
            "        _enforce_csrf(request)\n"  # unreachable
        )
        assert _get_violation_count(source) == 1

    def test_helper_under_if_false_in_handler_unreachable_fails(self) -> None:
        """Helper under ``if False`` in a handler body is unreachable."""
        source = (
            "@method_decorator(csrf_exempt, name='dispatch')\n"
            "class MyView(View):\n"
            "    http_method_names = ['post']\n"
            "    def post(self, request):\n"
            "        if False:\n"
            "            _enforce_csrf(request)\n"  # unreachable
            "        return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 1

    # ------------------------------------------------------------------
    # Compile-time truthy literal handling — class-level (CR-SA46-001)
    # ------------------------------------------------------------------

    def test_class_helper_under_if_true_else_unreachable_fails(self) -> None:
        """Helper in ``else`` of ``if True: return ...`` in class handler."""
        source = (
            "@method_decorator(csrf_exempt, name='dispatch')\n"
            "class MyView(View):\n"
            "    http_method_names = ['post']\n"
            "    def post(self, request):\n"
            "        if True:\n"
            "            return JsonResponse({})\n"
            "        else:\n"
            "            _enforce_csrf(request)\n"  # unreachable
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 1

    def test_class_helper_under_if_nonempty_string_is_reachable_passes(self) -> None:
        r"""Helper inside ``if \"x\":`` in class handler is reachable."""
        source = (
            "@method_decorator(csrf_exempt, name='dispatch')\n"
            "class MyView(View):\n"
            "    http_method_names = ['post']\n"
            "    def post(self, request):\n"
            '        if "x":\n'
            "            _enforce_csrf(request)\n"
            "        return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 0

    def test_class_helper_nonempty_string_else_unreachable_fails(self) -> None:
        r"""Helper in ``else`` of ``if \"x\": return ...`` in class handler."""
        source = (
            "@method_decorator(csrf_exempt, name='dispatch')\n"
            "class MyView(View):\n"
            "    http_method_names = ['post']\n"
            "    def post(self, request):\n"
            '        if "x":\n'
            "            return JsonResponse({})\n"
            "        else:\n"
            "            _enforce_csrf(request)\n"  # unreachable
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 1

    def test_no_http_method_names_allows_all_handlers(self) -> None:
        """Without ``http_method_names``, all standard handlers are checked."""
        source = (
            "@method_decorator(csrf_exempt, name='dispatch')\n"
            "class MyView(View):\n"
            "    def post(self, request):\n"
            "        _enforce_csrf(request)\n"
            "        return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 0

    def test_disallowed_handler_no_helper_elsewhere_fails(self) -> None:
        """http_method_names restricts, and no allowed handler has a helper."""
        source = (
            "@method_decorator(csrf_exempt, name='dispatch')\n"
            "class MyView(View):\n"
            "    http_method_names = ['get']\n"
            "    def get(self, request):\n"
            "        return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 1


# ---------------------------------------------------------------------------
# _CsrfExemptVisitor  —  function-level scans (nested-def gate)
# ---------------------------------------------------------------------------


class TestCsrfExemptVisitorFunctionLevel:
    """Function-level csrf_exempt scans must reject nested-def bypasses."""

    PASS_FUNC_HELPER_DIRECT = (
        "@csrf_exempt\n"
        "def my_view(request):\n"
        "    _enforce_csrf(request)\n"
        "    return JsonResponse({})\n"
    )

    FAIL_FUNC_HELPER_ONLY_IN_NESTED_DEF = (
        "@csrf_exempt\n"
        "def my_view(request):\n"
        "    def helper():\n"
        "        _enforce_csrf(request)\n"
        "    return JsonResponse({})\n"
    )

    FAIL_FUNC_NO_HELPER = "@csrf_exempt\ndef my_view(request):\n    return JsonResponse({})\n"

    PASS_FUNC_TYPED_CSRF_EXEMPT = (
        "@_typed_csrf_exempt\n"
        "def upload_media_api(request):\n"
        "    author, auth_error = authenticate_blog_api_request(request)\n"
        "    if auth_error is not None:\n"
        "        return auth_error\n"
        "    return JsonResponse({}, status=201)\n"
    )

    def test_direct_helper_in_body_passes(self) -> None:
        assert _get_violation_count(self.PASS_FUNC_HELPER_DIRECT) == 0

    def test_nested_def_helper_fails(self) -> None:
        assert _get_violation_count(self.FAIL_FUNC_HELPER_ONLY_IN_NESTED_DEF) == 1

    def test_no_helper_fails(self) -> None:
        assert _get_violation_count(self.FAIL_FUNC_NO_HELPER) == 1

    def test_typed_csrf_exempt_with_auth_helper_passes(self) -> None:
        """Blog-style ``@_typed_csrf_exempt`` with ``authenticate_blog_api_request``."""
        assert _get_violation_count(self.PASS_FUNC_TYPED_CSRF_EXEMPT) == 0

    def test_nested_async_def_helper_fails(self) -> None:
        """Helper only in async nested def is rejected."""
        source = (
            "@csrf_exempt\n"
            "async def my_view(request):\n"
            "    async def inner():\n"
            "        _enforce_csrf(request)\n"
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 1

    def test_deeply_nested_helpers_all_fail(self) -> None:
        """Helper several levels deep is still rejected."""
        source = (
            "@csrf_exempt\n"
            "def my_view(request):\n"
            "    def level1():\n"
            "        def level2():\n"
            "            _enforce_csrf(request)\n"
            "        return\n"
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 1

    # ------------------------------------------------------------------
    # Reachability: unreachable helpers must NOT satisfy the pairing
    # ------------------------------------------------------------------

    def test_helper_after_return_unreachable_fails(self) -> None:
        """Helper after unconditional ``return`` is unreachable and rejected."""
        source = (
            "@csrf_exempt\n"
            "def my_view(request):\n"
            "    return JsonResponse({})\n"
            "    _enforce_csrf(request)\n"  # unreachable
        )
        assert _get_violation_count(source) == 1

    def test_helper_after_raise_unreachable_fails(self) -> None:
        """Helper after unconditional ``raise`` is unreachable and rejected."""
        source = (
            "@csrf_exempt\n"
            "def my_view(request):\n"
            "    raise NotImplementedError()\n"
            "    _enforce_csrf(request)\n"  # unreachable
        )
        assert _get_violation_count(source) == 1

    def test_helper_under_if_false_unreachable_fails(self) -> None:
        """Helper inside ``if False:`` body is unreachable and rejected."""
        source = (
            "@csrf_exempt\n"
            "def my_view(request):\n"
            "    if False:\n"
            "        _enforce_csrf(request)\n"  # unreachable
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 1

    def test_helper_under_if_zero_unreachable_fails(self) -> None:
        """Helper inside ``if 0:`` body is unreachable and rejected."""
        source = (
            "@csrf_exempt\n"
            "def my_view(request):\n"
            "    if 0:\n"
            "        _enforce_csrf(request)\n"  # unreachable
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 1

    def test_helper_under_if_true_is_reachable_passes(self) -> None:
        """Helper inside ``if True:`` body is reachable and accepted."""
        source = (
            "@csrf_exempt\n"
            "def my_view(request):\n"
            "    if True:\n"
            "        _enforce_csrf(request)\n"
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 0

    def test_helper_under_if_one_is_reachable_passes(self) -> None:
        """Helper inside ``if 1:`` body is reachable and accepted."""
        source = (
            "@csrf_exempt\n"
            "def my_view(request):\n"
            "    if 1:\n"
            "        _enforce_csrf(request)\n"
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 0

    def test_helper_before_return_is_reachable_passes(self) -> None:
        """Helper before unconditional return is reachable and accepted."""
        source = (
            "@csrf_exempt\n"
            "def my_view(request):\n"
            "    _enforce_csrf(request)\n"
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 0

    def test_helper_in_if_false_else_branch_passes(self) -> None:
        """Helper in the ``else`` of ``if False:`` is reachable and accepted."""
        source = (
            "@csrf_exempt\n"
            "def my_view(request):\n"
            "    if False:\n"
            "        pass\n"
            "    else:\n"
            "        _enforce_csrf(request)\n"
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 0

    # ------------------------------------------------------------------
    # Compile-time truthy literal handling (CR-SA46-001)
    # ------------------------------------------------------------------

    def test_helper_under_if_true_else_unreachable_fails(self) -> None:
        """Helper in ``else`` of ``if True: return ... else:`` is unreachable."""
        source = (
            "@csrf_exempt\n"
            "def my_view(request):\n"
            "    if True:\n"
            "        return JsonResponse({})\n"
            "    else:\n"
            "        _enforce_csrf(request)\n"  # unreachable
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 1

    def test_helper_under_if_nonempty_string_is_reachable_passes(self) -> None:
        r"""Helper inside ``if \"x\":`` body is reachable and accepted."""
        source = (
            "@csrf_exempt\n"
            "def my_view(request):\n"
            '    if "x":\n'
            "        _enforce_csrf(request)\n"
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 0

    def test_helper_under_if_nonempty_string_else_unreachable_fails(self) -> None:
        r"""Helper in ``else`` of ``if \"x\": return ... else:`` is unreachable."""
        source = (
            "@csrf_exempt\n"
            "def my_view(request):\n"
            '    if "x":\n'
            "        return JsonResponse({})\n"
            "    else:\n"
            "        _enforce_csrf(request)\n"  # unreachable
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 1

    def test_helper_under_if_nonempty_bytes_is_reachable_passes(self) -> None:
        r"""Helper inside ``if b\"x\":`` body is reachable and accepted."""
        source = (
            "@csrf_exempt\n"
            "def my_view(request):\n"
            '    if b"x":\n'
            "        _enforce_csrf(request)\n"
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 0

    def test_helper_under_if_empty_string_is_unreachable_fails(self) -> None:
        r"""Helper inside ``if \"\":`` body is unreachable and rejected."""
        source = (
            "@csrf_exempt\n"
            "def my_view(request):\n"
            '    if "":\n'
            "        _enforce_csrf(request)\n"  # unreachable
            "    return JsonResponse({})\n"
        )
        assert _get_violation_count(source) == 1


# ---------------------------------------------------------------------------
# Integration: all currently valid real-world patterns still pass
# ---------------------------------------------------------------------------


class TestCurrentCallSites:
    """All existing csrf_exempt call-sites in the repo pass the tightened gate."""

    def test_billing_session_view_pattern(self) -> None:
        """Billing session-authed view: post() has _enforce_csrf."""
        source = (
            "@method_decorator(csrf_exempt, name='dispatch')\n"
            "class CreateCheckoutSessionView(View):\n"
            "    http_method_names = ['post']\n"
            "    def post(self, request, *args, **kwargs):\n"
            "        csrf_response = _enforce_csrf(request)\n"
            "        if csrf_response is not None:\n"
            "            return csrf_response\n"
            "        return JsonResponse({'checkout_url': 'https://...'})\n"
        )
        assert _get_violation_count(source) == 0

    def test_billing_stripe_webhook_pattern(self) -> None:
        """Stripe webhook view: post() has handle_stripe_event."""
        source = (
            "@method_decorator(csrf_exempt, name='dispatch')\n"
            "class StripeWebhookView(View):\n"
            "    http_method_names = ['post']\n"
            "    def post(self, request, *args, **kwargs):\n"
            "        result = handle_stripe_event(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('Stripe-Signature', ''),\n"
            "        )\n"
            "        return JsonResponse({'ok': True})\n"
        )
        assert _get_violation_count(source) == 0

    def test_notifications_webhook_pattern(self) -> None:
        """Notification webhook: post() has ingest_webhook_event."""
        source = (
            "@method_decorator(csrf_exempt, name='dispatch')\n"
            "class NotificationWebhookView(View):\n"
            "    http_method_names = ['post']\n"
            "    def post(self, request, *args, **kwargs):\n"
            "        result = ingest_webhook_event(\n"
            "            body=request.body,\n"
            "            payload={},\n"
            "            signature=request.headers.get('Signature', ''),\n"
            "            timestamp=request.headers.get('Timestamp', ''),\n"
            "        )\n"
            "        return JsonResponse({'status': 'accepted'})\n"
        )
        assert _get_violation_count(source) == 0

    def test_blog_upload_media_pattern(self) -> None:
        """Blog upload-media: function with @_typed_csrf_exempt + authenticate_blog_api_request."""
        source = (
            "@_typed_csrf_exempt\n"
            "def upload_media_api(request):\n"
            "    author, auth_error = authenticate_blog_api_request(request)\n"
            "    if auth_error is not None:\n"
            "        return auth_error\n"
            "    return JsonResponse({}, status=201)\n"
        )
        assert _get_violation_count(source) == 0

    def test_blog_publish_post_pattern(self) -> None:
        """Blog publish-post: function with @_typed_csrf_exempt + authenticate_blog_api_request."""
        source = (
            "@_typed_csrf_exempt\n"
            "def publish_post_api(request):\n"
            "    author, auth_error = authenticate_blog_api_request(request)\n"
            "    if auth_error is not None:\n"
            "        return auth_error\n"
            "    post = _create_post_from_payload(author, payload)\n"
            "    return JsonResponse({}, status=201)\n"
        )
        assert _get_violation_count(source) == 0


# ---------------------------------------------------------------------------
# Sanity: missing-helper violations are still detected
# ---------------------------------------------------------------------------


class TestMissingHelperDetected:
    """Scopes without any helper call are still flagged."""

    def test_function_no_helper_fails(self) -> None:
        source = "@csrf_exempt\ndef bad_view(request):\n    return JsonResponse({'oops': True})\n"
        assert _get_violation_count(source) == 1

    def test_class_no_helper_fails(self) -> None:
        source = (
            "@method_decorator(csrf_exempt, name='dispatch')\n"
            "class BadView(View):\n"
            "    def post(self, request):\n"
            "        return JsonResponse({'oops': True})\n"
        )
        assert _get_violation_count(source) == 1

    def test_async_function_no_helper_fails(self) -> None:
        source = (
            "@csrf_exempt\nasync def bad_view(request):\n    return JsonResponse({'oops': True})\n"
        )
        assert _get_violation_count(source) == 1

    def test_unrelated_decorator_no_false_positive(self) -> None:
        """A non-csrf_exempt function should never be flagged."""
        source = "def normal_view(request):\n    return JsonResponse({'ok': True})\n"
        assert _get_violation_count(source) == 0
