"""Apply db/migrations/*.sql in name order, each once and in its own transaction.

db/schema.sql is the frozen baseline a new database starts from; every later
change is a new, never-edited migration file.
"""

import argparse
import os
import sys
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "db/migrations"
DEFAULT_DATABASE_URL = "postgres://health:health@127.0.0.1:5432/health"


def pending(connection: psycopg.Connection, directory: Path = MIGRATIONS_DIR) -> list[Path]:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               name text PRIMARY KEY,
               applied_at timestamptz NOT NULL DEFAULT now()
           )"""
    )
    applied = {row[0] for row in connection.execute("SELECT name FROM schema_migrations")}
    return [path for path in sorted(directory.glob("*.sql")) if path.name not in applied]


def migrate(
    database_url: str, directory: Path = MIGRATIONS_DIR, dry_run: bool = False
) -> list[str]:
    with psycopg.connect(database_url, autocommit=True) as connection:
        # One migrator at a time; the lock ends with the session.
        connection.execute("SELECT pg_advisory_lock(hashtext('health:migrate')::bigint)")
        paths = pending(connection, directory)
        if not dry_run:
            for path in paths:
                with connection.transaction():
                    connection.execute(path.read_text(encoding="utf-8"))
                    connection.execute(
                        "INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,)
                    )
    return [path.name for path in paths]


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply pending database migrations")
    parser.add_argument("--dry-run", action="store_true", help="list pending migrations only")
    options = parser.parse_args()
    try:
        names = migrate(
            os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL), dry_run=options.dry_run
        )
    except (OSError, psycopg.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    verb = "pending" if options.dry_run else "applied"
    print("\n".join(f"{verb}: {name}" for name in names) or "database is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
