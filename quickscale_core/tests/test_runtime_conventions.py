"""Tests for the shared runtime convention helpers (SA218).

Covers Module Conventions rules 4 (``AppConfig`` capabilities), 9 (the one
DRF error shape), and 10 (startup checks run from ``ready()`` and registered
as system checks), including a control per helper proving failure is loud.
"""

from __future__ import annotations

import re

import pytest
from django.core.exceptions import ImproperlyConfigured

from quickscale_core.runtime import conventions

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")


class _FakeAppConfig:
    """A stand-in for ``django.apps.AppConfig`` with only the read surface used."""

    def __init__(self, label: str, **attributes: object) -> None:
        self.label = label
        for name, value in attributes.items():
            setattr(self, name, value)


class _FakeAppRegistry:
    def __init__(self, app_configs: list[_FakeAppConfig]) -> None:
        self._app_configs = tuple(app_configs)

    def get_app_configs(self) -> list[_FakeAppConfig]:
        return list(self._app_configs)


# ===================================================================
# collect_capabilities — rule 4
# ===================================================================


class TestCollectCapabilities:
    def test_collects_tuple_declarations_in_app_label_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            conventions,
            "apps",
            _FakeAppRegistry(
                [
                    _FakeAppConfig("z_provider", handlers=("z1",)),
                    _FakeAppConfig("a_provider", handlers=("a1", "a2")),
                    _FakeAppConfig("no_declaration"),
                ]
            ),
        )

        assert conventions.collect_capabilities("handlers") == ("a1", "a2", "z1")

    def test_collects_declaration_method(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Provider(_FakeAppConfig):
            def handlers(self) -> tuple[str, ...]:
                return ("from_method",)

        monkeypatch.setattr(
            conventions,
            "apps",
            _FakeAppRegistry([Provider("method_provider")]),
        )

        assert conventions.collect_capabilities("handlers") == ("from_method",)

    def test_collects_declaration_method_returning_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class SwitchedOffProvider(_FakeAppConfig):
            def handlers(self) -> tuple[str, ...]:
                return ()

        monkeypatch.setattr(
            conventions,
            "apps",
            _FakeAppRegistry([SwitchedOffProvider("off_provider")]),
        )

        assert conventions.collect_capabilities("handlers") == ()

    def test_no_declarations_returns_empty_tuple(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            conventions, "apps", _FakeAppRegistry([_FakeAppConfig("quiet")])
        )

        assert conventions.collect_capabilities("handlers") == ()

    def test_control_string_declaration_fails_loudly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            conventions,
            "apps",
            _FakeAppRegistry([_FakeAppConfig("stringy", handlers="one_handler")]),
        )

        with pytest.raises(ValueError, match="stringy.*as a string"):
            conventions.collect_capabilities("handlers")

    def test_control_none_declaration_fails_loudly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            conventions,
            "apps",
            _FakeAppRegistry([_FakeAppConfig("empty_provider", handlers=None)]),
        )

        with pytest.raises(ValueError, match="empty_provider.*as None"):
            conventions.collect_capabilities("handlers")

    def test_control_mapping_declaration_fails_loudly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            conventions,
            "apps",
            _FakeAppRegistry([_FakeAppConfig("mapped", handlers={"key": "handler"})]),
        )

        with pytest.raises(ValueError, match="mapped.*as a mapping"):
            conventions.collect_capabilities("handlers")

    def test_control_one_shot_iterator_declaration_fails_loudly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class IteratorProvider(_FakeAppConfig):
            def handlers(self):
                return (handler for handler in ("first", "second"))

        monkeypatch.setattr(
            conventions,
            "apps",
            _FakeAppRegistry([IteratorProvider("one_shot")]),
        )

        with pytest.raises(ValueError, match="one_shot.*as a one-shot iterator"):
            conventions.collect_capabilities("handlers")

    def test_control_broken_declaration_property_fails_loudly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class BrokenProvider(_FakeAppConfig):
            @property
            def handlers(self) -> tuple[str, ...]:
                raise AttributeError("misconfigured handler")

        monkeypatch.setattr(
            conventions,
            "apps",
            _FakeAppRegistry([BrokenProvider("broken")]),
        )

        with pytest.raises(
            ValueError, match="broken.*reading it raised AttributeError"
        ):
            conventions.collect_capabilities("handlers")

    def test_control_non_iterable_declaration_fails_loudly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            conventions,
            "apps",
            _FakeAppRegistry([_FakeAppConfig("opaque", handlers=object())]),
        )

        with pytest.raises(ValueError, match="opaque.*non-iterable"):
            conventions.collect_capabilities("handlers")

    @pytest.mark.parametrize("capability", ["", 7, None])
    def test_control_invalid_capability_name_fails_loudly(
        self, capability: object
    ) -> None:
        with pytest.raises(ValueError, match="non-empty capability name"):
            conventions.collect_capabilities(capability)  # type: ignore[arg-type]


