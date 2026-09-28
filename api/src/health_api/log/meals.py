"""Meals: what was eaten, when, and how much. Nutrition always comes from the catalog.

Callers send "this much of this": catalog foods with amounts. They cannot send
nutrition values; every number is the referenced source's value times the
amount, calculated when read. A meal without items is logged with unknown
nutrition.
"""

import os
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from psycopg import Connection
from pydantic import BaseModel, ConfigDict, Field, model_validator

from health_api.catalog.repository import NUTRIENTS

MealKind = Literal["breakfast", "lunch", "dinner", "snack"]
MAX_AMOUNT = Decimal(5000)
# Accept slightly future times from clock skew, not planned meals.
FUTURE_TOLERANCE = timedelta(minutes=10)


def timezone() -> ZoneInfo:
    """The person's local zone; days start at local midnight."""
    return ZoneInfo(os.environ.get("HEALTH_TIMEZONE", "Europe/Berlin"))


class ItemInput(BaseModel):
    """One food in a meal: a catalog food and how much, as an amount or a portion."""

    model_config = ConfigDict(extra="forbid")

    food: Annotated[str, Field(min_length=1, max_length=200, description="catalog slug")]
    # Default: the food's BLS 4.0 source, otherwise its newest source.
    source_id: int | None = None
    # In the source's unit (g or ml). Give this or a portion, not both.
    amount: Annotated[Decimal | None, Field(gt=0, max_digits=10, decimal_places=3)] = None
    # A named portion of the food, e.g. "Becher", times count.
    portion: Annotated[str | None, Field(min_length=1, max_length=60)] = None
    count: Annotated[Decimal, Field(gt=0, max_digits=6, decimal_places=3)] = Decimal(1)
    # The amount was guessed rather than weighed or read from a package.
    estimated: bool = False

    @model_validator(mode="after")
    def amount_or_portion(self):
        if (self.amount is None) == (self.portion is None):
            raise ValueError("give either amount or portion")
        return self


class MealInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Without an offset, the time is local (HEALTH_TIMEZONE). Default: now.
    eaten_at: datetime | None = None
    kind: MealKind | None = None
    # Empty means "ate something, nutrition unknown".
    items: list[ItemInput] = []


class MealUpdate(BaseModel):
    """Only the given fields change; `items` replaces all items."""

    model_config = ConfigDict(extra="forbid")

    eaten_at: datetime | None = None
    kind: MealKind | None = None
    items: list[ItemInput] | None = None


class LogError(Exception):
    def __init__(self, issues: list[dict]):
        super().__init__("; ".join(issue["message"] for issue in issues))
        self.issues = issues


def local_time(value: datetime | None) -> datetime:
    zone = timezone()
    if value is None:
        return datetime.now(zone)
    value = value.replace(tzinfo=zone) if value.tzinfo is None else value
    if value > datetime.now(UTC) + FUTURE_TOLERANCE:
        raise LogError([{"field": "eaten_at", "message": "lies in the future"}])
    return value


def resolve_items(connection: Connection, items: list[ItemInput]) -> list[dict]:
    """Find each item's source and turn portions into amounts; fail with all issues."""
    rows, issues = [], []
    for index, item in enumerate(items):
        field = f"items.{index}"
        food = connection.execute("SELECT id FROM foods WHERE slug = %s", (item.food,)).fetchone()
        if food is None:
            issues.append({"field": f"{field}.food", "message": f"unknown food {item.food!r}"})
            continue
        source = connection.execute(
            """SELECT id, reference_unit FROM food_sources
               WHERE food_id = %(food)s AND (%(source)s::bigint IS NULL OR id = %(source)s)
               ORDER BY (source_name = 'BLS 4.0') DESC, id DESC
               LIMIT 1""",
            {"food": food["id"], "source": item.source_id},
        ).fetchone()
        if source is None:
            message = f"source {item.source_id} is not a source of {item.food!r}"
            issues.append({"field": f"{field}.source_id", "message": message})
            continue
        amount = item.amount
        if item.portion is not None:
            portion = connection.execute(
                """SELECT quantity, unit FROM food_portions
                   WHERE food_id = %s AND lower(name) = lower(%s)""",
                (food["id"], item.portion),
            ).fetchone()
            if portion is None or portion["unit"] != source["reference_unit"]:
                names = [
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM food_portions WHERE food_id = %s ORDER BY name",
                        (food["id"],),
                    )
                ]
                message = f"{item.food!r} has no portion {item.portion!r}; known: {names}"
                issues.append({"field": f"{field}.portion", "message": message})
                continue
            amount = portion["quantity"] * item.count
        if amount > MAX_AMOUNT:
            unit = source["reference_unit"]
            issues.append({"field": field, "message": f"more than {MAX_AMOUNT} {unit}"})
            continue
        rows.append({"source_id": source["id"], "amount": amount, "estimated": item.estimated})
    if issues:
        raise LogError(issues)
    return rows


