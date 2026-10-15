import { Card, CardContent } from "@/components/ui/card"
import { statusColor, statusFor } from "@/lib/calendar"
import { formatNumber } from "@/lib/format"
import type { Day, Nutrient } from "@/lib/api/types"

const MACROS: Array<{ key: Nutrient; label: string; color: string }> = [
  { key: "protein_g", label: "Protein", color: "var(--macro-protein)" },
  { key: "fat_g", label: "Fat", color: "var(--macro-fat)" },
  { key: "carbs_g", label: "Carbs", color: "var(--macro-carbs)" },
  { key: "fiber_g", label: "Fiber", color: "var(--macro-fiber)" },
]

/** Measured plus estimated: estimates count as normal amounts in the day's totals. */
function sum(total: Day["totals"]["protein_g"]): number {
  return Number(total.measured) + Number(total.estimated)
}

/**
 * The day's kcal against the daily limit. The bar fills as kcal are eaten, on a
 * scale that runs to the limit plus the tolerance, so overshoots stay visible.
 */
function CalorieBar({ day }: { day: Day }) {
  const kcal = sum(day.totals.energy_kcal)
  const limit = day.daily_kcal_limit
  const tolerance = day.kcal_tolerance
  const status = day.incomplete ? "none" : statusFor(kcal, limit, tolerance)
  const scale = Math.max(limit + tolerance, kcal, 1)
  const fill = (kcal / scale) * 100
  const marker = (limit / scale) * 100

  let message: string
  if (day.incomplete) {
    message = "Incomplete day: not judged against your limit."
  } else if (kcal === 0) {
    message = "Nothing eaten yet."
  } else if (status === "within") {
    message = `${formatNumber(limit - kcal, 0)} kcal left.`
  } else if (status === "caution") {
    message = `${formatNumber(kcal - limit, 0)} kcal over the limit, within the tolerance.`
  } else {
    message = `${formatNumber(kcal - limit, 0)} kcal over the limit, beyond the tolerance.`
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-heading text-3xl font-semibold tabular-nums">
          {formatNumber(kcal, 0)}
          <span className="ml-1 text-base font-normal text-muted-foreground">
            kcal
          </span>
        </span>
        <span className="text-sm text-muted-foreground tabular-nums">
          of {formatNumber(limit, 0)} limit
        </span>
      </div>
      <div
        role="progressbar"
        aria-label="Calories eaten today"
        aria-valuemin={0}
        aria-valuemax={Math.round(scale)}
        aria-valuenow={Math.round(kcal)}
        aria-valuetext={message}
        className="relative h-3 overflow-hidden rounded-full bg-muted"
      >
        <div
          className="h-full rounded-full transition-[width] duration-300"
          style={{ width: `${fill}%`, background: statusColor(status) }}
        />
        <div
          aria-hidden
          className="absolute inset-y-0 w-0.5 bg-foreground/60"
          style={{ left: `${marker}%` }}
        />
      </div>
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  )
}

/** The day's kcal against the limit, then its protein, fat, carbs and fiber. */
export function DayTotals({ day }: { day: Day }) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <CalorieBar day={day} />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {MACROS.map(({ key, label, color }) => (
            <div key={key} className="rounded-lg bg-muted/60 p-3">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span
                  aria-hidden
                  className="size-2 rounded-full"
                  style={{ background: color }}
                />
                {label}
              </div>
              <div className="text-2xl font-medium tabular-nums">
                {formatNumber(sum(day.totals[key]))} g
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
