import { cn } from "cn"
import { formatNumber } from "@/lib/format"
import type { EnergyPart } from "@/lib/macros"

/** A stacked bar of where the energy comes from. Never color alone: callers
 * show labels (see MacroLegend), and the bar carries an accessible summary. */
export function MacroBar({
  parts,
  className,
}: {
  parts: Array<EnergyPart> | null
  className?: string
}) {
  if (!parts) {
    return (
      <div
        className={cn("h-2 rounded-full bg-muted", className)}
        aria-label="Energy split unknown"
        role="img"
      />
    )
  }
  const summary = parts
    .map((part) => `${part.label} ${formatNumber(part.share * 100, 0)}%`)
    .join(", ")
  return (
    <div
      role="img"
      aria-label={`Energy from ${summary}`}
      // 2px surface gaps between segments; rounded ends only at the outside.
      className={cn("flex h-2 gap-0.5 overflow-hidden rounded-full", className)}
    >
      {parts.map((part) => (
        <div
          key={part.key}
          title={`${part.label}: ${formatNumber(part.share * 100, 0)}% of energy`}
          className="h-full min-w-1"
          style={{ width: `${part.share * 100}%`, background: part.color }}
        />
      ))}
    </div>
  )
}

/** Labeled values for the macros, each with its color dot. */
export function MacroLegend({
  parts,
  mode = "grams",
  className,
}: {
  parts: Array<EnergyPart> | null
  mode?: "grams" | "share"
  className?: string
}) {
  if (!parts) return null
  return (
    <ul className={cn("flex flex-wrap gap-x-3 gap-y-1 text-xs", className)}>
      {parts.map((part) => (
        <li key={part.key} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="size-2 rounded-full"
            style={{ background: part.color }}
          />
          <span className="text-muted-foreground">{part.label}</span>
          <span className="font-medium tabular-nums">
            {mode === "grams"
              ? `${formatNumber(part.grams)} g`
              : `${formatNumber(part.share * 100, 0)}%`}
          </span>
        </li>
      ))}
    </ul>
  )
}
