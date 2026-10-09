import os
import shutil
from pathlib import Path

import psycopg
import pytest
from health_api.migrate import migrate
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

SCHEMA = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


@pytest.fixture
def scratch_database(tmp_path):
    """A new empty database and a db directory with the real baseline."""
    base = os.environ.get("TEST_DATABASE_URL")
    if not base:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    name = f"health_migrate_{os.getpid()}_{tmp_path.name[-8:]}"
    admin = make_conninfo(base, dbname="postgres")
    with psycopg.connect(admin, autocommit=True) as connection:
        connection.execute(f'CREATE DATABASE "{name}"')
    directory = tmp_path / "db"
    (directory / "migrations").mkdir(parents=True)
    shutil.copy(SCHEMA, directory / "schema.sql")
    try:
        yield make_conninfo(base, dbname=name), directory
    finally:
        with psycopg.connect(admin, autocommit=True) as connection:
            connection.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def run(url: str, directory: Path) -> list[str]:
    with psycopg.connect(url, row_factory=dict_row) as connection:
        return migrate(connection, directory)


def table_exists(url: str, name: str) -> bool:
    with psycopg.connect(url, row_factory=dict_row) as connection:
        return connection.execute("SELECT to_regclass(%s) IS NOT NULL AS f", (name,)).fetchone()[
            "f"
        ]


def test_new_database_gets_baseline_then_migrations_once(scratch_database):
    url, directory = scratch_database
    (directory / "migrations" / "0001_marker.sql").write_text(
        "CREATE TABLE migration_marker (id int);"
    )
    assert run(url, directory) == ["baseline", "0001_marker.sql"]
    assert table_exists(url, "migration_marker")
    assert table_exists(url, "catalog.foods")
    assert run(url, directory) == []


def test_existing_database_records_current_migrations_without_running_them(scratch_database):
    url, directory = scratch_database
    # A database as it was before the runner: the baseline, no tracking table.
    with psycopg.connect(url) as connection:
        connection.execute(SCHEMA.read_text(encoding="utf-8"))
    (directory / "migrations" / "0001_marker.sql").write_text(
        "CREATE TABLE migration_marker (id int);"
    )
    assert run(url, directory) == ["recorded 0001_marker.sql"]
    assert not table_exists(url, "migration_marker")
    assert run(url, directory) == []


def test_new_migration_runs_on_a_tracked_database(scratch_database):
    url, directory = scratch_database
    assert run(url, directory) == ["baseline"]
    (directory / "migrations" / "0002_second.sql").write_text(
        "CREATE TABLE second_marker (id int);"
    )
    assert run(url, directory) == ["0002_second.sql"]
    assert table_exists(url, "second_marker")


def test_failing_migration_rolls_back_and_is_not_recorded(scratch_database):
    url, directory = scratch_database
    assert run(url, directory) == ["baseline"]
    (directory / "migrations" / "0003_broken.sql").write_text(
        "CREATE TABLE half_done (id int); SELECT no_such_function();"
    )
    with pytest.raises(psycopg.Error):
        run(url, directory)
    assert not table_exists(url, "half_done")
    with psycopg.connect(url, row_factory=dict_row) as connection:
        names = [row["name"] for row in connection.execute("SELECT name FROM schema_migrations")]
    assert "0003_broken.sql" not in names