# ===================================================================
# register_module_checks — rule 10
# ===================================================================


@pytest.fixture
def system_check_registry():
    """Snapshot Django's system-check registry and restore it afterwards."""
    from django.core.checks.registry import registry

    before = set(registry.registered_checks)
    yield registry
    registry.registered_checks.clear()
    registry.registered_checks.update(before)


class TestRegisterModuleChecks:
    def test_passing_checks_register_with_the_app_label(
        self, system_check_registry
    ) -> None:
        app_config = _FakeAppConfig("quickscale_test_module")

        def check(app_configs: object = None, **kwargs: object) -> list:
            return []

        conventions.register_module_checks(app_config, [check])

        assert check in system_check_registry.registered_checks
        assert check.tags == ("quickscale_test_module",)

    def test_control_error_message_fails_startup_and_lists_every_failure(
        self, system_check_registry
    ) -> None:
        from django.core.checks import Error, Warning

        app_config = _FakeAppConfig("quickscale_test_module")

        def broken_check(app_configs: object = None, **kwargs: object) -> list:
            return [
                Error(
                    "BLOG_API_TOKENS is malformed.",
                    id="quickscale_test_module.E001",
                ),
                Warning("advisory only", id="quickscale_test_module.W001"),
            ]

        def raising_check(app_configs: object = None, **kwargs: object) -> list:
            raise ValueError("malformed declaration")

        with pytest.raises(ImproperlyConfigured) as excinfo:
            conventions.register_module_checks(
                app_config, [broken_check, raising_check]
            )

        message = str(excinfo.value)
        assert "quickscale_test_module" in message
        assert "quickscale_test_module.E001: BLOG_API_TOKENS is malformed." in message
        assert "advisory only" not in message
        assert "ValueError: malformed declaration" in message
        assert broken_check not in system_check_registry.registered_checks

    def test_warning_alone_does_not_fail_startup(self, system_check_registry) -> None:
        from django.core.checks import Warning

        app_config = _FakeAppConfig("quickscale_test_module")

        def warning_check(app_configs: object = None, **kwargs: object) -> list:
            return [Warning("advisory only", id="quickscale_test_module.W001")]

        conventions.register_module_checks(app_config, [warning_check])

        assert warning_check in system_check_registry.registered_checks
        assert warning_check.tags == ("quickscale_test_module",)

    def test_control_none_returning_check_fails_loudly(
        self, system_check_registry
    ) -> None:
        app_config = _FakeAppConfig("quickscale_test_module")

        def none_check(app_configs: object = None, **kwargs: object) -> None:
            return None

        with pytest.raises(ValueError, match="must return a sequence"):
            conventions.register_module_checks(app_config, [none_check])

    def test_control_non_iterable_check_return_fails_loudly(
        self, system_check_registry
    ) -> None:
        app_config = _FakeAppConfig("quickscale_test_module")

        def int_check(app_configs: object = None, **kwargs: object) -> int:
            return 7

        with pytest.raises(ValueError, match="must return a sequence"):
            conventions.register_module_checks(app_config, [int_check])

    def test_control_non_callable_check_fails_loudly(
        self, system_check_registry
    ) -> None:
        app_config = _FakeAppConfig("quickscale_test_module")

        with pytest.raises(ValueError, match="expected a check callable"):
            conventions.register_module_checks(app_config, ["not_a_check"])

    def test_control_invalid_message_fails_loudly(self, system_check_registry) -> None:
        app_config = _FakeAppConfig("quickscale_test_module")

        def bad_check(app_configs: object = None, **kwargs: object) -> list:
            return ["not a CheckMessage"]

        with pytest.raises(ValueError, match="instead of CheckMessage"):
            conventions.register_module_checks(app_config, [bad_check])

    def test_skip_env_var_skips_the_eager_run_but_registers(
        self, system_check_registry, monkeypatch
    ) -> None:
        """``all`` skips the eager refusal and still registers the checks."""
        from django.core.checks import Error

        app_config = _FakeAppConfig("quickscale_test_module")

        def failing_check(app_configs: object = None, **kwargs: object) -> list:
            return [Error("boom", id="quickscale_test_module.E001")]

        monkeypatch.setenv("QUICKSCALE_SKIP_MODULE_CHECKS", "all")
        monkeypatch.setattr(
            conventions.sys, "argv", ["manage.py", "collectstatic", "--noinput"]
        )

        conventions.register_module_checks(app_config, [failing_check])

        assert failing_check in system_check_registry.registered_checks

    def test_skip_env_var_accepts_a_comma_list(
        self, system_check_registry, monkeypatch
    ):
        """A label list skips only the named module."""
        from django.core.checks import Error

        app_config = _FakeAppConfig("quickscale_test_module")

        def failing_check(app_configs: object = None, **kwargs: object) -> list:
            return [Error("boom", id="quickscale_test_module.E001")]

        monkeypatch.setenv(
            "QUICKSCALE_SKIP_MODULE_CHECKS",
            "quickscale_other_module, quickscale_test_module",
        )
        monkeypatch.setattr(
            conventions.sys, "argv", ["manage.py", "collectstatic", "--noinput"]
        )

        conventions.register_module_checks(app_config, [failing_check])

        assert failing_check in system_check_registry.registered_checks

    def test_skip_env_var_for_another_module_still_fails_startup(
        self, system_check_registry, monkeypatch
    ) -> None:
        """A skip that does not name this label leaves the eager run in force."""
        from django.core.checks import Error

        app_config = _FakeAppConfig("quickscale_test_module")

        def failing_check(app_configs: object = None, **kwargs: object) -> list:
            return [Error("boom", id="quickscale_test_module.E001")]

        monkeypatch.setenv("QUICKSCALE_SKIP_MODULE_CHECKS", "quickscale_other_module")
        monkeypatch.setattr(
            conventions.sys, "argv", ["manage.py", "collectstatic", "--noinput"]
        )

        with pytest.raises(ImproperlyConfigured):
            conventions.register_module_checks(app_config, [failing_check])

    def test_skip_env_var_is_ineffective_on_a_serving_path(
        self, system_check_registry, monkeypatch
    ) -> None:
        """A skip value in a serving process never disables the eager checks."""
        from django.core.checks import Error

        app_config = _FakeAppConfig("quickscale_test_module")

        def failing_check(app_configs: object = None, **kwargs: object) -> list:
            return [Error("boom", id="quickscale_test_module.E001")]

        monkeypatch.setenv("QUICKSCALE_SKIP_MODULE_CHECKS", "all")
        monkeypatch.setattr(
            conventions.sys, "argv", ["gunicorn", "myproject.wsgi:application"]
        )

        with pytest.raises(ImproperlyConfigured):
            conventions.register_module_checks(app_config, [failing_check])

    def test_skip_env_var_is_ineffective_when_collectstatic_is_only_an_argument(
        self, system_check_registry, monkeypatch
    ) -> None:
        """A serving argv carrying collectstatic as a value still runs checks."""
        from django.core.checks import Error

        app_config = _FakeAppConfig("quickscale_test_module")

        def failing_check(app_configs: object = None, **kwargs: object) -> list:
            return [Error("boom", id="quickscale_test_module.E001")]

        monkeypatch.setenv("QUICKSCALE_SKIP_MODULE_CHECKS", "all")
        for argv in (
            ["gunicorn", "--name", "collectstatic", "myproject.wsgi:application"],
            ["/usr/local/bin/gunicorn", "collectstatic"],
        ):
            monkeypatch.setattr(conventions.sys, "argv", argv)
            with pytest.raises(ImproperlyConfigured):
                conventions.register_module_checks(app_config, [failing_check])

    def test_skip_env_var_applies_to_django_admin_collectstatic(
        self, system_check_registry, monkeypatch
    ) -> None:
        """The django-admin entry point is a genuine management invocation."""
        from django.core.checks import Error

        app_config = _FakeAppConfig("quickscale_test_module")

        def failing_check(app_configs: object = None, **kwargs: object) -> list:
            return [Error("boom", id="quickscale_test_module.E001")]

        monkeypatch.setenv("QUICKSCALE_SKIP_MODULE_CHECKS", "all")
        monkeypatch.setattr(conventions.sys, "argv", ["django-admin", "collectstatic"])

        conventions.register_module_checks(app_config, [failing_check])

        assert failing_check in system_check_registry.registered_checks


