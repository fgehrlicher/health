"""Amounts of catalog foods as callers send them: meal items and recipe ingredients.

A caller names a food by slug and gives an amount or a named portion; this
resolves it to a catalog source and an amount in the source's unit.
"""

from decimal import Decimal
from typing import Annotated

from psycopg import Connection
from pydantic import BaseModel, ConfigDict, Field, model_validator

from health_api.catalog.repository import NUTRIENTS
from health_api.nutrition import item_values, rounded_values

MAX_AMOUNT = Decimal(5000)


class InputError(Exception):
    """Invalid input found while checking it against the database; nothing is written."""

    def __init__(self, issues: list[dict]):
        super().__init__("; ".join(issue["message"] for issue in issues))
        self.issues = issues


class FoodAmount(BaseModel):
    """A catalog food and how much, as an amount or a portion."""

    model_config = ConfigDict(extra="forbid")

    food: Annotated[str, Field(min_length=1, max_length=200, description="catalog slug")]
    # Default: the food's BLS 4.0 source, otherwise its newest source.
    source_id: int | None = None
    # In the source's unit (g or ml). Give this or a portion, not both.
    amount: Annotated[Decimal | None, Field(gt=0, max_digits=10, decimal_places=3)] = None
    # A named portion of the food, e.g. "Becher", times count.
    portion: Annotated[str | None, Field(min_length=1, max_length=60)] = None
    # How many portions; only with `portion`. Default 1.
    count: Annotated[Decimal | None, Field(gt=0, max_digits=6, decimal_places=3)] = None
    # The amount was guessed rather than weighed or read from a package.
    estimated: bool = False

    @model_validator(mode="after")
    def amount_or_portion(self):
        if (self.amount is None) == (self.portion is None):
            raise ValueError("give either amount or portion")
        if self.count is not None and self.portion is None:
            raise ValueError("count applies only to a portion")
        return self


def resolve_amount(
    connection: Connection, item: FoodAmount, field: str
) -> tuple[dict | None, dict | None]:
    """The item as a source and amount, or the issue that prevents it."""
    food = connection.execute(
        "SELECT id FROM catalog.foods WHERE slug = %s", (item.food,)
    ).fetchone()
    if food is None:
        return None, {"field": f"{field}.food", "message": f"unknown food {item.food!r}"}
    source = connection.execute(
        """SELECT id, reference_unit FROM catalog.food_sources
           WHERE food_id = %(food)s AND (%(source)s::bigint IS NULL OR id = %(source)s)
           ORDER BY (source_name = 'BLS 4.0') DESC, id DESC
           LIMIT 1""",
        {"food": food["id"], "source": item.source_id},
    ).fetchone()
    if source is None:
        message = f"source {item.source_id} is not a source of {item.food!r}"
        return None, {"field": f"{field}.source_id", "message": message}
    amount = item.amount
    if item.portion is not None:
        portion = connection.execute(
            """SELECT quantity, unit FROM catalog.food_portions
               WHERE food_id = %s AND lower(name) = lower(%s)""",
            (food["id"], item.portion),
        ).fetchone()
        if portion is None:
            names = [
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM catalog.food_portions WHERE food_id = %s ORDER BY name",
                    (food["id"],),
                )
            ]
            message = f"{item.food!r} has no portion {item.portion!r}; known: {names}"
            return None, {"field": f"{field}.portion", "message": message}
        if portion["unit"] != source["reference_unit"]:
            message = (
                f"portion {item.portion!r} is in {portion['unit']}, but source "
                f"{source['id']} is per {source['reference_unit']}; pick a source_id in "
                f"{portion['unit']} or give an amount"
            )
            return None, {"field": f"{field}.portion", "message": message}
        amount = portion["quantity"] * (item.count or 1)
    if amount > MAX_AMOUNT:
        unit = source["reference_unit"]
        return None, {"field": field, "message": f"more than {MAX_AMOUNT} {unit}"}
    return {"source_id": source["id"], "amount": amount, "estimated": item.estimated}, None


