import { Link } from "@tanstack/react-router"
import { Badge } from "@/components/ui/badge"
import { clockTime, dayLabel, formatNumber } from "@/lib/format"
import { totalOf } from "@/lib/macros"
import type { CookSummary } from "@/lib/api/types"

/** One entry of the cooking log. */
export function CookRow({
  cook,
  showName = true,
}: {
  cook: CookSummary
  showName?: boolean
}) {
  const left = Number(cook.portions_left)
  return (
    <Link
      to="/cooks/$id"
      params={{ id: cook.id }}
      className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2.5 text-sm transition-colors hover:bg-muted/60"
    >
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate font-medium">
          {showName ? cook.name : dayLabel(cook.cooked_at.slice(0, 10))}
          {cook.version !== null && (
            <span className="ml-1.5 font-normal text-muted-foreground">
              v{cook.version}
            </span>
          )}
        </span>
        <span className="truncate text-xs text-muted-foreground">
          {showName ? `${dayLabel(cook.cooked_at.slice(0, 10))}, ` : ""}
          {clockTime(cook.cooked_at)}
          {cook.note ? ` · ${cook.note}` : ""}
        </span>
      </div>
      <Badge variant={left > 0 ? "secondary" : "outline"}>
        {formatNumber(left)}/{formatNumber(cook.portions)} left
      </Badge>
      <span className="w-20 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
        {formatNumber(totalOf(cook.per_portion.energy_kcal), 0)} kcal
      </span>
    </Link>
  )
}
