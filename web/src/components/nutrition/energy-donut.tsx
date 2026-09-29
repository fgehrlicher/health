import { Label, Pie, PieChart } from "recharts"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"
import { formatNumber } from "@/lib/format"
import { MACROS } from "@/lib/macros"
import type { ChartConfig } from "@/components/ui/chart"
import type { EnergyPart } from "@/lib/macros"

const config = Object.fromEntries(
  MACROS.map((macro) => [macro.key, { label: macro.label, color: macro.color }])
) satisfies ChartConfig

/** Where a food's energy comes from, with the total in the center. */
export function EnergyDonut({ parts }: { parts: Array<EnergyPart> }) {
  const total = parts.reduce((sum, part) => sum + part.kcal, 0)
  const data = parts.map((part) => ({
    key: part.key,
    kcal: Math.round(part.kcal),
    fill: part.color,
  }))

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:gap-6">
      <ChartContainer config={config} className="aspect-square h-48 shrink-0">
        <PieChart>
          <ChartTooltip
            cursor={false}
            content={
              <ChartTooltipContent
                hideLabel
                nameKey="key"
                formatter={(value, name) => {
                  const part = parts.find((item) => item.key === name)
                  return (
                    <span className="flex w-full justify-between gap-3">
                      <span className="text-muted-foreground">
                        {part?.label}
                      </span>
                      <span className="font-medium tabular-nums">
                        {formatNumber(Number(value), 0)} kcal ·{" "}
                        {formatNumber((part?.share ?? 0) * 100, 0)}%
                      </span>
                    </span>
                  )
                }}
              />
            }
          />
          <Pie
            data={data}
            dataKey="kcal"
            nameKey="key"
            innerRadius="62%"
            outerRadius="100%"
            paddingAngle={2}
            cornerRadius={4}
            stroke="var(--card)"
            strokeWidth={2}
            isAnimationActive={false}
          >
            <Label
              content={({ viewBox }) => {
                if (!viewBox || !("cx" in viewBox)) return null
                return (
                  <text textAnchor="middle" dominantBaseline="middle">
                    <tspan
                      x={viewBox.cx}
                      y={viewBox.cy}
                      className="fill-foreground font-heading text-2xl font-semibold"
                    >
                      {formatNumber(total, 0)}
                    </tspan>
                    <tspan
                      x={viewBox.cx}
                      y={viewBox.cy + 20}
                      className="fill-muted-foreground text-xs"
                    >
                      kcal
                    </tspan>
                  </text>
                )
              }}
            />
          </Pie>
        </PieChart>
      </ChartContainer>

      <div className="flex w-full flex-col gap-2">
        {parts.map((part) => (
          <div key={part.key} className="flex items-center gap-2 text-sm">
            <span
              aria-hidden
              className="size-2.5 shrink-0 rounded-full"
              style={{ background: part.color }}
            />
            <span className="flex-1">{part.label}</span>
            <span className="text-muted-foreground tabular-nums">
              {formatNumber(part.kcal, 0)} kcal
            </span>
            <span className="w-12 text-right font-medium tabular-nums">
              {formatNumber(part.share * 100, 0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
