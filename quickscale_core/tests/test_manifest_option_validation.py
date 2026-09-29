"""Manifest-declared option validation (SA217).

Covers the option-validation engine, the loader's required-field contract for
the per-option ``validation`` block, the shipped manifests' conformance to the
declared schema, and the ``plan``/``apply`` config-validation seam that makes
a bad value fail with the setting's name.
"""

from pathlib import Path

import pytest

from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.option_validation import (
    collect_option_validation_issues,
    validate_module_options,
)
from quickscale_core.manifest.schema import ConfigOption, ModuleManifest
from quickscale_core.schema.config_schema import ConfigValidationError, validate_config


def _manifest(*options: ConfigOption, name: str = "demo") -> ModuleManifest:
    """Build a small manifest carrying *options* as mutable where possible."""
    mutable = {}
    immutable = {}
    for option in options:
        if option.django_setting:
            mutable[option.name] = option
        else:
            immutable[option.name] = option
    return ModuleManifest(
        name=name,
        version="1.0.0",
        mutable_options=mutable,
        immutable_options=immutable,
    )


def _option(
    name: str,
    *,
    option_type: str = "string",
    default: object = "",
    setting: str | None = None,
    validation: dict[str, object] | None = None,
) -> ConfigOption:
    return ConfigOption(
        name=name,
        option_type=option_type,
        default=default,
        django_setting=setting,
        description="A demo option",
        mutability="mutable" if setting else "immutable",
        validation=validation or {},
    )


