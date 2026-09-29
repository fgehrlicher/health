// Macronutrients: fixed colors (see styles.css) and energy from EU factors.
// Order matters: it is the stacking order the colors were validated for.

export type MacroKey = "protein" | "fat" | "carbs" | "fiber" | "alcohol"

export const MACROS: ReadonlyArray<{
  key: MacroKey
  label: string
  /** kcal per gram (EU Regulation 1169/2011, Annex XIV). */
  kcalPerGram: number
  color: string
}> = [
  {
    key: "protein",
    label: "Protein",
    kcalPerGram: 4,
    color: "var(--macro-protein)",
  },
  {
    key: "fat",
    label: "Fat",
    kcalPerGram: 9,
    color: "var(--macro-fat)",
  },
  {
    key: "carbs",
    label: "Carbs",
    kcalPerGram: 4,
    color: "var(--macro-carbs)",
  },
  {
    key: "fiber",
    label: "Fiber",
    kcalPerGram: 2,
    color: "var(--macro-fiber)",
  },
  {
    key: "alcohol",
    label: "Alcohol",
    kcalPerGram: 7,
    color: "var(--macro-alcohol)",
  },
]

/** Nutrition fields as the API sends them: decimal strings, null if unknown. */
export type MacroValues = {
  protein_g?: string | null
  fat_g?: string | null
  carbs_g?: string | null
  polyols_g?: string | null
  fiber_g?: string | null
  alcohol_g?: string | null
}

export type EnergyPart = {
  key: MacroKey
  label: string
  color: string
  grams: number
  kcal: number
  /** Share of the energy from all known macros, 0–1. */
  share: number
}

function grams(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

/**
 * Where the energy comes from. Shares are relative to the energy of the known
 * macros, so they add up to 100%. Null when protein, fat, and carbs are all
 * unknown. Polyols within carbs count 2.4 kcal/g, as on EU labels.
 */
export function energySplit(values: MacroValues): Array<EnergyPart> | null {
  const protein = grams(values.protein_g)
  const fat = grams(values.fat_g)
  const carbs = grams(values.carbs_g)
  if (protein === null && fat === null && carbs === null) return null
  const polyols = Math.min(grams(values.polyols_g) ?? 0, carbs ?? 0)
  const amounts: Record<MacroKey, number> = {
    protein: protein ?? 0,
    fat: fat ?? 0,
    carbs: carbs ?? 0,
    fiber: grams(values.fiber_g) ?? 0,
    alcohol: grams(values.alcohol_g) ?? 0,
  }
  const parts = MACROS.map((macro) => ({
    key: macro.key,
    label: macro.label,
    color: macro.color,
    grams: amounts[macro.key],
    kcal:
      macro.key === "carbs"
        ? (amounts.carbs - polyols) * 4 + polyols * 2.4
        : amounts[macro.key] * macro.kcalPerGram,
  }))
  const total = parts.reduce((sum, part) => sum + part.kcal, 0)
  if (total <= 0) return null
  return parts
    .filter((part) => part.kcal > 0)
    .map((part) => ({ ...part, share: part.kcal / total }))
}

/** EU reference intakes for adults (Regulation 1169/2011, Annex XIII), in
 * the units of the API's nutrients table. */
export const REFERENCE_INTAKE: Record<string, number> = {
  vitamin_a: 800,
  vitamin_d: 5,
  vitamin_e: 12,
  vitamin_k: 75,
  vitamin_c: 80,
  thiamin: 1.1,
  riboflavin: 1.4,
  niacin: 16,
  vitamin_b6: 1.4,
  folate: 200,
  vitamin_b12: 2.5,
  potassium: 2000,
  calcium: 800,
  magnesium: 375,
  phosphorus: 700,
  iron: 14,
  zinc: 10,
  iodine: 150,
}
