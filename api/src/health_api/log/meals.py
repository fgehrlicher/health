"""Meals: what was eaten, when, and how much. Nutrition always comes from the catalog.

Callers send "this much of this": catalog foods with amounts, or portions of a
cook from the cooking log. Every number is the referenced source's value times
the amount (for a cook: its ingredients' total per portion), calculated when read.
A meal without items is logged with unknown nutrition.

One exception: a stated item has no product. The person gives its name and the
values they read or know, e.g. a label read before the package was thrown away.
Those values are stored as given, marked as stated, and never inferred.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from psycopg import Connection
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from health_api.catalog.repository import NUTRIENTS
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


class StatedInput(BaseModel):
    """Nutrition the person states for something without a catalog product.

    Only the values given are kept. A value left out is unknown, never a guess.
    """

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(max_length=200)]
    energy_kcal: Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=1)]
    protein_g: Annotated[Decimal | None, Field(ge=0, max_digits=8, decimal_places=2)] = None
    fat_g: Annotated[Decimal | None, Field(ge=0, max_digits=8, decimal_places=2)] = None
    carbs_g: Annotated[Decimal | None, Field(ge=0, max_digits=8, decimal_places=2)] = None
    fiber_g: Annotated[Decimal | None, Field(ge=0, max_digits=8, decimal_places=2)] = None

    @field_validator("name")
    @classmethod
    def name_is_text(cls, value: str) -> str:
        if not (stripped := value.strip()):
            raise ValueError("must not be blank")
        return stripped


class ItemInput(BaseModel):
    """One thing eaten: a catalog food (amount or portion), portions of a cook, or a stated item."""

    model_config = ConfigDict(extra="forbid")

    food: Annotated[str | None, Field(min_length=1, max_length=200, description="catalog slug")] = (
        None
    )
    # A cooked dish from the cooking log; `amount` is then in its portions.
    cook: int | None = None
    # Nutrition stated by the person, for something without a catalog product.
    stated: StatedInput | None = None
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
    def one_kind(self):
        given = [self.food is not None, self.cook is not None, self.stated is not None]
        if sum(given) != 1:
            raise ValueError("give exactly one of food, cook, or stated")
        if self.stated is not None:
            if any(
                value is not None
                for value in (self.amount, self.portion, self.count, self.source_id)
            ):
                raise ValueError("a stated item takes only its values and estimated")
            return self
        if self.cook is not None:
            if self.amount is None:
                raise ValueError("give the portions of the cook as amount")
            if self.source_id is not None or self.portion is not None or self.count is not None:
                raise ValueError("a cook takes only amount and estimated")
            return self
        FoodAmount.model_validate(self.model_dump(exclude={"cook", "stated"}))
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
        if item.stated is not None:
            rows.append({"stated": item.stated.model_dump(), "estimated": item.estimated})
            continue
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
            connection,
            FoodAmount.model_validate(item.model_dump(exclude={"cook", "stated"})),
            field,
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
        if "stated" in row:
            stated = row["stated"]
            connection.execute(
                """INSERT INTO log.meal_items (meal_id, amount, estimated, stated_name,
                       stated_energy_kcal, stated_protein_g, stated_fat_g, stated_carbs_g,
                       stated_fiber_g)
                   VALUES (%(meal_id)s, 1, %(estimated)s, %(name)s, %(energy_kcal)s,
                       %(protein_g)s, %(fat_g)s, %(carbs_g)s, %(fiber_g)s)""",
                {
                    "meal_id": meal_id,
                    "estimated": row["estimated"],
                    "name": stated["name"],
                    "energy_kcal": stated["energy_kcal"],
                    "protein_g": stated["protein_g"],
                    "fat_g": stated["fat_g"],
                    "carbs_g": stated["carbs_g"],
                    "fiber_g": stated["fiber_g"],
                },
            )
            continue
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


def stated_items(connection: Connection, meal_ids: list[int]) -> dict[int, list[dict]]:
    """Stated items, shaped like source amounts: one unit, with only the values given."""
    rows = connection.execute(
        """SELECT id, meal_id, estimated, stated_name, stated_energy_kcal, stated_protein_g,
                  stated_fat_g, stated_carbs_g, stated_fiber_g
           FROM log.meal_items
           WHERE meal_id = ANY(%s) AND stated_name IS NOT NULL ORDER BY id""",
        (meal_ids,),
    ).fetchall()
    result: dict[int, list[dict]] = {}
    for row in rows:
        values = {column: None for column in NUTRIENTS} | {
            "energy_kcal": row["stated_energy_kcal"],
            "protein_g": row["stated_protein_g"],
            "fat_g": row["stated_fat_g"],
            "carbs_g": row["stated_carbs_g"],
            "fiber_g": row["stated_fiber_g"],
        }
        result.setdefault(row["meal_id"], []).append(
            {
                "id": row["id"],
                "stated": True,
                "name": row["stated_name"],
                "estimated": row["estimated"],
                "amount": Decimal(1),
                "reference_quantity": Decimal(1),
                **values,
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
    for meal_id, stated in stated_items(connection, meal_ids).items():
        items[meal_id] = sorted(items.get(meal_id, []) + stated, key=lambda item: item["id"])
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


def public_stated(item: dict) -> dict:
    """A stated item as the API shows it: no product, only the values the person gave."""
    return {
        "id": item["id"],
        "food": None,
        "food_name": item["name"],
        "food_name_de": None,
        "source_id": None,
        "source_name": "Stated by you",
        "cook_id": None,
        "recipe": None,
        "cooked_at": None,
        "amount": "1",
        "unit": "item",
        "estimated": item["estimated"],
        "nutrition": rounded_values(item_values(item)),
    }


def public_item(item: dict) -> dict:
    if item.get("stated"):
        return public_stated(item)
    if "cook" not in item:
        return public_amount(item) | {"cook_id": None, "recipe": None, "cooked_at": None}
    cook = item["cook"]
    return {
        "id": item["id"],
        "food": None,
        "food_name": cook["name"],
        "food_name_de": None,
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
        "incomplete": is_incomplete(connection, day),
        "meals": meals,
        "counts": {
            name: sum(meal["status"] == name for meal in meals)
            for name in ("measured", "estimated", "unknown")
        },
        "totals": day_totals,
    }


def is_incomplete(connection: Connection, day: date) -> bool:
    row = connection.execute(
        "SELECT EXISTS (SELECT 1 FROM log.incomplete_days WHERE day = %s) AS flagged", (day,)
    ).fetchone()
    return row["flagged"]


def set_incomplete(connection: Connection, day: date, incomplete: bool) -> None:
    if incomplete:
        connection.execute(
            "INSERT INTO log.incomplete_days (day) VALUES (%s) ON CONFLICT DO NOTHING", (day,)
        )
    else:
        connection.execute("DELETE FROM log.incomplete_days WHERE day = %s", (day,))


def goals(connection: Connection) -> dict:
    """The daily kcal limit, and the kcal accepted above it before a day turns red."""
    row = connection.execute(
        "SELECT daily_kcal_limit, kcal_tolerance FROM log.goals WHERE id = 1"
    ).fetchone()
    return {"daily_kcal_limit": row["daily_kcal_limit"], "kcal_tolerance": row["kcal_tolerance"]}


def set_goals(connection: Connection, limit: int, tolerance: int) -> None:
    connection.execute(
        """UPDATE log.goals SET daily_kcal_limit = %s, kcal_tolerance = %s, updated_at = now()
           WHERE id = 1""",
        (limit, tolerance),
    )


# The nutrients the calendar sends per day: energy, and what the energy split needs.
CALENDAR_NUTRIENTS = (
    "energy_kcal",
    "protein_g",
    "fat_g",
    "carbs_g",
    "fiber_g",
    "polyols_g",
    "alcohol_g",
)


def calendar_days(connection: Connection, first: date, last: date) -> list[dict]:
    """Days from first to last, local time, that have meals or are marked incomplete.

    Each day sums its items the way day_summary does, in one query for the whole range.
    """
    start, _ = day_bounds(first)
    _, end = day_bounds(last)
    loaded = load_meals_with_items(
        connection, "eaten_at >= %(start)s AND eaten_at < %(end)s", {"start": start, "end": end}
    )
    flagged = {
        row["day"].isoformat()
        for row in connection.execute(
            "SELECT day FROM log.incomplete_days WHERE day BETWEEN %(first)s AND %(last)s",
            {"first": first, "last": last},
        )
    }
    by_day: dict[str, list[tuple[dict, list[dict]]]] = {day: [] for day in flagged}
    for meal, items in loaded:
        # The stored times are local (isoformat in the app zone), so the date is the local one.
        by_day.setdefault(meal["eaten_at"][:10], []).append((meal, items))
    days = []
    for day, entries in sorted(by_day.items()):
        day_totals = totals([item for _meal, items in entries for item in items])
        days.append(
            {
                "date": day,
                "incomplete": day in flagged,
                "meals": len(entries),
                "unknown_meals": sum(meal["status"] == "unknown" for meal, _items in entries),
            }
            | {name: day_totals[name] for name in CALENDAR_NUTRIENTS}
        )
    return days