class TestOptionValidationEngine:
    """The engine reads type and the per-option validation block."""

    def test_wrong_type_names_the_setting(self) -> None:
        manifest = _manifest(
            _option(
                "listings_per_page",
                option_type="integer",
                default=12,
                setting="LISTINGS_PER_PAGE",
            )
        )
        issues = validate_module_options(manifest, {"listings_per_page": "twelve"})
        assert issues == [
            "LISTINGS_PER_PAGE (modules.demo.listings_per_page) must be an integer"
        ]

    def test_boolean_is_not_an_integer(self) -> None:
        manifest = _manifest(
            _option("per_page", option_type="integer", default=1, setting="PER_PAGE")
        )
        issues = validate_module_options(manifest, {"per_page": True})
        assert "must be an integer" in issues[0]

    def test_choices_reject_a_value_outside_the_set(self) -> None:
        manifest = _manifest(
            _option(
                "mode",
                default="solo",
                setting="QUICKSCALE_MODE",
                validation={"choices": ["solo", "saas"]},
            )
        )
        issues = validate_module_options(manifest, {"mode": "team"})
        assert issues == [
            "QUICKSCALE_MODE (modules.demo.mode) must be one of: solo, saas"
        ]

    def test_range_enforces_minimum_and_maximum(self) -> None:
        manifest = _manifest(
            _option(
                "ttl",
                option_type="integer",
                default=1,
                setting="TTL_SECONDS",
                validation={"min": 1, "max": 10},
            )
        )
        assert validate_module_options(manifest, {"ttl": 0}) == [
            "TTL_SECONDS (modules.demo.ttl) must be >= 1"
        ]
        assert validate_module_options(manifest, {"ttl": 11}) == [
            "TTL_SECONDS (modules.demo.ttl) must be <= 10"
        ]
        assert validate_module_options(manifest, {"ttl": 5}) == []

    def test_pattern_matches_the_whole_value(self) -> None:
        manifest = _manifest(
            _option(
                "rate_limit",
                default="5/hour",
                setting="RATE_LIMIT",
                validation={"pattern": r"^\d+/(second|minute|hour|day)$"},
            )
        )
        assert validate_module_options(manifest, {"rate_limit": "5/fortnight"}) == [
            "RATE_LIMIT (modules.demo.rate_limit) must match pattern "
            r"^\d+/(second|minute|hour|day)$"
        ]
        assert validate_module_options(manifest, {"rate_limit": "5/hour"}) == []

    def test_required_when_fires_only_when_the_condition_holds(self) -> None:
        manifest = _manifest(
            _option(
                "automation_enabled",
                option_type="boolean",
                default=False,
                setting="AUTOMATION_ENABLED",
            ),
            _option("schedule", default="0 2 * * *", setting="SCHEDULE"),
            _option("bucket", setting="BUCKET"),
        )
        manifest.mutable_options["schedule"].validation = {
            "required_when": {"automation_enabled": True}
        }
        manifest.mutable_options["bucket"].validation = {
            "required_when": {"automation_enabled": True}
        }
        assert validate_module_options(manifest, {}) == []
        issues = validate_module_options(
            manifest, {"automation_enabled": True, "schedule": "  ", "bucket": ""}
        )
        assert any(
            "SCHEDULE (modules.demo.schedule) is required when " in issue
            for issue in issues
        )
        assert any(
            "BUCKET (modules.demo.bucket) is required when " in issue
            for issue in issues
        )
        assert all(
            "AUTOMATION_ENABLED (modules.demo.automation_enabled) is true" in issue
            for issue in issues
        )

    def test_required_when_in_selector(self) -> None:
        manifest = _manifest(
            _option(
                "backend",
                default="local",
                setting="BACKEND",
                validation={"choices": ["local", "s3"]},
            ),
            _option("access_key_env_var", default="KEY", setting="KEY_ENV_VAR"),
        )
        manifest.mutable_options["access_key_env_var"].validation = {
            "required_when": {"backend": ["s3"]}
        }
        assert validate_module_options(manifest, {}) == []
        issues = validate_module_options(
            manifest, {"backend": "s3", "access_key_env_var": ""}
        )
        assert issues == [
            "KEY_ENV_VAR (modules.demo.access_key_env_var) is required when "
            "BACKEND (modules.demo.backend) is one of: s3"
        ]

    def test_any_of_requires_one_sibling(self) -> None:
        manifest = _manifest(
            _option("endpoint", setting="ENDPOINT", validation={"any_of": ["region"]}),
            _option("region", setting="REGION"),
        )
        issues = validate_module_options(manifest, {})
        assert issues == [
            "one of ENDPOINT (modules.demo.endpoint), "
            "REGION (modules.demo.region) is required"
        ]
        assert validate_module_options(manifest, {"region": "us-east-1"}) == []

    def test_any_of_gated_by_required_when(self) -> None:
        manifest = _manifest(
            _option(
                "target_mode",
                default="local",
                setting="TARGET_MODE",
                validation={"choices": ["local", "private_remote"]},
            ),
            _option(
                "endpoint",
                setting="ENDPOINT",
                validation={
                    "required_when": {"target_mode": "private_remote"},
                    "any_of": ["region"],
                },
            ),
            _option("region", setting="REGION"),
        )
        assert validate_module_options(manifest, {}) == []
        issues = validate_module_options(manifest, {"target_mode": "private_remote"})
        assert issues == [
            "one of ENDPOINT (modules.demo.endpoint), "
            "REGION (modules.demo.region) is required when TARGET_MODE "
            "(modules.demo.target_mode) is 'private_remote'"
        ]

    def test_undeclared_overrides_are_ignored(self) -> None:
        manifest = _manifest(
            _option("per_page", option_type="integer", default=1, setting="PER_PAGE")
        )
        assert validate_module_options(manifest, {"other": "value"}) == []

    def test_null_value_fails_the_declared_type(self) -> None:
        manifest = _manifest(
            _option(
                "enabled",
                option_type="boolean",
                default=True,
                setting="ENABLED",
            )
        )
        assert validate_module_options(manifest, {"enabled": None}) == [
            "ENABLED (modules.demo.enabled) must be a boolean"
        ]

    def test_declared_type_checks_the_supplied_value_before_coercion(self) -> None:
        manifest = _manifest(_option("bucket", default="", setting="BUCKET"))
        issues = validate_module_options(
            manifest, {"bucket": "123"}, supplied={"bucket": 123}
        )
        assert issues == ["BUCKET (modules.demo.bucket) must be a string"]

    def test_huge_integer_bound_does_not_overflow(self) -> None:
        manifest = _manifest(
            _option(
                "per_page",
                option_type="integer",
                default=1,
                setting="PER_PAGE",
                validation={"min": 1},
            )
        )
        assert validate_module_options(manifest, {"per_page": int("9" * 400)}) == []

    def test_immutable_option_without_setting_is_named_by_its_path(self) -> None:
        manifest = _manifest(
            _option(
                "authentication_method",
                default="email",
                validation={"choices": ["email", "username"]},
            )
        )
        issues = validate_module_options(manifest, {"authentication_method": "token"})
        assert issues == [
            "modules.demo.authentication_method must be one of: email, username"
        ]

    def test_collect_issues_carries_the_offending_option(self) -> None:
        manifest = _manifest(
            _option("per_page", option_type="integer", default=1, setting="PER_PAGE")
        )
        issues = collect_option_validation_issues(manifest, {"per_page": "x"})
        assert [issue.option_name for issue in issues] == ["per_page"]


