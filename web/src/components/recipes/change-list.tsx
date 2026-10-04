import { ArrowRightIcon, MinusIcon, PlusIcon } from "lucide-react"
import { formatNumber } from "@/lib/format"
import type { Amount, Change } from "@/lib/api/types"

/** Foods whose amount differs between two ingredient lists, per food source. */
export function diffAmounts(
  before: Array<Amount>,
  after: Array<Amount>
): Array<Change> {
  const total = (items: Array<Amount>) => {
    const sums = new Map<number, { item: Amount; amount: number }>()
    for (const item of items) {
      const entry = sums.get(item.source_id)
      sums.set(item.source_id, {
        item,
        amount: (entry?.amount ?? 0) + Number(item.amount),
      })
    }
    return sums
  }
  const planned = total(before)
  const actual = total(after)
  const sources = [
    ...planned.keys(),
    ...[...actual.keys()].filter((source) => !planned.has(source)),
  ]
  return sources.flatMap((source) => {
    const was = planned.get(source)
    const now = actual.get(source)
    if (was && now && was.amount === now.amount) return []
    const item = (now ?? was)!.item
    return [
      {
        food: item.food,
        food_name: item.food_name,
        unit: item.unit,
        planned: was ? String(was.amount) : null,
        actual: now ? String(now.amount) : null,
      },
    ]
  })
}

/** Added, removed, and changed amounts, e.g. "Coconut milk 250 → 400 g". */
export function ChangeList({ changes }: { changes: Array<Change> }) {
  return (
    <ul className="flex flex-col gap-1 text-sm">
      {changes.map((change) => (
        <li key={change.food} className="flex items-center gap-2">
          {change.planned === null ? (
            <PlusIcon aria-label="Added" className="size-3.5 text-primary" />
          ) : change.actual === null ? (
            <MinusIcon
              aria-label="Left out"
              className="size-3.5 text-destructive"
            />
          ) : (
            <ArrowRightIcon
              aria-label="Changed"
              className="size-3.5 text-muted-foreground"
            />
          )}
          <span className="min-w-0 truncate">{change.food_name}</span>
          <span className="ml-auto shrink-0 text-muted-foreground tabular-nums">
            {change.planned !== null && change.actual !== null
              ? `${formatNumber(change.planned)} → ${formatNumber(change.actual)}`
              : formatNumber(change.planned ?? change.actual)}{" "}
            {change.unit}
          </span>
        </li>
      ))}
    </ul>
  )
}
