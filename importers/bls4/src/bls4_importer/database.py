"""Transactional writes for BLS 4.0 records."""

import psycopg
from psycopg.rows import dict_row

from bls4_importer.source import NUTRIENTS, SOURCE_NAME, Food

# Column names come from the fixed NUTRIENTS mapping, never from input.
NUTRIENT_COLUMNS = ", ".join(NUTRIENTS)
NUTRIENT_PLACEHOLDERS = ", ".join(f"%({column})s" for column in NUTRIENTS)
NUTRIENT_ASSIGNMENTS = ", ".join(f"{column} = %({column})s" for column in NUTRIENTS)


def write_foods(database_url: str, foods: list[Food]) -> tuple[int, int, int]:
    created = updated = skipped = 0
    with (
        psycopg.connect(database_url, row_factory=dict_row) as connection,
        connection.transaction(),
    ):
        connection.execute("SELECT pg_advisory_xact_lock(hashtext('health:bls4-import')::bigint)")
        stored_other: dict[str, dict] = {}
        for row in connection.execute(
            """SELECT s.external_id, n.nutrient_key, n.amount
               FROM food_source_nutrients n JOIN food_sources s ON s.id = n.source_id
               WHERE s.source_name = %s""",
            (SOURCE_NAME,),
        ):
            stored_other.setdefault(row["external_id"], {})[row["nutrient_key"]] = row["amount"]
        # Sources whose food_source_nutrients rows are replaced after the loop.
        other_rows: dict[int, dict] = {}
        for food in foods:
            other = {key: value for key, value in food.other_nutrients.items() if value is not None}
            values = {
                "food_name": food.german_name,
                "group_code": food.code[0],
                **food.nutrients,
            }
            rows = connection.execute(
                f"""SELECT s.id, f.id AS food_id, s.food_name, s.group_code,
                          s.reference_quantity, s.reference_unit, s.upper_bounds,
                          {NUTRIENT_COLUMNS}, f.kind, f.preparation_state
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
                    old["reference_quantity"] == 100
                    and old["reference_unit"] == "g"
                    and old["upper_bounds"] == []
                    and all(old[column] == value for column, value in values.items())
                )
                other_changed = stored_other.get(food.code, {}) != other
                # Fill a missing state; never overwrite a state someone set.
                add_state = old["preparation_state"] is None and food.preparation_state
                if unchanged and not other_changed and not add_state and old["kind"] == "generic":
                    skipped += 1
                    continue
                if old["kind"] != "generic":
                    connection.execute(
                        "UPDATE foods SET kind = 'generic' WHERE id = %s", (old["food_id"],)
                    )
                if add_state:
                    connection.execute(
                        "UPDATE foods SET preparation_state = %s WHERE id = %s",
                        (food.preparation_state, old["food_id"]),
                    )
                if other_changed:
                    other_rows[old["id"]] = other
                if not unchanged:
                    connection.execute(
                        f"""UPDATE food_sources
                           SET food_name = %(food_name)s, group_code = %(group_code)s,
                               reference_quantity = 100, reference_unit = 'g',
                               upper_bounds = '{{}}', {NUTRIENT_ASSIGNMENTS}
                           WHERE id = %(id)s""",
                        {**values, "id": old["id"]},
                    )
                updated += 1
                continue

            slug = f"bls4-{food.code.lower()}"
            if connection.execute("SELECT 1 FROM foods WHERE slug = %s", (slug,)).fetchone():
                raise ValueError(f"food slug {slug} already exists without its BLS source")
            aliases = [] if food.german_name == food.english_name else [food.german_name]
            food_id = connection.execute(
                """INSERT INTO foods (slug, name, aliases, kind, preparation_state)
                   VALUES (%s, %s, %s, 'generic', %s) RETURNING id""",
                (slug, food.english_name, aliases, food.preparation_state),
            ).fetchone()["id"]
            source_id = connection.execute(
                f"""INSERT INTO food_sources
                       (food_id, source_name, external_id, food_name, group_code,
                        reference_quantity, reference_unit, {NUTRIENT_COLUMNS})
                   VALUES (%(food_id)s, %(source_name)s, %(external_id)s, %(food_name)s,
                           %(group_code)s, 100, 'g', {NUTRIENT_PLACEHOLDERS})
                   RETURNING id""",
                {
                    **values,
                    "food_id": food_id,
                    "source_name": SOURCE_NAME,
                    "external_id": food.code,
                },
            ).fetchone()["id"]
            other_rows[source_id] = other
            created += 1
        write_other_nutrients(connection, other_rows)
        if created or updated:
            refresh_search(connection)
    return created, updated, skipped


def write_other_nutrients(connection: psycopg.Connection, rows: dict[int, dict]) -> None:
    """Replace the food_source_nutrients rows of the given sources in bulk."""
    if not rows:
        return
    connection.execute("DELETE FROM food_source_nutrients WHERE source_id = ANY(%s)", (list(rows),))
    with connection.cursor().copy(
        "COPY food_source_nutrients (source_id, nutrient_key, amount) FROM STDIN"
    ) as copy:
        for source_id, nutrients in rows.items():
            for key, amount in nutrients.items():
                copy.write_row((source_id, key, amount))


def refresh_search(connection: psycopg.Connection) -> None:
    """Rebuild the catalog search views from the committed food names."""
    connection.execute("REFRESH MATERIALIZED VIEW food_search_terms")
    connection.execute("REFRESH MATERIALIZED VIEW food_search_vocabulary")
