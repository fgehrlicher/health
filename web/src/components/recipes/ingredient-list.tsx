import { Link } from "@tanstack/react-router"
import { formatNumber } from "@/lib/format"
import type { Amount } from "@/lib/api/types"

/** Ingredients with their amounts and calories for the whole pot. */
export function IngredientList({ items }: { items: Array<Amount> }) {
  return (
    <ul className="flex flex-col gap-1.5 text-sm">
      {items.map((item) => (
        <li key={item.id} className="flex items-baseline gap-2">
          <Link
            to="/foods/$slug"
            params={{ slug: item.food }}
            className="min-w-0 truncate hover:underline"
          >
            {item.food_name}
          </Link>
          <span className="shrink-0 text-muted-foreground tabular-nums">
            {item.estimated ? "~" : ""}
            {formatNumber(item.amount)} {item.unit}
          </span>
          <span className="ml-auto shrink-0 text-muted-foreground tabular-nums">
            {formatNumber(item.nutrition.energy_kcal, 0)} kcal
          </span>
        </li>
      ))}
    </ul>
  )
}
