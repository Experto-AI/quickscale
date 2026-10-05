"""Control cases for the misc module-convention rules."""

from __future__ import annotations

from dataclasses import replace

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    _golden_module,
    _violations,
    _with_files,
)


def test_check_registration_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace("register_module_checks(self, [check_demo])", "pass"),
    )
    assert _violations(checker.rule_10_checks_errors, broken)


def test_error_base_control() -> None:
    module = _golden_module()
    broken = _with_files(module, exceptions="class DemoProblem(Exception):\n    pass\n")
    assert _violations(checker.rule_10_checks_errors, broken)


def test_ready_raise_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "register_module_checks(self, [check_demo])",
            "raise RuntimeError('boom')",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, broken)


def test_email_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.core.mail import send_mail\n\n\n"
            "def index():\n    send_mail('a', 'b', 'c', ['d'])\n"
        ),
    )
    assert _violations(checker.rule_20_email, broken)


def test_email_requirement_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views="from quickscale_modules_notifications.services import send_notification\n",
    )
    assert any(
        "requiring notifications" in violation
        for violation in _violations(checker.rule_20_email, broken)
    )


def test_registration_after_return_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        return\n        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_in_dead_branch_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        if False:\n            register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_after_terminal_branch_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        if True:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_after_terminal_try_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        try:\n"
            "            return\n"
            "        finally:\n"
            "            pass\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_in_short_circuited_expression_control() -> None:
    module = _golden_module()
    dead = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        if False and register_module_checks(self, [check_demo]):\n            pass\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, dead)
    )
    short_circuit = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        True or register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, short_circuit)
    )


def test_registration_with_static_boolop_test_control() -> None:
    module = _golden_module()
    dead = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        if False and True:\n            register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, dead)
    )
    terminal = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        if True or False:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, terminal)
    )
    executed = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        if True and True:\n            register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, executed) == []


def test_registration_in_uncalled_lambda_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        unused = lambda: register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_in_later_handler_control() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        self.setup_checks()\n"
            "\n"
            "    def setup_checks(self) -> None:\n"
            "        try:\n"
            "            raise ValueError('boom')\n"
            "        except TypeError:\n"
            "            pass\n"
            "        except ValueError:\n"
            "            register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, good) == []


def test_registration_after_break_bypasses_else_control() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, good) == []
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            pass\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )
    nested_break = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            for inner in [1]:\n"
            "                break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, nested_break)
    )
    dead_break = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            if False:\n"
            "                break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, dead_break)
    )
    try_star = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            try:\n"
            "                break\n"
            "            except* Exception:\n"
            "                pass\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, try_star) == []
    unreachable_break = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            return\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, unreachable_break)
    )
    terminal_try = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            try:\n"
            "                return\n"
            "            finally:\n"
            "                pass\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, terminal_try)
    )
    terminal_match = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            match 1:\n"
            "                case _:\n"
            "                    return\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, terminal_match)
    )
    finally_override = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            try:\n"
            "                break\n"
            "            finally:\n"
            "                return\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, finally_override)
    )


def test_registration_loop_termination_controls() -> None:
    module = _golden_module()
    nested_terminal_loop = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            for inner in []:\n"
            "                pass\n"
            "            else:\n"
            "                return\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, nested_terminal_loop)
    )
    nested_terminal_match = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            if True:\n"
            "                match 1:\n"
            "                    case _:\n"
            "                        return\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, nested_terminal_match)
    )
    continue_before_break = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            continue\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, continue_before_break)
    )
    finally_continue = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            try:\n"
            "                break\n"
            "            finally:\n"
            "                continue\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, finally_continue)
    )
    caught_raise = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        self.setup_checks()\n"
            "\n"
            "    def setup_checks(self) -> None:\n"
            "        for _ in [1]:\n"
            "            try:\n"
            "                raise ValueError('boom')\n"
            "            except ValueError:\n"
            "                pass\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, caught_raise) == []
    guarded_match = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        self.setup_checks()\n"
            "\n"
            "    def setup_checks(self) -> None:\n"
            "        for _ in [1]:\n"
            "            match 1:\n"
            "                case _ if False:\n"
            "                    return\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, guarded_match) == []
    compound_continue = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            if True:\n"
            "                continue\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, compound_continue)
    )
    match_subject = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        match register_module_checks(self, [check_demo]):\n"
            "            case _:\n"
            "                pass\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, match_subject) == []
    match_guard = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        match 1:\n"
            "            case _ if register_module_checks(self, [check_demo]) is None:\n"
            "                pass\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, match_guard) == []
    conditional_finally = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        flag = False\n"
            "        for _ in [1]:\n"
            "            try:\n"
            "                break\n"
            "            finally:\n"
            "                if flag:\n"
            "                    continue\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, conditional_finally) == []
    compound_continue_suffix = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            if True:\n"
            "                if flag:\n"
            "                    pass\n"
            "                continue\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, compound_continue_suffix)
    )
    finally_suffix = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            try:\n"
            "                break\n"
            "            finally:\n"
            "                if flag:\n"
            "                    pass\n"
            "                continue\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, finally_suffix)
    )
    wrapped_continue_call = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            if True:\n"
            "                continue\n"
            "            register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, wrapped_continue_call)
    )
    dead_match = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            match 1:\n"
            "                case _ if False:\n"
            "                    break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, dead_match)
    )


