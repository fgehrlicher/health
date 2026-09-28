"""Read-only queries for the food catalog."""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from psycopg import Connection
from psycopg.rows import DictRow

Sort = Literal[
    "relevance",
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
    "relevance": "relevance DESC, length(name) ASC, lower(name) ASC, id ASC",
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
# Nutrition columns in EU label order, see db/schema.sql.
NUTRIENTS = (
    "energy_kj",
    "energy_kcal",
    "fat_g",
    "saturated_fat_g",
    "monounsaturated_fat_g",
    "polyunsaturated_fat_g",
    "carbs_g",
    "sugars_g",
    "polyols_g",
    "starch_g",
    "fiber_g",
    "protein_g",
    "salt_g",
    "alcohol_g",
)
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

# Ranked search over the food_search_* views. Every query token must match a
# word of the food's names, codes, brand, or barcode: exactly, by prefix, as a
# plural/compound part, or by trigram similarity for typos. Ranking favors
# foods whose head phrase (words before the first comma) the query covers.
# Unprepared BLS foods (code ending in 00; the sixth digit encodes preparation)
# get a bonus, composite dishes (BLS groups X and Y) a penalty.
SEARCH_SQL = """
WITH query_tokens AS (
    SELECT token FROM unnest(%(tokens)s::text[]) AS token
),
word_matches AS (
    SELECT word, token, CASE
        WHEN word = token THEN 1.0
        WHEN starts_with(word, token) THEN 0.9
        WHEN starts_with(token, word)
            THEN CASE WHEN length(token) - length(word) <= 2 THEN 0.85 ELSE 0.6 END
        ELSE similarity(word, token) * 0.8
    END AS score
    FROM (
        SELECT v.word, q.token FROM query_tokens q
        JOIN catalog.food_search_vocabulary v ON starts_with(v.word, q.token)
        UNION
        SELECT v.word, q.token FROM query_tokens q
        CROSS JOIN LATERAL generate_series(3, length(q.token)) AS prefix_length
        JOIN catalog.food_search_vocabulary v ON v.word = left(q.token, prefix_length)
        UNION
        SELECT v.word, q.token FROM query_tokens q
        JOIN catalog.food_search_vocabulary v
          -- Typos only for words, not codes: F130100 is not a typo of F110100.
          ON length(q.token) >= 4 AND q.token !~ '[0-9]'
         AND v.word %% q.token AND similarity(v.word, q.token) >= 0.4
    ) candidates
),
token_scores AS (
    SELECT t.food_id, m.token, max(m.score) AS score
    FROM word_matches m JOIN catalog.food_search_terms t USING (word)
    GROUP BY t.food_id, m.token
),
matched_foods AS (
    SELECT food_id, avg(score) AS match_score
    FROM token_scores
    GROUP BY food_id
    HAVING count(*) = (SELECT count(*) FROM query_tokens)
),
-- Share of each word the query covers: "butter" covers 6 of 14 letters of
-- "butterzwieback", so a compound does not count as a full match.
word_scores AS (
    SELECT word, max(score * least(length(token), length(word))::numeric / length(word)) AS score
    FROM word_matches GROUP BY word
),
-- Credit each head word with the best-scoring term covering it, including
-- joined pairs: "hähnchenbrust" covers both words of "hähnchen brustfilet".
covered_words AS (
    SELECT t.food_id, t.title, part AS word, max(w.score) AS score
    FROM catalog.food_search_terms t
    JOIN matched_foods USING (food_id)
    JOIN word_scores w USING (word)
    CROSS JOIN LATERAL unnest(t.parts) AS part
    GROUP BY t.food_id, t.title, part
),
head_coverage AS (
    SELECT food_id, max(coverage) AS coverage
    FROM (
        SELECT t.food_id,
               sum(length(t.word) * coalesce(c.score, 0)) / sum(length(t.word)) AS coverage
        FROM catalog.food_search_terms t
        JOIN matched_foods USING (food_id)
        LEFT JOIN covered_words c USING (food_id, title, word)
        WHERE t.head
        GROUP BY t.food_id, t.title
    ) per_title
    GROUP BY food_id
),
search_matches AS (
    SELECT
        m.food_id,
        0.4 * m.match_score + 0.6 * coalesce(h.coverage, 0)
        + CASE WHEN EXISTS (
              SELECT 1 FROM catalog.food_sources s
              WHERE s.food_id = m.food_id AND s.source_name = 'BLS 4.0'
                AND right(s.external_id, 2) = '00'
          ) THEN 0.1 ELSE 0 END
        - CASE WHEN EXISTS (
              SELECT 1 FROM catalog.food_sources s
              WHERE s.food_id = m.food_id AND s.group_code IN ('X', 'Y')
          ) THEN 0.15 ELSE 0 END
        AS relevance
    FROM matched_foods m
    LEFT JOIN head_coverage h USING (food_id)
)
"""

BASE_SQL = (
    SEARCH_SQL
    + """
SELECT
    f.id, f.slug, f.name, f.aliases, f.kind, f.preparation_state, f.brand, f.barcode,
    (SELECT count(*) FROM catalog.food_sources s WHERE s.food_id = f.id) AS source_count,
    chosen.id AS source_id, chosen.source_name, chosen.external_id, chosen.group_code,
    chosen.food_name, chosen.reference_quantity, chosen.reference_unit,
    chosen.upper_bounds, chosen.ingredients_text, """
    + ", ".join(f"chosen.{column}" for column in NUTRIENTS)
    + """,
    chosen.protein_g * 100 / NULLIF(chosen.energy_kcal, 0) AS protein_per_100_kcal,
    coalesce(m.relevance, 0) AS relevance
FROM catalog.foods f
LEFT JOIN search_matches m ON m.food_id = f.id
LEFT JOIN LATERAL (
    SELECT s.* FROM catalog.food_sources s
    WHERE s.food_id = f.id
      AND (%(source_name)s::text IS NULL OR s.source_name = %(source_name)s)
    ORDER BY (s.source_name = 'BLS 4.0') DESC, s.id ASC
    LIMIT 1
) chosen ON true
WHERE (%(kind)s::text IS NULL OR f.kind = %(kind)s)
  AND (%(group)s::text IS NULL OR EXISTS (
      SELECT 1 FROM catalog.food_sources group_source
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
  AND (%(tokens)s::text[] IS NULL OR m.food_id IS NOT NULL)
"""
)


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
    sort: Sort = "relevance"
    limit: int = 24
    offset: int = 0

    def sql_params(self) -> dict:
        return {
            "tokens": search_tokens(self.q),
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


def search_tokens(q: str | None) -> list[str] | None:
    """Split a query into at most eight distinct lowercase words, or None for no search."""
    tokens = list(dict.fromkeys(re.findall(r"[^\W_]+", (q or "").lower())))[:8]
    return tokens or None


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
        "upper_bounds": row["upper_bounds"],
        "ingredients_text": row["ingredients_text"],
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
    # Without a query every relevance is 0; browse alphabetically instead.
    sort = "name" if filters.sort == "relevance" and not params["tokens"] else filters.sort
    total = connection.execute(
        f"SELECT count(*) AS total FROM ({BASE_SQL}) listing", params
    ).fetchone()["total"]
    rows = connection.execute(
        f"SELECT * FROM ({BASE_SQL}) listing ORDER BY {SORT_SQL[sort]} "
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
           FROM catalog.foods WHERE slug = %s""",
        (slug,),
    ).fetchone()
    if row is None:
        return None
    sources = connection.execute(
        f"""SELECT id AS source_id, source_name, external_id, food_name, group_code,
                  reference_quantity, reference_unit, upper_bounds, ingredients_text,
                  {", ".join(NUTRIENTS)},
                  protein_g * 100 / NULLIF(energy_kcal, 0) AS protein_per_100_kcal
           FROM catalog.food_sources WHERE food_id = %s
           ORDER BY (source_name = 'BLS 4.0') DESC, id ASC""",
        (row["id"],),
    ).fetchall()
    nutrients: dict[int, list] = {}
    for nutrient in connection.execute(
        """SELECT v.source_id, n.key, n.name, n.category, v.amount, n.unit, v.upper_bound
           FROM catalog.food_source_nutrients v
           JOIN catalog.nutrients n ON n.key = v.nutrient_key
           JOIN catalog.food_sources s ON s.id = v.source_id
           WHERE s.food_id = %s
           ORDER BY n.sort_order""",
        (row["id"],),
    ):
        source_id = nutrient.pop("source_id")
        nutrient["amount"] = decimal_text(nutrient["amount"])
        nutrients.setdefault(source_id, []).append(nutrient)
    portions = connection.execute(
        """SELECT name, kind, quantity, unit FROM catalog.food_portions
           WHERE food_id = %s ORDER BY quantity, name""",
        (row["id"],),
    ).fetchall()
    return {
        **dict(row),
        "sources": [
            {**source_from_row(source), "nutrients": nutrients.get(source["source_id"], [])}
            for source in sources
        ],
        "portions": [
            {**portion, "quantity": decimal_text(portion["quantity"])} for portion in portions
        ],
    }


def get_facets(connection: Connection) -> dict:
    return {
        "foods": connection.execute("SELECT count(*) AS n FROM catalog.foods").fetchone()["n"],
        "sources": connection.execute("SELECT count(*) AS n FROM catalog.food_sources").fetchone()[
            "n"
        ],
        "kinds": [
            row["kind"]
            for row in connection.execute(
                "SELECT DISTINCT kind FROM catalog.foods ORDER BY kind"
            ).fetchall()
        ],
        "source_names": [
            row["source_name"]
            for row in connection.execute(
                "SELECT DISTINCT source_name FROM catalog.food_sources ORDER BY source_name"
            ).fetchall()
        ],
        "preparation_states": [
            row["preparation_state"]
            for row in connection.execute(
                "SELECT DISTINCT preparation_state FROM catalog.foods "
                "WHERE preparation_state IS NOT NULL ORDER BY preparation_state"
            ).fetchall()
        ],
        "groups": [
            {"code": row["code"], "name": BLS_GROUP_NAMES[row["code"]], "count": row["count"]}
            for row in connection.execute(
                """SELECT group_code AS code, count(*) AS count
                   FROM catalog.food_sources WHERE source_name = 'BLS 4.0'
                     AND group_code IS NOT NULL
                   GROUP BY group_code ORDER BY group_code"""
            ).fetchall()
            if row["code"] in BLS_GROUP_NAMES
        ],
    }
