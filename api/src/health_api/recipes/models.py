"""Response shapes of the recipe and cooking log API."""

from typing import Literal

from pydantic import BaseModel

from health_api.log.models import Amount, NutrientTotals, RecipeRef

Status = Literal["measured", "estimated", "unknown"]


class Change(BaseModel):
    """A food whose amount in a cook differs from its version; null means absent."""

    food: str
    food_name: str
    unit: str
    planned: str | None
    actual: str | None


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
