import { MacroBar } from "@/components/nutrition/macro-bar"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { formatNumber } from "@/lib/format"
import { energySplit } from "@/lib/macros"
import type { Day, Nutrient } from "@/lib/api/types"

const MACROS: Array<{ key: Nutrient; label: string; color: string }> = [
  { key: "protein_g", label: "Protein", color: "var(--macro-protein)" },
  { key: "fat_g", label: "Fat", color: "var(--macro-fat)" },
  { key: "carbs_g", label: "Carbs", color: "var(--macro-carbs)" },
  { key: "fiber_g", label: "Fiber", color: "var(--macro-fiber)" },
]

/** Measured plus estimated, as one number for charts and ratios. */
function sum(total: Day["totals"]["protein_g"]): number {
  return Number(total.measured) + Number(total.estimated)
}

/** Day totals that keep measured, estimated, and unknown apart. */
export function DayTotals({ day }: { day: Day }) {
  const kcal = day.totals.energy_kcal
  const energy = sum(kcal)
  const protein = sum(day.totals.protein_g)
  const density = energy > 0 ? (protein * 100) / energy : null
  const parts = energySplit({
    protein_g: String(protein),
    fat_g: String(sum(day.totals.fat_g)),
    carbs_g: String(sum(day.totals.carbs_g)),
    polyols_g: String(sum(day.totals.polyols_g)),
    fiber_g: String(sum(day.totals.fiber_g)),
    alcohol_g: String(sum(day.totals.alcohol_g)),
  })

  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end gap-x-3 gap-y-1">
          <div>
            <span className="font-heading text-5xl font-semibold tabular-nums">
              {formatNumber(kcal.measured, 0)}
            </span>
            <span className="ml-1 text-muted-foreground">kcal</span>
          </div>
          {Number(kcal.estimated) > 0 && (
            <span className="pb-1.5 text-sm text-muted-foreground">
              + {formatNumber(kcal.estimated, 0)} estimated
            </span>
          )}
          <div className="ml-auto flex gap-1.5 pb-1.5">
            {day.counts.unknown > 0 && (
              <Badge variant="outline">
                {day.counts.unknown} unknown{" "}
                {day.counts.unknown === 1 ? "meal" : "meals"}
              </Badge>
            )}
            {kcal.items_without_value > 0 && (
              <Badge variant="outline">lower bound</Badge>
            )}
          </div>
        </div>

        {energy > 0 && (
          <div className="flex flex-col gap-1.5">
            <MacroBar parts={parts} className="h-3" />
            <div className="text-xs text-muted-foreground">
              Where today's energy comes from
              {parts &&
                `: ${parts
                  .map(
                    (part) =>
                      `${part.label.toLowerCase()} ${formatNumber(part.share * 100, 0)}%`
                  )
                  .join(", ")}`}
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
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
              <div className="text-lg font-medium tabular-nums">
                {formatNumber(day.totals[key].measured)} g
              </div>
              {Number(day.totals[key].estimated) > 0 && (
                <div className="text-xs text-muted-foreground tabular-nums">
                  + {formatNumber(day.totals[key].estimated)} g est.
                </div>
              )}
            </div>
          ))}
          <div className="col-span-2 rounded-lg bg-secondary p-3 text-secondary-foreground sm:col-span-1">
            <div className="text-xs opacity-75">Protein / 100 kcal</div>
            <div className="text-lg font-medium tabular-nums">
              {density === null ? "–" : `${formatNumber(density)} g`}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