def insert_items(connection: Connection, meal_id: int, rows: list[dict]) -> None:
    for row in rows:
        connection.execute(
            """INSERT INTO log.meal_items (meal_id, source_id, amount, estimated)
               VALUES (%(meal_id)s, %(source_id)s, %(amount)s, %(estimated)s)""",
            {**row, "meal_id": meal_id},
        )


def rounded(column: str, value: Decimal) -> str:
    places = Decimal(1) if column.startswith("energy") else Decimal("0.01")
    return str(value.quantize(places))


def item_values(item: dict) -> dict[str, Decimal | None]:
    """Each nutrient for the eaten amount; None where the source has no value."""
    factor = item["amount"] / item["reference_quantity"]
    return {column: None if item[column] is None else item[column] * factor for column in NUTRIENTS}


def status(items: list[dict]) -> Literal["measured", "estimated", "unknown"]:
    if not items:
        return "unknown"
    return "estimated" if any(item["estimated"] for item in items) else "measured"


def load_meals(connection: Connection, where: str, params: dict) -> list[dict]:
    meals = connection.execute(
        f"SELECT id, eaten_at, kind FROM log.meals WHERE {where} ORDER BY eaten_at, id", params
    ).fetchall()
    if not meals:
        return []
    items: dict[int, list] = {}
    for item in connection.execute(
        f"""SELECT i.id, i.meal_id, f.slug AS food, f.name AS food_name, i.source_id,
                   s.source_name, i.amount, s.reference_unit AS unit, i.estimated,
                   s.reference_quantity, {", ".join(f"s.{c}" for c in NUTRIENTS)}
            FROM log.meal_items i
            JOIN food_sources s ON s.id = i.source_id
            JOIN foods f ON f.id = s.food_id
            WHERE i.meal_id = ANY(%s)
            ORDER BY i.id""",
        ([meal["id"] for meal in meals],),
    ):
        items.setdefault(item["meal_id"], []).append(item)
    zone = timezone()
    return [
        {
            "id": meal["id"],
            "eaten_at": meal["eaten_at"].astimezone(zone).isoformat(),
            "kind": meal["kind"],
            "status": status(items.get(meal["id"], [])),
            "items": [public_item(item) for item in items.get(meal["id"], [])],
            "totals": totals(items.get(meal["id"], [])),
        }
        for meal in meals
    ]


def public_item(item: dict) -> dict:
    return {
        "id": item["id"],
        "food": item["food"],
        "food_name": item["food_name"],
        "source_id": item["source_id"],
        "source_name": item["source_name"],
        "amount": str(item["amount"]),
        "unit": item["unit"],
        "estimated": item["estimated"],
        "nutrition": {
            column: None if value is None else rounded(column, value)
            for column, value in item_values(item).items()
        },
    }


def totals(items: list[dict]) -> dict:
    """Per nutrient: sums of measured and estimated items, and items lacking a value."""
    result = {}
    for column in NUTRIENTS:
        measured = estimated = Decimal(0)
        missing = 0
        for item in items:
            value = item_values(item)[column]
            if value is None:
                missing += 1
            elif item["estimated"]:
                estimated += value
            else:
                measured += value
        result[column] = {
            "measured": rounded(column, measured),
            "estimated": rounded(column, estimated),
            "items_without_value": missing,
        }
    return result


def get_meal(connection: Connection, meal_id: int) -> dict | None:
    meals = load_meals(connection, "id = %(id)s", {"id": meal_id})
    return meals[0] if meals else None


def day_bounds(day: date) -> tuple[datetime, datetime]:
    zone = timezone()
    return datetime.combine(day, time(), zone), datetime.combine(day + timedelta(1), time(), zone)


def day_summary(connection: Connection, day: date) -> dict:
    start, end = day_bounds(day)
    meals = load_meals(
        connection, "eaten_at >= %(start)s AND eaten_at < %(end)s", {"start": start, "end": end}
    )
    day_totals = {}
    for column in NUTRIENTS:
        day_totals[column] = {
            key: rounded(
                column, sum((Decimal(meal["totals"][column][key]) for meal in meals), Decimal(0))
            )
            for key in ("measured", "estimated")
        } | {
            "items_without_value": sum(
                meal["totals"][column]["items_without_value"] for meal in meals
            )
        }
    return {
        "date": day.isoformat(),
        "timezone": timezone().key,
        "meals": meals,
        "counts": {
            name: sum(meal["status"] == name for meal in meals)
            for name in ("measured", "estimated", "unknown")
        },
        "totals": day_totals,
    }
