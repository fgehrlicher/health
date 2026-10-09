// Food names for display: German first, the catalog (English) name underneath.
// BLS foods have a German name on their source; branded products have none, so
// their name is shown once.

export type Names = { primary: string; secondary: string | null }

/** A catalog food, as the API returns it (name_de is null for products). */
export function foodNames(food: {
  name: string
  name_de?: string | null
}): Names {
  return food.name_de
    ? { primary: food.name_de, secondary: food.name }
    : { primary: food.name, secondary: null }
}

/** A meal, recipe or cook item: the same rule with the item's own fields. */
export function itemNames(item: {
  food_name: string
  food_name_de?: string | null
}): Names {
  return item.food_name_de
    ? { primary: item.food_name_de, secondary: item.food_name }
    : { primary: item.food_name, secondary: null }
}
