"""Presence guards, deferred aliases, and absolute-URL boundary parity."""

from __future__ import annotations

import copy
import ipaddress
import re
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from quickscale_core.manifest.derivation import build_schema_from_manifest
from quickscale_core.manifest.entry_point import (
    MANIFEST_ADAPTER_REGISTRY,
    build_generic_manifest_spec,
    build_manifest_wiring_spec,
    load_managed_adapter_module,
    load_module_manifest,
)
from quickscale_core.manifest.loader import ManifestError, load_manifest
from quickscale_core.manifest.option_validation import validate_module_options
from quickscale_core.manifest.resolver import resolve_module_config


@pytest.mark.parametrize(
    ("module", "option"),
    [
        ("storage", "public_base_url"),
        ("storage", "endpoint_url"),
        ("backups", "remote_endpoint_url"),
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        "bad host",
        "https://",
        "https://host\npath",
        "https://host:bad",
        "https://host\\bad",
        "http://[::::]:9000/",
        "http://[::gg]:9000/",
        "http://[::1:9000/",
        "http://[::1]:bad/",
        "http://[1:2:3:4:5:6:7:8:9]/",
        "http://[1:2:3:4:5:6::192.0.2.1]/",
        "http://[1:2:3:4:5::6:192.0.2.1]/",
        "http://[::ffff:999.0.2.1]/",
    ],
)
def test_optional_absolute_urls_fail_at_config_and_wiring(
    module, option, value
) -> None:
    manifest = load_module_manifest(module)
    supplied = {option: value}
    assert any(option in issue for issue in validate_module_options(manifest, supplied))
    with pytest.raises(ManifestError, match=option):
        build_generic_manifest_spec(module, supplied)


@pytest.mark.parametrize(
    ("module", "option"),
    [
        ("storage", "public_base_url"),
        ("storage", "endpoint_url"),
        ("backups", "remote_endpoint_url"),
    ],
)
@pytest.mark.parametrize(
    "value", ["", "  ", "example.com/path/", "//localhost:9000/", " https://r2/path/ "]
)
def test_optional_absolute_urls_keep_blank_and_schemeless_spellings(
    module, option, value
) -> None:
    assert validate_module_options(load_module_manifest(module), {option: value}) == []
    build_generic_manifest_spec(module, {option: value})


@pytest.mark.parametrize(
    ("module", "option", "setting"),
    [
        ("storage", "public_base_url", "QUICKSCALE_STORAGE_PUBLIC_BASE_URL"),
        ("storage", "endpoint_url", "AWS_S3_ENDPOINT_URL"),
        ("backups", "remote_endpoint_url", "QUICKSCALE_BACKUPS_REMOTE_ENDPOINT_URL"),
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        "http://[::1]:9000/",
        "https://[2001:db8::1]/",
        "http://[2001:db8:0:1:2:3:4:5]:80/path/",
        "https://[::]/",
        "http://[::ffff:192.0.2.1]:9000/",
        "http://[1:2::3:192.0.2.1]/",
        "https://[1:2:3:4:5:6:192.0.2.1]/",
    ],
)
def test_ipv6_urls_keep_config_generic_adapter_and_snapshot_parity(
    monkeypatch, module, option, setting, value
) -> None:
    root = Path(__file__).resolve().parents[2]
    canonical = root / "quickscale_modules" / module / "module.yml"
    bundled = (
        root
        / "quickscale_core/src/quickscale_core/data/manifests"
        / module
        / "module.yml"
    )
    assert canonical.read_bytes() == bundled.read_bytes()
    supplied = {option: value}
    if module == "storage":
        supplied["backend"] = "s3"
    manifest = load_module_manifest(module)
    assert validate_module_options(manifest, supplied) == []
    assert validate_module_options(load_manifest(bundled.read_text()), supplied) == []
    adapter = load_managed_adapter_module(module).get_manifest_adapter()
    monkeypatch.setitem(MANIFEST_ADAPTER_REGISTRY, module, adapter)
    for spec in (
        build_generic_manifest_spec(module, supplied),
        adapter(supplied),
        build_manifest_wiring_spec(module, supplied),
    ):
        assert spec.settings[setting] == value.rstrip("/")


def test_ipv6_pattern_agrees_with_address_parser_across_compression_positions() -> None:
    manifest = load_module_manifest("storage")
    pattern = manifest.mutable_options["endpoint_url"].validation["pattern"]
    for dotted in (False, True):
        for before in range(9):
            for after in range(9):
                prefix = ":".join(["abcd"] * before)
                suffix = ":".join(["1234"] * after + (["192.0.2.1"] if dotted else []))
                address = prefix + "::" + suffix
                try:
                    ipaddress.IPv6Address(address)
                    valid = True
                except ipaddress.AddressValueError:
                    valid = False
                assert (
                    bool(re.fullmatch(pattern, f"http://[{address}]:9000/path"))
                    == valid
                ), address


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"enabled": False},
        {
            "sender_name": "Ops",
            "sender_email": "ops@example.com",
            "resend_domain": "mg.example.com",
        },
    ],
)
def test_notification_query_and_wiring_selection_still_agree(options) -> None:
    module = load_managed_adapter_module("notifications")
    spec = module.get_manifest_adapter()(options)
    selected = module.notifications_runtime_email_backend(options)
    assert spec.settings["EMAIL_BACKEND"] == (
        selected or module.NOTIFICATIONS_CONSOLE_EMAIL_BACKEND
    )
    assert module.notifications_production_targeted(options) == bool(
        options.get("resend_domain")
    )
    assert module.notifications_live_delivery_configured(options) == bool(
        options.get("resend_domain")
    )