class TestRetiredOptionRefusal:
    """A manifest declares retired keys with the message that refuses them."""

    def test_retired_key_is_reported_with_its_declared_message(self) -> None:
        manifest = _manifest(
            _option("per_page", option_type="integer", default=1, setting="PER_PAGE")
        )
        manifest.retired_options = {"default_pipeline_stages": "Retired: remove it."}
        issues = collect_option_validation_issues(
            manifest, {"default_pipeline_stages": ["lead"]}
        )
        assert [(issue.option_name, issue.message) for issue in issues] == [
            ("default_pipeline_stages", "Retired: remove it.")
        ]

    def test_retired_key_is_reported_before_declared_option_issues(self) -> None:
        manifest = _manifest(
            _option(
                "per_page",
                option_type="integer",
                default=1,
                setting="PER_PAGE",
                validation={"min": 1},
            )
        )
        manifest.retired_options = {"retired_key": "Retired: remove it."}
        issues = collect_option_validation_issues(
            manifest, {"retired_key": 1, "per_page": 0}
        )
        assert issues[0].option_name == "retired_key"

    def test_absent_retired_key_is_not_reported(self) -> None:
        manifest = _manifest()
        manifest.retired_options = {"retired_key": "Retired: remove it."}
        assert validate_module_options(manifest, {}) == []

    def test_shipped_crm_manifest_refuses_its_retired_key(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        manifest = load_manifest_from_path(
            repo_root / "quickscale_modules" / "crm" / "module.yml"
        )
        issues = collect_option_validation_issues(
            manifest, {"default_pipeline_stages": ["lead"]}
        )
        assert [issue.option_name for issue in issues] == ["default_pipeline_stages"]
        assert "no longer supported" in issues[0].message


class TestShippedManifestConformance:
    """Every shipped manifest conforms to the schema SA217 makes live."""

    @staticmethod
    def _manifest_paths() -> list[Path]:
        repo_root = Path(__file__).resolve().parents[2]
        modules_root = repo_root / "quickscale_modules"
        return sorted(modules_root.glob("*/module.yml"))

    def test_every_module_declares_a_validation_block_per_option(self) -> None:
        paths = self._manifest_paths()
        assert len(paths) == 12

        for path in paths:
            manifest = load_manifest_from_path(path)
            for name, option in manifest.get_all_options().items():
                assert isinstance(option.validation, dict), (
                    f"{manifest.name}.{name} has no validation block"
                )
                assert option.option_type, (
                    f"{manifest.name}.{name} has no declared type"
                )

    def test_shipped_defaults_satisfy_their_own_rules(self) -> None:
        for path in self._manifest_paths():
            manifest = load_manifest_from_path(path)
            assert validate_module_options(manifest, {}) == [], (
                f"{manifest.name} defaults violate its own manifest rules"
            )

    def test_no_one_to_one_derived_settings_remain(self) -> None:
        """A mutable option's django_setting is its only one-to-one projection."""
        for path in self._manifest_paths():
            manifest = load_manifest_from_path(path)
            for option_name, option in manifest.get_all_options().items():
                if not option.django_setting:
                    continue
                raw = manifest.option_derivations.get(option_name, {})
                for derived in raw.get("derived_settings", []):
                    if derived.get("derivation_type") != "direct":
                        continue
                    assert derived.get("setting_key") != option.django_setting, (
                        f"{manifest.name}.{option_name} repeats its django_setting "
                        f"in derived_settings"
                    )

    def test_listings_rule_lives_in_the_option_not_the_derivation(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        manifest = load_manifest_from_path(
            repo_root / "quickscale_modules" / "listings" / "module.yml"
        )
        option = manifest.get_option("listings_per_page")
        assert option is not None
        assert option.validation == {"min": 1}
        derivation = manifest.option_derivations.get("listings_per_page", {})
        assert derivation.get("validation_rules", []) == []
        assert derivation.get("derived_settings", []) == []


class TestPlanApplyEnforcement:
    """``validate_config`` — the plan/apply seam — fails with the setting name."""

    @staticmethod
    def _config(module_body: str) -> str:
        return (
            'version: "1"\n'
            "project:\n"
            "  slug: myproject\n"
            "  package: my_package\n"
            "  theme: showcase_react\n"
            "modules:\n"
            f"{module_body}"
        )

    def test_wrong_type_fails_with_the_setting_name(self) -> None:
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(
                self._config('  listings:\n    listings_per_page: "twelve"\n')
            )
        assert "LISTINGS_PER_PAGE" in str(exc_info.value)

    def test_violated_range_fails_with_the_setting_name(self) -> None:
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(self._config("  listings:\n    listings_per_page: 0\n"))
        assert "LISTINGS_PER_PAGE" in str(exc_info.value)

    def test_violated_required_when_fails_with_the_setting_name(self) -> None:
        body = (
            "  backups:\n"
            "    target_mode: private_remote\n"
            "    remote_access_key_id_env_var: REMOTE_KEY\n"
            "    remote_secret_access_key_env_var: REMOTE_SECRET\n"
            "    remote_region_name: us-east-1\n"
        )
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(self._config(body))
        assert "QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME" in str(exc_info.value)

    def test_retired_option_fails_with_its_declared_message(self) -> None:
        body = "  crm:\n    default_pipeline_stages:\n      - lead\n"
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(self._config(body))
        assert "default_pipeline_stages" in str(exc_info.value)
        assert "no longer supported" in str(exc_info.value)

    def test_valid_options_pass(self) -> None:
        config = validate_config(
            self._config("  listings:\n    listings_per_page: 24\n")
        )
        assert config.modules["listings"].options["listings_per_page"] == 24

    def test_null_value_fails_with_the_setting_name(self) -> None:
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(self._config("  analytics:\n    enabled: null\n"))
        assert "QUICKSCALE_ANALYTICS_ENABLED" in str(exc_info.value)

    def test_supplied_type_is_checked_before_canonicalization(self) -> None:
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(self._config("  storage:\n    bucket_name: 123\n"))
        assert "AWS_STORAGE_BUCKET_NAME" in str(exc_info.value)

    def test_auth_wrong_type_names_the_setting(self) -> None:
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(self._config('  auth:\n    registration_enabled: "true"\n'))
        assert "ACCOUNT_ALLOW_REGISTRATION" in str(exc_info.value)

    def test_billing_wrong_type_names_the_setting(self) -> None:
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(self._config('  billing:\n    enabled: "true"\n'))
        assert "QUICKSCALE_BILLING_ENABLED" in str(exc_info.value)

    def test_canonicalizable_values_pass(self) -> None:
        config = validate_config(self._config("  orgs:\n    mode: SAAS\n"))
        assert config.modules["orgs"].options["mode"] == "SAAS"

    def test_canonicalized_backups_private_remote_passes(self) -> None:
        body = (
            "  backups:\n"
            "    target_mode: PRIVATE_REMOTE\n"
            "    remote_bucket_name: bucket\n"
            "    remote_access_key_id_env_var: REMOTE_KEY\n"
            "    remote_secret_access_key_env_var: REMOTE_SECRET\n"
            "    remote_region_name: us-east-1\n"
        )
        validate_config(self._config(body))

    def test_stripped_rate_limit_passes(self) -> None:
        validate_config(self._config("  blog:\n    api_rate_limit: ' 5/hour '\n"))
