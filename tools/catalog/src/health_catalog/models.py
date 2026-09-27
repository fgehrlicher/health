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
    energy_kj: str | None
    energy_kcal: str | None
    fat_g: str | None
    saturated_fat_g: str | None
    monounsaturated_fat_g: str | None
    polyunsaturated_fat_g: str | None
    carbs_g: str | None
    sugars_g: str | None
    polyols_g: str | None
    starch_g: str | None
    fiber_g: str | None
    protein_g: str | None
    salt_g: str | None
    alcohol_g: str | None
    protein_per_100_kcal: str | None
    # Columns whose value is a declared maximum, e.g. a label's "<0,5 g".
    upper_bounds: list[str]


class Portion(BaseModel):
    name: str
    kind: str
    quantity: str
    unit: str


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
    portions: list[Portion]


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
