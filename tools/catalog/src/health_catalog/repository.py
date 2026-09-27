"""Read-only queries for the food catalog."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from psycopg import Connection
from psycopg.rows import DictRow

Sort = Literal[
    "name",
    "name_desc",
    "group_asc",
    "group_desc",
    "code_asc",
    "code_desc",
    "source_asc",
    "source_desc",
    "energy_asc",
    "energy_desc",
    "protein_asc",
    "protein_desc",
    "protein_density_asc",
    "protein_density_desc",
    "fat_asc",
    "fat_desc",
    "carbs_asc",
    "carbs_desc",
    "fiber_asc",
    "fiber_desc",
]
SORT_SQL = {
    "name": "lower(name) ASC, id ASC",
    "name_desc": "lower(name) DESC, id ASC",
    "group_asc": "group_code ASC NULLS LAST, lower(name) ASC, id ASC",
    "group_desc": "group_code DESC NULLS LAST, lower(name) ASC, id ASC",
    "code_asc": "external_id ASC NULLS LAST, lower(name) ASC, id ASC",
    "code_desc": "external_id DESC NULLS LAST, lower(name) ASC, id ASC",
    "source_asc": "source_name ASC NULLS LAST, lower(name) ASC, id ASC",
    "source_desc": "source_name DESC NULLS LAST, lower(name) ASC, id ASC",
    "energy_asc": "energy_kcal ASC NULLS LAST, lower(name) ASC, id ASC",
    "energy_desc": "energy_kcal DESC NULLS LAST, lower(name) ASC, id ASC",
    "protein_asc": "protein_g ASC NULLS LAST, lower(name) ASC, id ASC",
    "protein_desc": "protein_g DESC NULLS LAST, lower(name) ASC, id ASC",
    "protein_density_asc": "protein_per_100_kcal ASC NULLS LAST, lower(name) ASC, id ASC",
    "protein_density_desc": "protein_per_100_kcal DESC NULLS LAST, lower(name) ASC, id ASC",
    "fat_asc": "fat_g ASC NULLS LAST, lower(name) ASC, id ASC",
    "fat_desc": "fat_g DESC NULLS LAST, lower(name) ASC, id ASC",
    "carbs_asc": "carbs_g ASC NULLS LAST, lower(name) ASC, id ASC",
    "carbs_desc": "carbs_g DESC NULLS LAST, lower(name) ASC, id ASC",
    "fiber_asc": "fiber_g ASC NULLS LAST, lower(name) ASC, id ASC",
    "fiber_desc": "fiber_g DESC NULLS LAST, lower(name) ASC, id ASC",
}
NUTRIENTS = ("energy_kcal", "protein_g", "fat_g", "carbs_g", "fiber_g")
BLS_GROUP_NAMES = {
    "B": "Bread",
    "C": "Cereals and grains",
    "D": "Cakes and baked goods",
    "E": "Eggs and pasta",
    "F": "Fruit",
    "G": "Vegetables",
    "H": "Legumes, nuts and seeds",
    "K": "Potatoes and mushrooms",
    "M": "Dairy",
    "N": "Nonalcoholic drinks",
    "P": "Alcoholic drinks",
    "Q": "Fats and oils",
    "R": "Seasonings and sauces",
    "S": "Sweets",
    "T": "Fish and seafood",
    "U": "Red meat",
    "V": "Poultry and game",
    "W": "Meat products",
    "X": "Mostly plant dishes",
    "Y": "Mostly animal dishes",
}

BASE_SQL = """
SELECT
    f.id, f.slug, f.name, f.aliases, f.kind, f.preparation_state, f.brand, f.barcode,
    (SELECT count(*) FROM food_sources s WHERE s.food_id = f.id) AS source_count,
    chosen.id AS source_id, chosen.source_name, chosen.external_id, chosen.group_code,
    chosen.food_name, chosen.reference_quantity, chosen.reference_unit,
    chosen.energy_kcal, chosen.protein_g, chosen.fat_g, chosen.carbs_g, chosen.fiber_g,
    chosen.protein_g * 100 / NULLIF(chosen.energy_kcal, 0) AS protein_per_100_kcal
FROM foods f
LEFT JOIN LATERAL (
    SELECT s.* FROM food_sources s
    WHERE s.food_id = f.id
      AND (%(source_name)s::text IS NULL OR s.source_name = %(source_name)s)
    ORDER BY (s.source_name = 'BLS 4.0') DESC, s.id ASC
    LIMIT 1
) chosen ON true
WHERE (%(kind)s::text IS NULL OR f.kind = %(kind)s)
  AND (%(group)s::text IS NULL OR EXISTS (
      SELECT 1 FROM food_sources group_source
      WHERE group_source.food_id = f.id AND group_source.source_name = 'BLS 4.0'
        AND group_source.group_code = %(group)s
  ))
  AND (%(preparation_state)s::text IS NULL OR f.preparation_state = %(preparation_state)s)
  AND (%(source_name)s::text IS NULL OR chosen.id IS NOT NULL)
  AND (%(min_protein)s::numeric IS NULL OR chosen.protein_g >= %(min_protein)s)
  AND (%(min_protein_density)s::numeric IS NULL OR
       chosen.protein_g * 100 / NULLIF(chosen.energy_kcal, 0) >= %(min_protein_density)s)
  AND (%(min_fiber)s::numeric IS NULL OR chosen.fiber_g >= %(min_fiber)s)
  AND (%(max_energy)s::numeric IS NULL OR chosen.energy_kcal <= %(max_energy)s)
  AND (
    %(q)s::text IS NULL
    OR strpos(lower(f.name), %(q)s) > 0
    OR strpos(lower(coalesce(f.brand, '')), %(q)s) > 0
    OR strpos(lower(coalesce(f.barcode, '')), %(q)s) > 0
    OR EXISTS (
        SELECT 1 FROM unnest(f.aliases) alias_name
        WHERE strpos(lower(alias_name), %(q)s) > 0
    )
    OR EXISTS (
        SELECT 1 FROM food_sources s
        WHERE s.food_id = f.id
          AND (
            strpos(lower(s.food_name), %(q)s) > 0
            OR strpos(lower(s.source_name), %(q)s) > 0
            OR strpos(lower(coalesce(s.external_id, '')), %(q)s) > 0
          )
    )
  )
