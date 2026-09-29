import { formatNumber } from "@/lib/format"
import { REFERENCE_INTAKE } from "@/lib/macros"
import type { SourceNutrient } from "@/lib/api/types"

/**
 * Vitamins and minerals as a share of the EU daily reference intake, largest
 * first. One series in the primary color; the value is always written out.
 */
export function ReferenceIntakeBars({
  nutrients,
  basis,
}: {
  nutrients: Array<SourceNutrient>
  basis: string
}) {
  const rows = nutrients
    .filter((nutrient) => nutrient.key in REFERENCE_INTAKE)
    .map((nutrient) => ({
      ...nutrient,
      percent: (Number(nutrient.amount) / REFERENCE_INTAKE[nutrient.key]) * 100,
    }))
    .sort((a, b) => b.percent - a.percent)

  if (rows.length === 0) return null
  return (
    <figure className="flex flex-col gap-2">
      <figcaption className="text-xs text-muted-foreground">
        Share of the EU daily reference intake {basis}. The line marks 100%.
      </figcaption>
      <ul className="flex flex-col gap-1.5">
        {rows.map((row) => (
          <li
            key={row.key}
            className="grid grid-cols-[minmax(6rem,9rem)_1fr_4.5rem] items-center gap-3 text-sm"
            title={`${row.name}: ${formatNumber(row.amount, 3)} ${row.unit} (${formatNumber(row.percent, 0)}% of ${formatNumber(REFERENCE_INTAKE[row.key])} ${row.unit})`}
          >
            <span className="truncate">{row.name.replace(/ \(.*\)$/, "")}</span>
            <span className="relative h-2.5 rounded-full bg-muted">
              <span
                className="absolute inset-y-0 left-0 rounded-full bg-primary"
                style={{ width: `${Math.min(row.percent, 100)}%` }}
              />
              {/* 100% marker, visible when the bar reaches it. */}
              <span className="absolute inset-y-[-3px] right-0 w-px bg-foreground/40" />
            </span>
            <span className="text-right tabular-nums">
              {row.upper_bound ? "< " : ""}
              {formatNumber(row.percent, 0)}%
            </span>
          </li>
        ))}
      </ul>
    </figure>
  )
}
