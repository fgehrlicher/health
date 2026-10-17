import os

import psycopg
import pytest


@pytest.fixture
def database_url():
    """The test database, put back as it was after the test.

    These tests import USDA foods and write German food group names. Left behind,
    they change what the catalog tests see on the next run against the same
    database: extra foods, and German group names in place of English ones.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    with psycopg.connect(url) as connection:
        foods = [row[0] for row in connection.execute("SELECT id FROM catalog.foods")]
        groups = connection.execute("SELECT name_de, code FROM catalog.food_groups").fetchall()
    yield url
    with psycopg.connect(url) as connection:
        # Sources, portions and nutrients go with their food (ON DELETE CASCADE).
        connection.execute("DELETE FROM catalog.foods WHERE NOT id = ANY(%s)", (foods,))
        with connection.cursor() as cursor:
            cursor.executemany(
                "UPDATE catalog.food_groups SET name_de = %s WHERE code = %s", groups
            )
        connection.execute("SELECT catalog.refresh_search()")
