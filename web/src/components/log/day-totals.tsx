import { Card, CardContent } from "@/components/ui/card"
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

/** The day's protein, fat, carbs and fiber. Each meal shows its own calories. */
export function DayTotals({ day }: { day: Day }) {
  return (
    <Card>
      <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-4">
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
      </CardContent>
    </Card>
  )
}
