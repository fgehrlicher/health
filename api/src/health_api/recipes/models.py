"""Response shapes of the recipe and cooking log API."""

from typing import Literal

from pydantic import BaseModel

from health_api.log.models import Amount, NutrientTotals, RecipeRef

Status = Literal["measured", "estimated", "unknown"]


class ChangePart(BaseModel):
    food: str
    food_name: str
    amount: str
    unit: str


class Change(BaseModel):
    """One ingredient that differs, before and after; empty means absent.

    A branded product and its generic food are the same ingredient, so a swap
    is one change with different foods on either side.
    """

    planned: list[ChangePart]
    actual: list[ChangePart]


class CookSummary(BaseModel):
    id: int
    name: str
    recipe: RecipeRef | None
    version: int | None
    cooked_at: str
    portions: str
    weight_g: str | None
    note: str | None
    portions_eaten: str
    portions_left: str
    status: Status
    totals: NutrientTotals
    per_portion: NutrientTotals


class Cook(CookSummary):
    items: list[Amount]
    # Against the version cooked from; empty for an improvised cook.
    changes: list[Change]


class ParentRef(BaseModel):
    recipe: str
    recipe_name: str
    number: int


class Version(BaseModel):
    id: int
    number: int
    parent: ParentRef | None
    # Against the parent version; empty without a parent.
    changes: list[Change]
    from_cook_id: int | None
    note: str | None
    instructions: str | None
    portions: str
    created_at: str
    cooks: int
    status: Status
    items: list[Amount]
    totals: NutrientTotals
    per_portion: NutrientTotals


class Fork(BaseModel):
    slug: str
    name: str
    from_version: int


class Recipe(BaseModel):
    slug: str
    name: str
    note: str | None
    created_at: str
    # Newest first.
    versions: list[Version]
    forks: list[Fork]
    cooks: list[CookSummary]


class RecipeSummary(BaseModel):
    slug: str
    name: str
    note: str | None
    latest_version: int
    cooks: int
    last_cooked_at: str | None
    portions: str
    # Of the latest version.
    per_portion: NutrientTotals
