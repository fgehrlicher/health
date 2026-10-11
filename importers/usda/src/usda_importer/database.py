"""Transactional writes for USDA FoodData Central foods.

Each FDC ID becomes one generic food with one USDA source. Its nutrients and
portions are replaced on every run, so reruns are idempotent. A food's names,
aliases and preparation state are set when it is created and never overwritten.
"""

import psycopg
from psycopg.rows import dict_row

from usda_importer.source import LABEL_COLUMNS, OTHER, SOURCE_NAME, Food

LABEL_NAMES = ", ".join(LABEL_COLUMNS)
LABEL_PLACEHOLDERS = ", ".join(f"%({column})s" for column in LABEL_COLUMNS)
LABEL_ASSIGNMENTS = ", ".join(f"{column} = %({column})s" for column in LABEL_COLUMNS)


def slug_for(fdc_id: int) -> str:
    return f"usda-{fdc_id}"


def check_catalog_units(connection: psycopg.Connection) -> None:
    """The catalog's nutrient units must be the ones the mapping was written for."""
    stored = {
        row["key"]: row["unit"]
        for row in connection.execute("SELECT key, unit FROM catalog.nutrients")
    }
    for key, (_numbers, _usda_unit, expected) in OTHER.items():
        if stored.get(key) != expected:
            raise ValueError(
                f"catalog nutrient {key} is in {stored.get(key)!r}, expected {expected!r}"
            )


def write_foods(database_url: str, foods: list[Food]) -> tuple[int, int]:
    """Create or update the foods; returns (created, updated)."""
    created = updated = 0
    with (
        psycopg.connect(database_url, row_factory=dict_row) as connection,
        connection.transaction(),
    ):
        connection.execute("SELECT pg_advisory_xact_lock(hashtext('health:usda-import')::bigint)")
        check_catalog_units(connection)
        for food in foods:
            values = {"food_name": food.description, **food.nutrients}
            existing = connection.execute(
                """SELECT s.id, s.food_id, f.kind FROM catalog.food_sources s
                   JOIN catalog.foods f ON f.id = s.food_id
                   WHERE s.source_name = %s AND s.external_id = %s""",
                (SOURCE_NAME, str(food.fdc_id)),
            ).fetchone()
            if existing:
                if existing["kind"] != "generic":
                    raise ValueError(f"USDA source {food.fdc_id} belongs to a non-generic food")
                source_id, food_id = existing["id"], existing["food_id"]
                connection.execute(
                    f"""UPDATE catalog.food_sources
                       SET food_name = %(food_name)s, reference_quantity = 100,
                           reference_unit = 'g', upper_bounds = '{{}}', {LABEL_ASSIGNMENTS}
                       WHERE id = %(id)s""",
                    {**values, "id": source_id},
                )
                updated += 1
            else:
                slug = slug_for(food.fdc_id)
                if connection.execute(
                    "SELECT 1 FROM catalog.foods WHERE slug = %s", (slug,)
                ).fetchone():
                    raise ValueError(f"food slug {slug} already exists without its USDA source")
                aliases = [food.german_name] if food.german_name else []
                food_id = connection.execute(
                    """INSERT INTO catalog.foods (slug, name, aliases, kind, preparation_state)
                       VALUES (%s, %s, %s, 'generic', %s) RETURNING id""",
                    (slug, food.description, aliases, food.preparation_state),
                ).fetchone()["id"]
                source_id = connection.execute(
                    f"""INSERT INTO catalog.food_sources
                           (food_id, source_name, external_id, food_name,
                            reference_quantity, reference_unit, {LABEL_NAMES})
                       VALUES (%(food_id)s, %(source_name)s, %(external_id)s, %(food_name)s,
                               100, 'g', {LABEL_PLACEHOLDERS})
                       RETURNING id""",
                    {
                        **values,
                        "food_id": food_id,
                        "source_name": SOURCE_NAME,
                        "external_id": str(food.fdc_id),
                    },
                ).fetchone()["id"]
                created += 1

            connection.execute(
                "DELETE FROM catalog.food_source_nutrients WHERE source_id = %s", (source_id,)
            )
            if food.other:
                with connection.cursor().copy(
                    "COPY catalog.food_source_nutrients (source_id, nutrient_key, amount) FROM STDIN"
                ) as copy:
                    for key, amount in food.other.items():
                        copy.write_row((source_id, key, amount))

            connection.execute("DELETE FROM catalog.food_portions WHERE food_id = %s", (food_id,))
            for portion in food.portions:
                connection.execute(
                    """INSERT INTO catalog.food_portions (food_id, name, kind, quantity, unit)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (food_id, portion.name, portion.kind, portion.quantity, portion.unit),
                )
        if created or updated:
            connection.execute("SELECT catalog.refresh_search()")
    return created, updated
