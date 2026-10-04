import { FoodPicker } from "@/components/food-picker"
import { ItemRow, newDraft } from "@/components/log/meal-sheet"
import type { ItemDraft } from "@/components/log/meal-sheet"

/** Edit a list of catalog foods with amounts or label portions. */
export function IngredientEditor({
  items,
  onChange,
}: {
  items: Array<ItemDraft>
  onChange: (items: Array<ItemDraft>) => void
}) {
  return (
    <div className="flex flex-col gap-2">
      {items.map((item) => (
        <ItemRow
          key={item.key}
          item={item}
          onChange={(changed) =>
            onChange(
              items.map((other) => (other.key === item.key ? changed : other))
            )
          }
          onRemove={() =>
            onChange(items.filter((other) => other.key !== item.key))
          }
        />
      ))}
      <FoodPicker
        onPick={(food) =>
          onChange([
            ...items,
            newDraft({
              slug: food.slug,
              name: food.name,
              unit: food.source?.reference_unit ?? "g",
            }),
          ])
        }
      />
    </div>
  )
}
