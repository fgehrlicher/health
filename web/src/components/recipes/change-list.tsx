import {
  ArrowLeftRightIcon,
  ArrowRightIcon,
  MinusIcon,
  PlusIcon,
} from "lucide-react"
import { formatNumber } from "@/lib/format"
import type { Change } from "@/lib/api/types"

type Part = Change["planned"][number]

const names = (parts: Array<Part>) =>
  parts.map((part) => part.food_name).join(" + ")
const amounts = (parts: Array<Part>) =>
  parts.map((part) => `${formatNumber(part.amount)} ${part.unit}`).join(" + ")

/** "300 → 500 g", "300 g → 300 ml", or one side's amounts. */
function fromTo(planned: Array<Part>, actual: Array<Part>): string {
  if (planned.length === 0) return amounts(actual)
  if (actual.length === 0 || amounts(planned) === amounts(actual)) {
    return amounts(actual.length ? actual : planned)
  }
  const [was, now] = [planned[0], actual[0]]
  if (planned.length === 1 && actual.length === 1 && was.unit === now.unit) {
    return `${formatNumber(was.amount)} → ${formatNumber(now.amount)} ${now.unit}`
  }
  return `${amounts(planned)} → ${amounts(actual)}`
}

/**
 * Added, left out, changed, and swapped ingredients, e.g. "Coconut milk
 * 250 → 400 g" or a generic soy drink replaced by a brand's.
 */
export function ChangeList({ changes }: { changes: Array<Change> }) {
  return (
    <ul className="flex flex-col gap-1 text-sm">
      {changes.map((change) => {
        const { planned, actual } = change
        const key = [...planned, ...actual].map((part) => part.food).join()
        const swapped =
          planned.length > 0 &&
          actual.length > 0 &&
          names(planned) !== names(actual)
        let icon = (
          <ArrowRightIcon
            aria-label="Changed"
            className="size-3.5 shrink-0 text-muted-foreground"
          />
        )
        if (planned.length === 0) {
          icon = (
            <PlusIcon
              aria-label="Added"
              className="size-3.5 shrink-0 text-primary"
            />
          )
        } else if (actual.length === 0) {
          icon = (
            <MinusIcon
              aria-label="Left out"
              className="size-3.5 shrink-0 text-destructive"
            />
          )
        } else if (swapped) {
          icon = (
            <ArrowLeftRightIcon
              aria-label="Swapped"
              className="size-3.5 shrink-0 text-primary"
            />
          )
        }
        const shown = actual.length > 0 ? actual : planned
        return (
          <li key={key} className="flex items-start gap-2">
            <span className="pt-0.5">{icon}</span>
            <span className="flex min-w-0 flex-col">
              <span className="truncate">{names(shown)}</span>
              {swapped && (
                <span className="truncate text-xs text-muted-foreground">
                  instead of {names(planned)}
                </span>
              )}
            </span>
            <span className="ml-auto shrink-0 text-muted-foreground tabular-nums">
              {fromTo(planned, actual)}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
