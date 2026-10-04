import { MacroBar, MacroLegend } from "@/components/nutrition/macro-bar"
import { formatNumber } from "@/lib/format"
import { energySplit, totalOf } from "@/lib/macros"
import { cn } from "@/lib/utils"
import type { NutrientTotals } from "@/lib/api/types"

/** One portion's calories, protein, and where the energy comes from. */
export function PortionNutrition({
  perPortion,
  compact = false,
  className,
}: {
  perPortion: NutrientTotals
  compact?: boolean
  className?: string
}) {
  const kcal = totalOf(perPortion.energy_kcal)
  const protein = totalOf(perPortion.protein_g)
  const parts = energySplit({
    protein_g: String(protein),
    fat_g: String(totalOf(perPortion.fat_g)),
    carbs_g: String(totalOf(perPortion.carbs_g)),
    polyols_g: String(totalOf(perPortion.polyols_g)),
    fiber_g: String(totalOf(perPortion.fiber_g)),
    alcohol_g: String(totalOf(perPortion.alcohol_g)),
  })
  const partial = perPortion.energy_kcal.items_without_value > 0
  const estimated = Number(perPortion.energy_kcal.estimated) > 0

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span>
          <strong
            className={cn(
              "font-heading tabular-nums",
              compact ? "text-lg" : "text-2xl"
            )}
          >
            {estimated ? "~" : ""}
            {formatNumber(kcal, 0)}
            {partial ? "+" : ""}
          </strong>{" "}
          <span className="text-sm text-muted-foreground">kcal/portion</span>
        </span>
        <span className="text-sm">
          <strong className="tabular-nums">{formatNumber(protein)} g</strong>{" "}
          <span className="text-muted-foreground">protein</span>
        </span>
        {kcal > 0 && (
          <span className="text-sm">
            <strong className="tabular-nums">
              {formatNumber((protein * 100) / kcal)} g
            </strong>{" "}
            <span className="text-muted-foreground">per 100 kcal</span>
          </span>
        )}
      </div>
      <MacroBar parts={parts} />
      {!compact && <MacroLegend parts={parts} />}
      {partial && (
        <p className="text-xs text-muted-foreground">
          {perPortion.energy_kcal.items_without_value} ingredients have no
          energy value; the total is a lower bound.
        </p>
      )}
    </div>
  )
}
