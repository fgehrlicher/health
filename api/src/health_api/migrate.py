"""Database migrations: the baseline schema, then numbered changes.

`db/schema.sql` is the baseline, the schema as it was when migrations began.
Every later change is a file in `db/migrations/`, named like
`0001_recipe_tags.sql`. Each file runs once, in order, in its own transaction,
and its name is recorded in `schema_migrations`.

A new, empty database gets the baseline, then every migration. A database that
already has the catalog but no `schema_migrations` table predates this runner:
its current migration files are recorded as applied without running them,
because their changes are already in it. That happens once, when the table is
first created.
"""

import os
import sys
from pathlib import Path

from psycopg import Connection

from health_api.db import connect


def db_dir() -> Path:
    """The `db/` folder: HEALTH_DB_DIR, or the repository's `db/`."""
    configured = os.environ.get("HEALTH_DB_DIR")
    return Path(configured) if configured else Path(__file__).resolve().parents[3] / "db"


def migration_files(directory: Path) -> list[Path]:
    return sorted((directory / "migrations").glob("*.sql"))


def exists(connection: Connection, name: str) -> bool:
    return connection.execute("SELECT to_regclass(%s) IS NOT NULL AS found", (name,)).fetchone()[
        "found"
    ]


def migrate(connection: Connection, directory: Path) -> list[str]:
    """Apply pending migrations; returns what was applied or recorded, in order."""
    had_catalog = exists(connection, "catalog.foods")
    had_tracking = exists(connection, "schema_migrations")
    done: list[str] = []

    if not had_catalog:
        with connection.transaction():
            connection.execute((directory / "schema.sql").read_text(encoding="utf-8"))
        done.append("baseline")

    connection.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               name text PRIMARY KEY,
               applied_at timestamptz NOT NULL DEFAULT now()
           )"""
    )
    recorded = {row["name"] for row in connection.execute("SELECT name FROM schema_migrations")}
    files = migration_files(directory)

    if had_catalog and not had_tracking:
        for path in files:
            connection.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
            done.append(f"recorded {path.name}")
        return done

    for path in files:
        if path.name in recorded:
            continue
        with connection.transaction():
            connection.execute(path.read_text(encoding="utf-8"))
            connection.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
        done.append(path.name)
    return done


def main() -> int:
    with connect() as connection:
        applied = migrate(connection, db_dir())
    print("\n".join(applied) if applied else "database is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