# ===================================================================
# exception_handler — rule 9
# ===================================================================


@pytest.fixture(scope="class")
def configured_django():
    """Configure Django and DRF's import-time settings for the handler tests."""
    import django
    from django.conf import settings

    if not settings.configured:
        settings.configure(
            DEBUG=False,
            DATABASES={},
            INSTALLED_APPS=[],
            LANGUAGE_CODE="en-us",
            REST_FRAMEWORK={},
            USE_I18N=True,
            USE_TZ=True,
        )
    django.setup()


@pytest.mark.usefixtures("configured_django")
class TestExceptionHandler:
    def _handler(self):
        from quickscale_core.runtime.conventions import exception_handler

        return exception_handler

    def test_validation_error_takes_the_one_shape(self) -> None:
        from rest_framework.exceptions import ValidationError

        handler = self._handler()
        response = handler(ValidationError({"title": ["This field is required."]}), {})

        assert response is not None
        assert response.status_code == 400
        assert response.data == {
            "error": {
                "code": "validation_error",
                "message": "Invalid input.",
                "fields": {"title": ["This field is required."]},
            }
        }

    def test_non_field_validation_error_takes_the_one_shape(self) -> None:
        from rest_framework.exceptions import ValidationError

        handler = self._handler()
        response = handler(ValidationError(["bad input"]), {})

        assert response is not None
        assert response.status_code == 400
        assert response.data["error"]["fields"] == {"non_field_errors": ["bad input"]}

    def test_nested_validation_error_flattens_field_paths(self) -> None:
        from rest_framework.exceptions import ValidationError

        handler = self._handler()
        response = handler(
            ValidationError({"address": {"city": ["This field is required."]}}), {}
        )

        assert response is not None
        assert response.status_code == 400
        assert response.data["error"]["fields"] == {
            "address.city": ["This field is required."]
        }

    def test_nested_list_validation_error_keeps_item_positions(self) -> None:
        from rest_framework.exceptions import ValidationError

        handler = self._handler()
        response = handler(
            ValidationError({"addresses": [{}, {"city": ["This field is required."]}]}),
            {},
        )

        assert response is not None
        assert response.status_code == 400
        assert response.data["error"]["fields"] == {
            "addresses[1].city": ["This field is required."]
        }

    def test_nested_many_serializer_errors_keep_item_positions(self) -> None:
        from rest_framework import serializers
        from rest_framework.exceptions import ValidationError

        class AddressSerializer(serializers.Serializer):
            city = serializers.CharField(allow_blank=False)

        class PersonSerializer(serializers.Serializer):
            addresses = AddressSerializer(many=True)

        serializer = PersonSerializer(
            data={"addresses": [{"city": "London"}, {"city": ""}]}
        )
        assert not serializer.is_valid()

        handler = self._handler()
        response = handler(ValidationError(serializer.errors), {})

        assert response is not None
        fields = response.data["error"]["fields"]
        assert list(fields) == ["addresses[1].city"]
        assert "blank" in fields["addresses[1].city"][0]

    @pytest.mark.parametrize(
        ("exception_factory", "status_code", "code"),
        [
            ("NotFound", 404, "not_found"),
            ("PermissionDenied", 403, "permission_denied"),
            ("Throttled", 429, "throttled"),
            ("AuthenticationFailed", 401, "authentication_failed"),
        ],
    )
    def test_api_exception_codes_and_statuses(
        self, exception_factory: str, status_code: int, code: str
    ) -> None:
        import rest_framework.exceptions as drf_exceptions

        handler = self._handler()
        exc = getattr(drf_exceptions, exception_factory)()
        response = handler(exc, {})

        assert response is not None
        assert response.status_code == status_code
        assert response.data["error"]["code"] == code
        assert isinstance(response.data["error"]["message"], str)
        assert response.data["error"]["message"]
        assert "fields" not in response.data["error"]

    def test_django_http_exceptions_are_mapped(self) -> None:
        from django.core.exceptions import PermissionDenied
        from django.http import Http404

        handler = self._handler()

        not_found = handler(Http404(), {})
        denied = handler(PermissionDenied(), {})

        assert not_found is not None
        assert not_found.status_code == 404
        assert not_found.data["error"]["code"] == "not_found"
        assert denied is not None
        assert denied.status_code == 403
        assert denied.data["error"]["code"] == "permission_denied"

    def test_response_headers_are_preserved(self) -> None:
        from rest_framework.exceptions import AuthenticationFailed

        handler = self._handler()
        exc = AuthenticationFailed()
        exc.auth_header = 'Token realm="api"'  # type: ignore[attr-defined]
        response = handler(exc, {})

        assert response is not None
        assert response["WWW-Authenticate"] == 'Token realm="api"'

    def test_control_unhandled_exception_is_not_swallowed(self) -> None:
        handler = self._handler()

        assert handler(ValueError("unexpected server error"), {}) is None

    def test_every_handled_error_has_exactly_the_one_shape(self) -> None:
        import rest_framework.exceptions as drf_exceptions
        from django.core.exceptions import PermissionDenied
        from django.http import Http404

        handler = self._handler()
        exceptions = [
            drf_exceptions.ValidationError({"title": ["required"]}),
            drf_exceptions.ValidationError(["required"]),
            drf_exceptions.NotFound(),
            drf_exceptions.PermissionDenied(),
            drf_exceptions.Throttled(),
            drf_exceptions.AuthenticationFailed(),
            drf_exceptions.MethodNotAllowed("POST"),
            Http404(),
            PermissionDenied(),
        ]

        for exc in exceptions:
            response = handler(exc, {})
            assert response is not None
            assert set(response.data) == {"error"}, type(exc)
            error = response.data["error"]
            assert set(error) <= {"code", "message", "fields"}, type(exc)
            assert SNAKE_CASE.match(error["code"]), type(exc)
            assert isinstance(error["message"], str) and error["message"]
            if "fields" in error:
                assert isinstance(exc, drf_exceptions.ValidationError), type(exc)
                assert isinstance(error["fields"], dict)