def resolve_amounts(
    connection: Connection, items: list[FoodAmount], prefix: str = "items"
) -> list[dict]:
    """Resolve every item; fail with all issues at once."""
    rows, issues = [], []
    for index, item in enumerate(items):
        row, issue = resolve_amount(connection, item, f"{prefix}.{index}")
        if issue:
            issues.append(issue)
        else:
            rows.append(row)
    if issues:
        raise InputError(issues)
    return rows


# Tables holding amounts of sources, each with the column naming its owner.
ITEM_TABLES = {
    "log.meal_items": "meal_id",
    "recipe.version_items": "version_id",
    "recipe.cook_items": "cook_id",
}


def load_amounts(connection: Connection, table: str, owner_ids: list[int]) -> dict[int, list[dict]]:
    """Each owner's source amounts with the source's values, in insertion order."""
    owner = ITEM_TABLES[table]
    result: dict[int, list[dict]] = {}
    if not owner_ids:
        return result
    for item in connection.execute(
        f"""SELECT i.id, i.{owner} AS owner_id, f.slug AS food, f.name AS food_name,
                   g.slug AS variant_of, g.name AS variant_of_name,
                   (SELECT count(*) FROM catalog.foods v WHERE v.variant_of = f.id) AS variants,
                   i.source_id, s.source_name, i.amount, s.reference_unit AS unit, i.estimated,
                   s.reference_quantity, {", ".join(f"s.{c}" for c in NUTRIENTS)}
            FROM {table} i
            JOIN catalog.food_sources s ON s.id = i.source_id
            JOIN catalog.foods f ON f.id = s.food_id
            LEFT JOIN catalog.foods g ON g.id = f.variant_of
            WHERE i.{owner} = ANY(%s)
            ORDER BY i.id""",
        (owner_ids,),
    ):
        result.setdefault(item["owner_id"], []).append(item)
    return result


def insert_amounts(connection: Connection, table: str, owner_id: int, rows: list[dict]) -> None:
    owner = ITEM_TABLES[table]
    for row in rows:
        connection.execute(
            f"""INSERT INTO {table} ({owner}, source_id, amount, estimated)
                VALUES (%(owner_id)s, %(source_id)s, %(amount)s, %(estimated)s)""",
            {**row, "owner_id": owner_id},
        )


def public_amount(item: dict) -> dict:
    return {
        "id": item["id"],
        "food": item["food"],
        "food_name": item["food_name"],
        "variant_of": item["variant_of"],
        "variants": item["variants"],
        "source_id": item["source_id"],
        "source_name": item["source_name"],
        "amount": str(item["amount"]),
        "unit": item["unit"],
        "estimated": item["estimated"],
        "nutrition": rounded_values(item_values(item)),
    }


def changes(before: list[dict], after: list[dict]) -> list[dict]:
    """What differs between two ingredient lists, per ingredient.

    A branded product counts as the generic food it is a variant of, so soy
    drink in a recipe and a brand's soy drink in the pot are one ingredient:
    a swap, not a removal and an addition.
    """

    def parts(items: list[dict]) -> dict[str, dict[tuple, dict]]:
        result: dict[str, dict[tuple, dict]] = {}
        for item in items:
            key = item["variant_of"] or item["food"]
            part = result.setdefault(key, {}).setdefault(
                (item["food"], item["unit"]),
                {
                    "food": item["food"],
                    "food_name": item["food_name"],
                    "amount": Decimal(0),
                    "unit": item["unit"],
                },
            )
            part["amount"] += item["amount"]
        return result

    planned, actual = parts(before), parts(after)
    result = []
    for key in list(planned) + [key for key in actual if key not in planned]:
        was = list(planned.get(key, {}).values())
        now = list(actual.get(key, {}).values())
        if was == now:
            continue
        result.append(
            {
                "planned": [part | {"amount": str(part["amount"])} for part in was],
                "actual": [part | {"amount": str(part["amount"])} for part in now],
            }
        )
    return result