"""


@dataclass(frozen=True)
class FoodFilters:
    q: str | None = None
    kind: str | None = None
    group: str | None = None
    source_name: str | None = None
    preparation_state: str | None = None
    min_protein: Decimal | None = None
    min_protein_density: Decimal | None = None
    min_fiber: Decimal | None = None
    max_energy: Decimal | None = None
    sort: Sort = "name"
    limit: int = 24
    offset: int = 0

    def sql_params(self) -> dict:
        return {
            "q": self.q.strip().lower() or None if self.q else None,
            "kind": self.kind,
            "group": self.group,
            "source_name": self.source_name,
            "preparation_state": self.preparation_state,
            "min_protein": self.min_protein,
            "min_protein_density": self.min_protein_density,
            "min_fiber": self.min_fiber,
            "max_energy": self.max_energy,
            "limit": self.limit,
            "offset": self.offset,
        }


def decimal_text(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def source_from_row(row: DictRow) -> dict | None:
    if row["source_id"] is None:
        return None
    return {
        "id": row["source_id"],
        "source_name": row["source_name"],
        "external_id": row["external_id"],
        "food_name": row["food_name"],
        "group_code": row["group_code"],
        "reference_quantity": decimal_text(row["reference_quantity"]),
        "reference_unit": row["reference_unit"],
        "protein_per_100_kcal": decimal_text(row["protein_per_100_kcal"]),
        **{field: decimal_text(row[field]) for field in NUTRIENTS},
    }


def food_from_row(row: DictRow) -> dict:
    return {
        "id": row["id"],
        "slug": row["slug"],
        "name": row["name"],
        "aliases": row["aliases"],
        "kind": row["kind"],
        "preparation_state": row["preparation_state"],
        "brand": row["brand"],
        "barcode": row["barcode"],
        "source_count": row["source_count"],
        "source": source_from_row(row),
    }


def list_foods(connection: Connection, filters: FoodFilters) -> dict:
    params = filters.sql_params()
    total = connection.execute(
        f"SELECT count(*) AS total FROM ({BASE_SQL}) catalog", params
    ).fetchone()["total"]
    rows = connection.execute(
        f"SELECT * FROM ({BASE_SQL}) catalog ORDER BY {SORT_SQL[filters.sort]} "
        "LIMIT %(limit)s OFFSET %(offset)s",
        params,
    ).fetchall()
    return {
        "items": [food_from_row(row) for row in rows],
        "total": total,
        "limit": filters.limit,
        "offset": filters.offset,
    }


def get_food(connection: Connection, slug: str) -> dict | None:
    row = connection.execute(
        """SELECT id, slug, name, aliases, kind, preparation_state, brand, barcode
           FROM foods WHERE slug = %s""",
        (slug,),
    ).fetchone()
    if row is None:
        return None
    sources = connection.execute(
        """SELECT id AS source_id, source_name, external_id, food_name, group_code,
                  reference_quantity, reference_unit,
                  energy_kcal, protein_g, fat_g, carbs_g, fiber_g,
                  protein_g * 100 / NULLIF(energy_kcal, 0) AS protein_per_100_kcal
           FROM food_sources WHERE food_id = %s
           ORDER BY (source_name = 'BLS 4.0') DESC, id ASC""",
        (row["id"],),
    ).fetchall()
    return {
        **dict(row),
        "sources": [source_from_row(source) for source in sources],
    }


def get_facets(connection: Connection) -> dict:
    return {
        "foods": connection.execute("SELECT count(*) AS n FROM foods").fetchone()["n"],
        "sources": connection.execute("SELECT count(*) AS n FROM food_sources").fetchone()["n"],
        "kinds": [
            row["kind"]
            for row in connection.execute(
                "SELECT DISTINCT kind FROM foods ORDER BY kind"
            ).fetchall()
        ],
        "source_names": [
            row["source_name"]
            for row in connection.execute(
                "SELECT DISTINCT source_name FROM food_sources ORDER BY source_name"
            ).fetchall()
        ],
        "preparation_states": [
            row["preparation_state"]
            for row in connection.execute(
                "SELECT DISTINCT preparation_state FROM foods "
                "WHERE preparation_state IS NOT NULL ORDER BY preparation_state"
            ).fetchall()
        ],
        "groups": [
            {"code": row["code"], "name": BLS_GROUP_NAMES[row["code"]], "count": row["count"]}
            for row in connection.execute(
                """SELECT group_code AS code, count(*) AS count
                   FROM food_sources WHERE source_name = 'BLS 4.0'
                     AND group_code IS NOT NULL
                   GROUP BY group_code ORDER BY group_code"""
            ).fetchall()
            if row["code"] in BLS_GROUP_NAMES
        ],
    }
