"""Meals: what was eaten, when, and how much. Nutrition always comes from the catalog.

Callers send "this much of this": catalog foods with amounts, or portions of a
cook from the cooking log. They cannot send nutrition values; every number is
the referenced source's value times the amount (for a cook: its ingredients'
total per portion), calculated when read. A meal without items is logged with
unknown nutrition.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from psycopg import Connection
from pydantic import BaseModel, ConfigDict, Field, model_validator

from health_api.clock import day_bounds, timezone
from health_api.ingredients import (
    FoodAmount,
    InputError,
    load_amounts,
    public_amount,
    resolve_amount,
)
from health_api.nutrition import item_values, rounded_values, status, totals
from health_api.recipes.cooks import cook_sources

MealKind = Literal["breakfast", "lunch", "dinner", "snack"]
MAX_ITEMS = 100
MAX_PORTIONS = Decimal(20)


class ItemInput(BaseModel):
    """One thing eaten: a catalog food (amount or portion), or portions of a cook."""

    model_config = ConfigDict(extra="forbid")

    food: Annotated[str | None, Field(min_length=1, max_length=200, description="catalog slug")] = (
        None
    )
    # A cooked dish from the cooking log; `amount` is then in its portions.
    cook: int | None = None
    # Default: the food's BLS 4.0 source, otherwise its newest source.
    source_id: int | None = None
    # In the source's unit (g or ml), or portions of a cook. Give this or a portion.
    amount: Annotated[Decimal | None, Field(gt=0, max_digits=10, decimal_places=3)] = None
    # A named portion of the food, e.g. "Becher", times count.
    portion: Annotated[str | None, Field(min_length=1, max_length=60)] = None
    # How many portions; only with `portion`. Default 1.
    count: Annotated[Decimal | None, Field(gt=0, max_digits=6, decimal_places=3)] = None
    # The amount was guessed rather than weighed or read from a package.
    estimated: bool = False

    @model_validator(mode="after")
    def food_or_cook(self):
        if (self.food is None) == (self.cook is None):
            raise ValueError("give either food or cook")
        if self.cook is not None:
            if self.amount is None:
                raise ValueError("give the portions of the cook as amount")
            if self.source_id is not None or self.portion is not None or self.count is not None:
                raise ValueError("a cook takes only amount and estimated")
            return self
        FoodAmount.model_validate(self.model_dump(exclude={"cook"}))
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


def resolve_items(connection: Connection, items: list[ItemInput]) -> list[dict]:
    """Find each item's source or cook and its amount; fail with all issues."""
    rows, issues = [], []
    for index, item in enumerate(items):
        field = f"items.{index}"
        if item.cook is not None:
            found = connection.execute(
                "SELECT 1 FROM recipe.cooks WHERE id = %s", (item.cook,)
            ).fetchone()
            if found is None:
                issues.append({"field": f"{field}.cook", "message": f"unknown cook {item.cook}"})
            elif item.amount > MAX_PORTIONS:
                issues.append({"field": field, "message": f"more than {MAX_PORTIONS} portions"})
            else:
                rows.append(
                    {"cook_id": item.cook, "amount": item.amount, "estimated": item.estimated}
                )
            continue
        row, issue = resolve_amount(
            connection, FoodAmount.model_validate(item.model_dump(exclude={"cook"})), field
        )
        if issue:
            issues.append(issue)
        else:
            rows.append(row)
    if issues:
        raise InputError(issues)
    return rows


def insert_items(connection: Connection, meal_id: int, rows: list[dict]) -> None:
    for row in rows:
        connection.execute(
            """INSERT INTO log.meal_items (meal_id, source_id, cook_id, amount, estimated)
               VALUES (%(meal_id)s, %(source_id)s, %(cook_id)s, %(amount)s, %(estimated)s)""",
            {"source_id": None, "cook_id": None} | row | {"meal_id": meal_id},
        )


def clean_note(note: str | None) -> str | None:
    """Trimmed note text; blank means no note."""
    return note.strip() or None if note is not None else None


def cook_items(connection: Connection, meal_ids: list[int]) -> dict[int, list[dict]]:
    """Portions of cooks, shaped like source amounts: the cook's total per its portions."""
    rows = connection.execute(
        """SELECT id, meal_id, cook_id, amount, estimated FROM log.meal_items
           WHERE meal_id = ANY(%s) AND cook_id IS NOT NULL ORDER BY id""",
        (meal_ids,),
    ).fetchall()
    cooks = cook_sources(connection, sorted({row["cook_id"] for row in rows}))
    result: dict[int, list[dict]] = {}
    for row in rows:
        cook = cooks[row["cook_id"]]
        result.setdefault(row["meal_id"], []).append(
            {
                **row,
                "cook": cook,
                "own_estimated": row["estimated"],
                "estimated": row["estimated"] or cook["estimated"],
                "reference_quantity": cook["portions"],
                **cook["values"],
            }
        )
    return result


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
    meal_ids = [meal["id"] for meal in meals]
    items = load_amounts(connection, "log.meal_items", meal_ids)
    for meal_id, portions in cook_items(connection, meal_ids).items():
        items[meal_id] = sorted(items.get(meal_id, []) + portions, key=lambda item: item["id"])
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
    if "cook" not in item:
        return public_amount(item) | {"cook_id": None, "recipe": None, "cooked_at": None}
    cook = item["cook"]
    return {
        "id": item["id"],
        "food": None,
        "food_name": cook["name"],
        "source_id": None,
        "source_name": None,
        "cook_id": cook["id"],
        "recipe": cook["recipe"],
        "cooked_at": cook["cooked_at"].astimezone(timezone()).isoformat(),
        "amount": str(item["amount"]),
        "unit": "portion",
        "estimated": item["own_estimated"],
        "nutrition": rounded_values(item_values(item)),
    }


def get_meal(connection: Connection, meal_id: int) -> dict | None:
    meals = load_meals(connection, "id = %(id)s", {"id": meal_id})
    return meals[0] if meals else None


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
