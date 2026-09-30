"""Public response shapes for the food catalog API."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class NutritionSource(BaseModel):
    id: int
    source_name: str
    external_id: str | None
    food_name: str
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
    ingredients_text: str | None


class SourceNutrient(BaseModel):
    key: str
    name: str
    category: str
    amount: str
    unit: str
    # A declared maximum, e.g. a label's "<0,1 µg".
    upper_bound: bool


class SourceDetail(NutritionSource):
    # Vitamins, minerals, and more beyond the label columns; unknown ones are absent.
    nutrients: list[SourceNutrient]


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
    # Code and name of the food group, e.g. "M" / "Dairy"; None if unassigned.
    food_group: str | None
    food_group_name: str | None
    brand: str | None
    barcode: str | None


class FoodSummary(FoodBase):
    source_count: int
    source: NutritionSource | None


class FoodDetail(FoodBase):
    sources: list[SourceDetail]
    portions: list[Portion]


class FoodPage(BaseModel):
    items: list[FoodSummary]
    total: int
    limit: int
    offset: int


class FacetValue(BaseModel):
    value: str
    count: int


class FacetGroup(BaseModel):
    code: str
    name: str
    count: int


class CatalogFacets(BaseModel):
    """Filter values with counts. Each list is counted under every active
    filter except its own, and holds the values with at least one food plus
    the selected value (with count 0 if nothing matches)."""

    # Foods matching every given filter.
    foods: int
    # Foods matching every filter except the group: the "all groups" count.
    any_group: int
    sources: int
    kinds: list[FacetValue]
    source_names: list[str]
    preparation_states: list[FacetValue]
    groups: list[FacetGroup]
    brands: list[FacetValue]


Amount = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=4)]
NutrientName = Literal[
    "energy_kj",
    "energy_kcal",
    "fat_g",
    "saturated_fat_g",
    "monounsaturated_fat_g",
    "polyunsaturated_fat_g",
    "carbs_g",
    "sugars_g",
    "polyols_g",
    "starch_g",
    "fiber_g",
    "protein_g",
    "salt_g",
    "alcohol_g",
]


class NutritionInput(BaseModel):
    """One nutrition column of a label, as printed (use the as-sold column)."""

    model_config = ConfigDict(extra="forbid")

    reference_quantity: Annotated[Decimal, Field(gt=0)] = Decimal(100)
    reference_unit: Literal["g", "ml"] = "g"
    energy_kj: Amount | None = None
    energy_kcal: Amount
    fat_g: Amount
    saturated_fat_g: Amount | None = None
    monounsaturated_fat_g: Amount | None = None
    polyunsaturated_fat_g: Amount | None = None
    carbs_g: Amount
    sugars_g: Amount | None = None
    polyols_g: Amount | None = None
    starch_g: Amount | None = None
    fiber_g: Amount | None = None
    protein_g: Amount
    salt_g: Amount | None = None
    alcohol_g: Amount | None = None
    # Values printed as "<0,5 g": store 0.5 and list the column here.
    upper_bounds: list[NutrientName] = []


class PortionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=60)]
    kind: Literal["package", "serving", "piece", "household"]
    quantity: Annotated[Decimal, Field(gt=0)]
    unit: Literal["g", "ml"]


class FoodInput(BaseModel):
    """A branded food from a label photo or product database."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=200)]
    brand: Annotated[str | None, Field(max_length=100)] = None
    barcode: Annotated[str | None, Field(max_length=14)] = None
    # Food group code, e.g. "M" for dairy (see /api/foods/facets). Without one,
    # the food is missing from category browsing.
    food_group: Annotated[str | None, Field(pattern="^[A-Z]$")] = None
    aliases: list[Annotated[str, Field(min_length=1, max_length=200)]] = []
    # Where the values come from, e.g. "Product label" or "Open Food Facts".
    source_name: Annotated[str, Field(min_length=1, max_length=100)] = "Product label"
    # Name as the source states it, e.g. the label's legal name; default: name.
    source_food_name: Annotated[str | None, Field(max_length=300)] = None
    # The full "Zutaten" list as printed, unparsed; omit rather than send a partial list.
    ingredients_text: Annotated[str | None, Field(min_length=1, max_length=5000)] = None
    nutrition: NutritionInput
    portions: list[PortionInput] = []


class FoodUpdate(BaseModel):
    """Catalog fields of a food; only the given ones change, null clears."""

    model_config = ConfigDict(extra="forbid")

    food_group: Annotated[str | None, Field(pattern="^[A-Z]$")] = None
    brand: Annotated[str | None, Field(min_length=1, max_length=100)] = None


class SourceTextUpdate(BaseModel):
    """Text read later from the same label, e.g. a second photo of a round cup."""

    model_config = ConfigDict(extra="forbid")

    # The label's legal name ("Bezeichnung"), stored as the source's food_name.
    food_name: Annotated[str | None, Field(min_length=1, max_length=300)] = None
    # The full "Zutaten" list as printed, unparsed.
    ingredients_text: Annotated[str | None, Field(min_length=1, max_length=5000)] = None


class Issue(BaseModel):
    field: str
    message: str


class FoodRegistration(BaseModel):
    dry_run: bool
    slug: str
    warnings: list[Issue]
    food: FoodDetail | None
