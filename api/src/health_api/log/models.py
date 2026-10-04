"""Response shapes of the consumption log API."""

from typing import Literal

from pydantic import BaseModel, create_model

from health_api.catalog.repository import NUTRIENTS
from health_api.log.meals import MealKind

# One field per label column, e.g. energy_kcal; None where the source has no value.
Nutrition = create_model(
    "Nutrition", **{column: (str | None, ...) for column in NUTRIENTS}, __base__=BaseModel
)


class NutrientTotal(BaseModel):
    measured: str
    estimated: str
    # Items whose source lacks this nutrient; the total is then a lower bound.
    items_without_value: int


NutrientTotals = create_model(
    "NutrientTotals", **{column: (NutrientTotal, ...) for column in NUTRIENTS}, __base__=BaseModel
)


class Amount(BaseModel):
    """An amount of a catalog source with its nutrition."""

    id: int
    food: str
    food_name: str
    # For a branded product: the generic food it is a kind of.
    variant_of: str | None
    # For a generic food: how many branded products are a kind of it.
    variants: int
    source_id: int
    source_name: str
    amount: str
    unit: str
    estimated: bool
    nutrition: Nutrition


class RecipeRef(BaseModel):
    slug: str
    name: str


class MealItem(BaseModel):
    """A catalog food, or portions of a cook (then `food` and `source_id` are null)."""

    id: int
    food: str | None
    # The food's name, or the cook's.
    food_name: str
    source_id: int | None
    source_name: str | None
    cook_id: int | None
    recipe: RecipeRef | None
    cooked_at: str | None
    amount: str
    # g or ml for a food; "portion" for a cook.
    unit: str
    estimated: bool
    nutrition: Nutrition


class Meal(BaseModel):
    id: int
    eaten_at: str
    kind: MealKind | None
    note: str | None
    status: Literal["measured", "estimated", "unknown"]
    items: list[MealItem]
    totals: NutrientTotals


class MealCounts(BaseModel):
    measured: int
    estimated: int
    unknown: int


class Day(BaseModel):
    date: str
    timezone: str
    meals: list[Meal]
    counts: MealCounts
    totals: NutrientTotals
