// Friendly names for the generated FastAPI schema (see `make web-types`).
import type { components } from "./schema.gen"

type Schemas = components["schemas"]

export type FoodPage = Schemas["FoodPage"]
export type FoodSummary = Schemas["FoodSummary"]
export type FoodDetail = Schemas["FoodDetail"]
export type Facets = Schemas["CatalogFacets"]
export type Source = Schemas["SourceDetail"]
export type SourceNutrient = Schemas["SourceNutrient"]
export type Portion = Schemas["Portion"]

export type Day = Schemas["Day"]
export type Meal = Schemas["Meal"]
export type MealItem = Schemas["MealItem"]
export type MealKind = NonNullable<Meal["kind"]>
export type NutrientTotals = Schemas["NutrientTotals"]
export type Nutrient = keyof NutrientTotals

export const MEAL_KINDS: ReadonlyArray<MealKind> = [
  "breakfast",
  "lunch",
  "dinner",
  "snack",
]

/** A validation problem reported by the API for one input field. */
export type Issue = { field: string; message: string }
