"""Database connection settings shared by all API modules."""

import os

import psycopg
from psycopg.rows import dict_row

DEFAULT_DATABASE_URL = "postgres://health:health@127.0.0.1:5432/health"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def connect() -> psycopg.Connection:
    """A new connection returning rows as dicts; use it as a context manager."""
    return psycopg.connect(database_url(), row_factory=dict_row)