@pytest.mark.parametrize("backend", ["s3", "local", "r2", "s3"])
def test_manifest_owns_cloud_aliases_across_generic_adapter_and_registry(
    monkeypatch, backend
) -> None:
    adapter = load_managed_adapter_module("storage").get_manifest_adapter()
    monkeypatch.setitem(MANIFEST_ADAPTER_REGISTRY, "storage", adapter)
    options = {
        "backend": backend,
        "access_key_id_env_var": "OPERATOR_ACCESS",
        "secret_access_key_env_var": "OPERATOR_SECRET",
    }
    with patch(
        "os.environ.get", side_effect=AssertionError("apply must not read secrets")
    ):
        generic = build_generic_manifest_spec("storage", options)
        owned = adapter(options)
        registered = build_manifest_wiring_spec("storage", options)
    for key, source in (
        ("AWS_ACCESS_KEY_ID", "OPERATOR_ACCESS"),
        ("AWS_SECRET_ACCESS_KEY", "OPERATOR_SECRET"),
    ):
        if backend == "local":
            assert all(
                key not in spec.settings for spec in (generic, owned, registered)
            )
        else:
            assert all(
                spec.settings[key] == f"__QS_ENV__:{source}"
                for spec in (generic, owned, registered)
            )
    assert owned == registered


def test_alias_removal_and_optional_blanks_are_governed_by_manifest() -> None:
    manifest = load_module_manifest("storage")
    # Optional credentials are a supported generic projection state even when
    # this loaded declaration's required_when guard refuses a blank cloud input.
    schema = build_schema_from_manifest(
        "storage",
        derived_settings=manifest.derived_settings,
        option_derivations=manifest.option_derivations,
    )
    options = {
        "backend": "s3",
        "access_key_id_env_var": "",
        "secret_access_key_env_var": "",
    }
    result = resolve_module_config(manifest, schema, options)
    assert "AWS_ACCESS_KEY_ID" not in result.derived_settings
    assert "AWS_SECRET_ACCESS_KEY" not in result.derived_settings
    optional = dict(manifest.mutable_options)
    for key in ("access_key_id_env_var", "secret_access_key_env_var"):
        validation = dict(optional[key].validation)
        del validation["required_when"]
        optional[key] = replace(optional[key], validation=validation)
    optional_manifest = replace(manifest, mutable_options=optional)
    adapter = load_managed_adapter_module("storage").get_manifest_adapter()
    with patch(
        "quickscale_core.manifest.entry_point.load_module_manifest",
        return_value=optional_manifest,
    ):
        assert "AWS_ACCESS_KEY_ID" not in adapter(options).settings
        assert "AWS_SECRET_ACCESS_KEY" not in adapter(options).settings
    removed = replace(
        manifest,
        derived_settings=[
            entry
            for entry in manifest.derived_settings
            if not entry["setting_key"].startswith("AWS_")
        ],
    )
    with patch(
        "quickscale_core.manifest.entry_point.load_module_manifest",
        return_value=removed,
    ):
        assert "AWS_ACCESS_KEY_ID" not in adapter({"backend": "s3"}).settings
        assert "AWS_SECRET_ACCESS_KEY" not in adapter({"backend": "s3"}).settings


@pytest.mark.parametrize(
    "guard",
    [
        {"when": []},
        {"when": {}},
        {"when": {"missing": ["s3"]}},
        {"when": {"backend": "s3"}},
        {"when": {"backend": [True]}},
        {"omit_if_blank": "backend"},
        {"omit_if_blank": []},
        {"omit_if_blank": ["missing"]},
        {"omit_if_blank": ["enabled"]},
    ],
)
def test_presence_guards_fail_closed_at_loader(guard) -> None:
    path = Path(__file__).resolve().parents[2] / "quickscale_modules/storage/module.yml"
    raw = yaml.safe_load(path.read_text())
    entry = next(
        item
        for item in raw["derivation"]["derived_settings"]
        if item["setting_key"] == "AWS_ACCESS_KEY_ID"
    )
    entry["expression"] = {"template": "__QS_ENV__:{access_key_id_env_var}", **guard}
    with pytest.raises(ManifestError, match="expression"):
        load_manifest(yaml.safe_dump(raw))


def test_presence_guards_are_generic_and_require_all_conditions() -> None:
    path = Path(__file__).resolve().parents[2] / "quickscale_modules/storage/module.yml"
    raw = yaml.safe_load(path.read_text())
    raw["name"] = "demo"
    entry = copy.deepcopy(
        next(
            item
            for item in raw["derivation"]["derived_settings"]
            if item["setting_key"] == "AWS_ACCESS_KEY_ID"
        )
    )
    entry["setting_key"] = "DEMO_ALIAS"
    entry["expression"]["when"]["enabled"] = [True]
    raw["derivation"]["derived_settings"] = [entry]
    manifest = load_manifest(yaml.safe_dump(raw))
    schema = build_schema_from_manifest(
        "demo", derived_settings=manifest.derived_settings
    )
    for backend, enabled, present in [
        ("s3", True, True),
        ("local", True, False),
        ("s3", False, False),
        ("r2", True, True),
    ]:
        result = resolve_module_config(
            manifest, schema, {"backend": backend, "enabled": enabled}
        )
        assert ("DEMO_ALIAS" in result.derived_settings) is present
