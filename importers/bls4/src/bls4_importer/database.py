"""Transactional writes for BLS 4.0 records."""

import psycopg
from psycopg.rows import dict_row

from bls4_importer.source import SOURCE_NAME, Food


def write_foods(database_url: str, foods: list[Food]) -> tuple[int, int, int]:
    created = updated = skipped = 0
    with (
        psycopg.connect(database_url, row_factory=dict_row) as connection,
        connection.transaction(),
    ):
        connection.execute("SELECT pg_advisory_xact_lock(hashtext('health:bls4-import')::bigint)")
        for food in foods:
            rows = connection.execute(
                """SELECT s.id, f.id AS food_id, s.food_name, s.group_code,
                          s.reference_quantity, s.reference_unit,
                          s.energy_kcal, s.protein_g, s.fat_g, s.carbs_g, s.fiber_g, f.kind
                   FROM food_sources s JOIN foods f ON f.id = s.food_id
                   WHERE s.source_name = %s AND s.external_id = %s""",
                (SOURCE_NAME, food.code),
            ).fetchall()
            if len(rows) > 1:
                raise ValueError(f"duplicate {SOURCE_NAME} source records for {food.code}")
            if rows:
                old = rows[0]
                if old["kind"] not in ("ingredient", "generic"):
                    raise ValueError(f"BLS source {food.code} belongs to a non-generic food")
                unchanged = (
                    old["food_name"] == food.german_name
                    and old["group_code"] == food.code[0]
                    and old["reference_quantity"] == 100
                    and old["reference_unit"] == "g"
                    and all(
                        old[column] == value
                        for column, value in (
                            ("energy_kcal", food.energy),
                            ("protein_g", food.protein),
                            ("fat_g", food.fat),
                            ("carbs_g", food.carbs),
                            ("fiber_g", food.fiber),
                        )
                    )
                )
                if unchanged and old["kind"] == "generic":
                    skipped += 1
                    continue
                if old["kind"] != "generic":
                    connection.execute(
                        "UPDATE foods SET kind = 'generic' WHERE id = %s", (old["food_id"],)
                    )
                if not unchanged:
                    connection.execute(
                        """UPDATE food_sources
                           SET food_name = %s, group_code = %s,
                               reference_quantity = 100, reference_unit = 'g',
                               energy_kcal = %s, protein_g = %s, fat_g = %s, carbs_g = %s, fiber_g = %s
                           WHERE id = %s""",
                        (
                            food.german_name,
                            food.code[0],
                            food.energy,
                            food.protein,
                            food.fat,
                            food.carbs,
                            food.fiber,
                            old["id"],
                        ),
                    )
                updated += 1
                continue

            slug = f"bls4-{food.code.lower()}"
            if connection.execute("SELECT 1 FROM foods WHERE slug = %s", (slug,)).fetchone():
                raise ValueError(f"food slug {slug} already exists without its BLS source")
            aliases = [] if food.german_name == food.english_name else [food.german_name]
            food_id = connection.execute(
                """INSERT INTO foods (slug, name, aliases, kind)
                   VALUES (%s, %s, %s, 'generic') RETURNING id""",
                (slug, food.english_name, aliases),
            ).fetchone()["id"]
            connection.execute(
                """INSERT INTO food_sources
                           (food_id, source_name, external_id, food_name, group_code, reference_quantity,
                            reference_unit, energy_kcal, protein_g, fat_g, carbs_g, fiber_g)
                       VALUES (%s, %s, %s, %s, %s, 100, 'g', %s, %s, %s, %s, %s)""",
                (
                    food_id,
                    SOURCE_NAME,
                    food.code,
                    food.german_name,
                    food.code[0],
                    food.energy,
                    food.protein,
                    food.fat,
                    food.carbs,
                    food.fiber,
                ),
            )
            created += 1
    return created, updated, skipped
