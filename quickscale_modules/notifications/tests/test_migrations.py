"""Fresh-initial contract tests for the notifications module migrations.

The module ships one consolidated ``0001_initial`` (clean-break history);
these tests prove that single migration reproduces today's models and
installs the module's tables.
"""

from __future__ import annotations

import pytest
from django.apps import apps as django_apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.models import Model

pytestmark = [
    pytest.mark.bypass_rls,
    pytest.mark.django_db(transaction=True),
]

APP_LABEL = "quickscale_notifications"
MIG_0001 = (APP_LABEL, "0001_initial")


def _shipped_models() -> list[type[Model]]:
    """Return the module's shipped models, excluding test-only models."""
    return [
        model
        for model in django_apps.get_app_config(APP_LABEL).get_models()
        if "tests" not in model.__module__.split(".")
    ]


def test_module_ships_exactly_one_initial_migration() -> None:
    """The clean-break history holds one ``0001_initial`` and nothing else."""
    loader = MigrationLoader(connection=connection, ignore_no_migrations=True)
    names = sorted(
        name for (app_label, name) in loader.disk_migrations if app_label == APP_LABEL
    )
    assert names == ["0001_initial"]


def test_fresh_initial_reproduces_the_current_models() -> None:
    """Every model's fields, table, ordering, constraints, and indexes match."""
    executor = MigrationExecutor(connection)
    executor.migrate([MIG_0001])
    historical_apps = executor.loader.project_state([MIG_0001]).apps

    current_models = _shipped_models()
    assert current_models, "the module must expose at least one shipped model"

    historical_names = {
        model.__name__
        for model in historical_apps.get_models()
        if model._meta.app_label == APP_LABEL
    }
    assert historical_names == {model.__name__ for model in current_models}, (
        "the initial migration and the shipped models disagree on the model set"
    )

    for model in current_models:
        historical = historical_apps.get_model(APP_LABEL, model.__name__)
        assert historical is not None, (
            f"{model.__name__} missing from the initial state"
        )

        assert {field.name for field in historical._meta.local_fields} == {
            field.name for field in model._meta.local_fields
        }, f"{model.__name__} fields drift from the initial migration"
        for field in model._meta.local_fields:
            historical_field = historical._meta.get_field(field.name)
            assert historical_field.deconstruct() == field.deconstruct(), (
                f"{model.__name__}.{field.name} differs from the initial migration"
            )

        assert {field.name for field in historical._meta.local_many_to_many} == {
            field.name for field in model._meta.local_many_to_many
        }, f"{model.__name__} many-to-many fields drift from the initial migration"
        for field in model._meta.local_many_to_many:
            historical_field = historical._meta.get_field(field.name)
            assert historical_field.deconstruct() == field.deconstruct(), (
                f"{model.__name__}.{field.name} differs from the initial migration"
            )

        assert historical._meta.db_table == model._meta.db_table
        assert list(historical._meta.ordering or []) == list(model._meta.ordering or [])

        historical_constraints = {
            constraint.name: constraint for constraint in historical._meta.constraints
        }
        assert sorted(historical_constraints) == sorted(
            constraint.name for constraint in model._meta.constraints
        ), f"{model.__name__} constraints drift from the initial migration"
        for constraint in model._meta.constraints:
            assert (
                historical_constraints[constraint.name].deconstruct()
                == constraint.deconstruct()
            ), f"{model.__name__} constraint {constraint.name} differs"

        historical_indexes = {index.name: index for index in historical._meta.indexes}
        assert sorted(historical_indexes) == sorted(
            index.name for index in model._meta.indexes
        ), f"{model.__name__} indexes drift from the initial migration"
        for index in model._meta.indexes:
            assert (
                historical_indexes[index.name].deconstruct() == index.deconstruct()
            ), f"{model.__name__} index {index.name} differs"


def test_initial_produces_the_modules_tables() -> None:
    """Every current model's table exists in the test database."""
    expected = {model._meta.db_table for model in _shipped_models()}

    assert set(connection.introspection.table_names()) >= expected
