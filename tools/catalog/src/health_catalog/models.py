"""Public response shapes for the food catalog API."""

from pydantic import BaseModel


class NutritionSource(BaseModel):
    id: int
    source_name: str
    external_id: str | None
    food_name: str
    group_code: str | None
    reference_quantity: str
    reference_unit: str
    energy_kcal: str | None
    protein_g: str | None
    protein_per_100_kcal: str | None
    fat_g: str | None
    carbs_g: str | None
    fiber_g: str | None


class FoodBase(BaseModel):
    id: int
    slug: str
    name: str
    aliases: list[str]
    kind: str
    preparation_state: str | None
    brand: str | None
    barcode: str | None


class FoodSummary(FoodBase):
    source_count: int
    source: NutritionSource | None


class FoodDetail(FoodBase):
    sources: list[NutritionSource]


class FoodPage(BaseModel):
    items: list[FoodSummary]
    total: int
    limit: int
    offset: int


class CatalogFacets(BaseModel):
    foods: int
    sources: int
    kinds: list[str]
    source_names: list[str]
    preparation_states: list[str]
    groups: list[dict[str, str | int]]
