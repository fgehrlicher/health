import { formatNumber } from "@/lib/format"
import type { EnergyPart } from "@/lib/macros"

/**
 * What 100 g of a food is made of: macros by weight, then water, then the rest
 * (minerals, unknown or unlisted parts). Only for a 100 g basis.
 */
export function CompositionBar({
  parts,
  water,
}: {
  parts: Array<EnergyPart>
  water: number | null
}) {
  const macros = parts.filter((part) => part.grams > 0)
  const known = macros.reduce((sum, part) => sum + part.grams, 0) + (water ?? 0)
  const rest = Math.max(0, 100 - known)
  const segments = [
    ...macros.map((part) => ({
      key: part.key,
      label: part.label,
      grams: part.grams,
      color: part.color,
    })),
    ...(water !== null && water > 0
      ? [
          {
            key: "water",
            label: "Water",
            grams: water,
            color: "var(--macro-rest)",
          },
        ]
      : []),
    ...(rest > 0.5
      ? [
          {
            key: "rest",
            label: water === null ? "Water & other" : "Other",
            grams: rest,
            color: "transparent",
          },
        ]
      : []),
  ]

  return (
    <div className="flex flex-col gap-3">
      <div
        role="img"
        aria-label={segments
          .map((segment) => `${segment.label} ${formatNumber(segment.grams)} g`)
          .join(", ")}
        className="flex h-5 gap-0.5 overflow-hidden rounded-md"
      >
        {segments.map((segment) => (
          <div
            key={segment.key}
            title={`${segment.label}: ${formatNumber(segment.grams)} g`}
            className={
              segment.key === "rest"
                ? "h-full rounded-sm border border-dashed border-border"
                : "h-full min-w-1 rounded-sm"
            }
            style={{
              width: `${Math.min(segment.grams, 100)}%`,
              background: segment.color,
            }}
          />
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {segments.map((segment) => (
          <li key={segment.key} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className={
                segment.key === "rest"
                  ? "size-2 rounded-full border border-dashed border-muted-foreground"
                  : "size-2 rounded-full"
              }
              style={{ background: segment.color }}
            />
            <span className="text-muted-foreground">{segment.label}</span>
            <span className="font-medium tabular-nums">
              {formatNumber(segment.grams)} g
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
