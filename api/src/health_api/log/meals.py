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
MAX_ITEMS = 100
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


class MealInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Without an offset, the time is local (HEALTH_TIMEZONE). Default: now.
    eaten_at: datetime | None = None
    kind: MealKind | None = None
    # Free thoughts about the meal, e.g. "too salty, portion was huge".
    note: Annotated[str | None, Field(max_length=2000)] = None
    # Empty means "ate something, nutrition unknown".
    items: Annotated[list[ItemInput], Field(max_length=MAX_ITEMS)] = []


class MealUpdate(BaseModel):
    """Only the given fields change; `items` replaces all items."""

    model_config = ConfigDict(extra="forbid")

    eaten_at: datetime | None = None
    kind: MealKind | None = None
    note: Annotated[str | None, Field(max_length=2000)] = None
    items: Annotated[list[ItemInput] | None, Field(max_length=MAX_ITEMS)] = None


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
        food = connection.execute(
            "SELECT id FROM catalog.foods WHERE slug = %s", (item.food,)
        ).fetchone()
        if food is None:
            issues.append({"field": f"{field}.food", "message": f"unknown food {item.food!r}"})
            continue
        source = connection.execute(
            """SELECT id, reference_unit FROM catalog.food_sources
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
                issues.append({"field": f"{field}.portion", "message": message})
                continue
            if portion["unit"] != source["reference_unit"]:
                message = (
                    f"portion {item.portion!r} is in {portion['unit']}, but source "
                    f"{source['id']} is per {source['reference_unit']}; pick a source_id in "
                    f"{portion['unit']} or give an amount"
                )
                issues.append({"field": f"{field}.portion", "message": message})
                continue
            amount = portion["quantity"] * (item.count or 1)
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


def clean_note(note: str | None) -> str | None:
    """Trimmed note text; blank means no note."""
    return note.strip() or None if note is not None else None


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
    return [meal for meal, _items in load_meals_with_items(connection, where, params)]


def load_meals_with_items(
    connection: Connection, where: str, params: dict
) -> list[tuple[dict, list[dict]]]:
    """Public meals, each with its raw items for exact sums across meals."""
    meals = connection.execute(
        f"SELECT id, eaten_at, kind, note FROM log.meals WHERE {where} ORDER BY eaten_at, id",
        params,
    ).fetchall()
    if not meals:
        return []
    items: dict[int, list] = {}
    for item in connection.execute(
        f"""SELECT i.id, i.meal_id, f.slug AS food, f.name AS food_name, i.source_id,
                   s.source_name, i.amount, s.reference_unit AS unit, i.estimated,
                   s.reference_quantity, {", ".join(f"s.{c}" for c in NUTRIENTS)}
            FROM log.meal_items i
            JOIN catalog.food_sources s ON s.id = i.source_id
            JOIN catalog.foods f ON f.id = s.food_id
            WHERE i.meal_id = ANY(%s)
            ORDER BY i.id""",
        ([meal["id"] for meal in meals],),
    ):
        items.setdefault(item["meal_id"], []).append(item)
    zone = timezone()
    return [
        (
            {
                "id": meal["id"],
                "eaten_at": meal["eaten_at"].astimezone(zone).isoformat(),
                "kind": meal["kind"],
                "note": meal["note"],
                "status": status(items.get(meal["id"], [])),
                "items": [public_item(item) for item in items.get(meal["id"], [])],
                "totals": totals(items.get(meal["id"], [])),
            },
            items.get(meal["id"], []),
        )
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
    loaded = load_meals_with_items(
        connection, "eaten_at >= %(start)s AND eaten_at < %(end)s", {"start": start, "end": end}
    )
    meals = [meal for meal, _items in loaded]
    # Sum exact item values, then round once; summing rounded meals drifts.
    day_totals = totals([item for _meal, items in loaded for item in items])
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