def test_registration_after_return_inside_loop_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        while True:\n"
            "            return\n"
            "            register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_in_conditional_expression_control() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        value = 1 if (register_module_checks(self, [check_demo]) or True) else 2\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, good) == []


def test_registration_context_expression_control() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        with nullcontext(register_module_checks(self, [check_demo])):\n"
            "            pass\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, good) == []


def test_registration_after_caught_raise_control() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        self.setup_checks()\n"
            "\n"
            "    def setup_checks(self) -> None:\n"
            "        try:\n"
            "            raise ValueError('boom')\n"
            "        except ValueError:\n"
            "            pass\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, good) == []


def test_registration_in_evaluated_condition_control() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        if register_module_checks(self, [check_demo]):\n            pass\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, good) == []


def test_registration_returned_call_is_credited() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        return register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, good) == []


def test_registration_in_unrelated_class_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        pass\n",
        )
        + (
            "\n\nclass OtherConfig:\n"
            "    def ready(self) -> None:\n"
            "        register_module_checks(self, [check_demo])\n"
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_in_uncalled_nested_function_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        def unused() -> None:\n"
            "            register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_class_method_shadowed_by_module_helper_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        self.setup_checks()\n\n    def setup_checks(self) -> None:\n        pass\n",
        )
        + "\n\ndef setup_checks() -> None:\n    register_module_checks(None, [])\n",
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_module_helper_shadowed_by_class_method_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        setup_checks()\n\n"
            "    def setup_checks(self) -> None:\n"
            "        register_module_checks(self, [check_demo])\n",
        )
        + "\n\ndef setup_checks() -> None:\n    pass\n",
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_outside_ready_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "def ready(self) -> None:", "def unused(self) -> None:"
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_swallowed_registration_in_except_star_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        try:\n"
            "            register_module_checks(self, [check_demo])\n"
            "        except* Exception:\n"
            "            pass\n",
        ),
    )
    assert any(
        "catches a registration failure" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_swallowed_registration_failure_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        try:\n"
            "            register_module_checks(self, [check_demo])\n"
            "        except Exception:\n"
            "            pass\n",
        ),
    )
    assert any(
        "catches a registration failure" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_email_dependency_shape_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views="from quickscale_modules_notifications.services import send_notification\n",
    )
    broken = replace(broken, manifest={**broken.manifest, "required_modules": 1})
    assert any(
        "requiring notifications" in violation
        for violation in _violations(checker.rule_20_email, broken)
    )
    assert any(
        "must be a list" in violation
        for violation in _violations(checker.rule_39_module_dependencies, broken)
    )


def test_stub_exemption_controls() -> None:
    module = _golden_module()
    assert _violations(checker.rule_45_stub_exemptions, module) == []
    per_module = replace(
        module,
        root_files={
            **module.root_files,
            "pyproject.toml": module.root_files["pyproject.toml"]
            + "\n[tool.mypy]\ndisallow_untyped_defs = false\n",
        },
    )
    assert any(
        "declares a per-module [tool.mypy] table" in violation
        for violation in _violations(checker.rule_45_stub_exemptions, per_module)
    )
    overrides_only = replace(
        module,
        root_files={
            **module.root_files,
            "pyproject.toml": module.root_files["pyproject.toml"]
            + '\n[[tool.mypy.overrides]]\nmodule = "anymail.*"\n'
            "ignore_missing_imports = true\n",
        },
    )
    assert any(
        "declares a per-module [tool.mypy] table" in violation
        for violation in _violations(checker.rule_45_stub_exemptions, overrides_only)
    )
