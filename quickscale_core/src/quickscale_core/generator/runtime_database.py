"""Single-source generated runtime database role contract."""

RUNTIME_DB_ROLE = "quickscale_runtime"
RUNTIME_DB_DEFAULT_PASSWORD = f"{RUNTIME_DB_ROLE}_password"

RUNTIME_DB_ROLE_ATTRIBUTES: tuple[str, ...] = (
    "LOGIN",
    "NOSUPERUSER",
    "NOBYPASSRLS",
    "NOCREATEDB",
    "NOCREATEROLE",
)

RUNTIME_DB_GRANT_STATEMENTS: tuple[str, ...] = (
    "GRANT CONNECT ON DATABASE {database} TO {role}",
    "GRANT USAGE ON SCHEMA public TO {role}",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}",
    "GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {role}",
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}",
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO {role}",
)


def _quote_identifier(identifier: str) -> str:
    """Quote a PostgreSQL identifier for generated literal SQL."""
    escaped_identifier = identifier.replace('"', '""')
    return f'"{escaped_identifier}"'


def render_runtime_db_grant_statements(
    *,
    role: str,
    database: str,
) -> tuple[str, ...]:
    """Render the canonical grants as literal SQL statements."""
    identifiers = {
        "role": _quote_identifier(role),
        "database": _quote_identifier(database),
    }
    return tuple(
        statement.format(**identifiers) for statement in RUNTIME_DB_GRANT_STATEMENTS
    )


def runtime_db_template_context(database: str) -> dict[str, object]:
    """Return the shared role contract in template-ready forms."""
    return {
        "runtime_db_role": RUNTIME_DB_ROLE,
        "runtime_db_password": RUNTIME_DB_DEFAULT_PASSWORD,
        "runtime_db_role_attributes": RUNTIME_DB_ROLE_ATTRIBUTES,
        "runtime_db_grant_statement_templates": RUNTIME_DB_GRANT_STATEMENTS,
        "runtime_db_init_grant_statements": render_runtime_db_grant_statements(
            role=RUNTIME_DB_ROLE,
            database=database,
        ),
        "runtime_db_manual_grant_statements": render_runtime_db_grant_statements(
            role=RUNTIME_DB_ROLE,
            database="<database>",
        ),
    }
