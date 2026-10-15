import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  XAxis,
  YAxis,
} from "recharts"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"
import type { ChartConfig } from "@/components/ui/chart"
import { statusColor, statusFor } from "@/lib/calendar"
import { formatNumber } from "@/lib/format"
import { MACROS } from "@/lib/macros"
import type { EnergyPart } from "@/lib/macros"

const kcalConfig = {
  kcal: { label: "kcal" },
} satisfies ChartConfig

const trendConfig = {
  kcal: { label: "kcal" },
  average: { label: "7-day average" },
} satisfies ChartConfig

const splitConfig = Object.fromEntries(
  MACROS.map((macro) => [macro.key, { label: macro.label, color: macro.color }])
) satisfies ChartConfig

/** The limit (dashed) and the edge of the tolerance above it (dotted). */
function GoalLines({ limit, tolerance }: { limit: number; tolerance: number }) {
  return (
    <>
      <ReferenceLine
        y={limit}
        stroke="var(--foreground)"
        strokeOpacity={0.5}
        strokeDasharray="4 4"
      />
      <ReferenceLine
        y={limit + tolerance}
        stroke="var(--caution)"
        strokeDasharray="1 4"
      />
    </>
  )
}

/**
 * One bar per label, colored like the calendar: green within the limit, yellow
 * up to the tolerance above it, red beyond. A null value leaves its bar out.
 */
export function KcalBars({
  data,
  limit,
  tolerance,
  labelEvery = 1,
}: {
  data: Array<{ label: string; kcal: number | null }>
  limit: number
  tolerance: number
  /** Show every nth label, so long series stay readable on a phone. */
  labelEvery?: number
}) {
  return (
    <ChartContainer config={kcalConfig} className="aspect-auto h-48 w-full">
      <BarChart data={data} margin={{ left: 0, right: 4, top: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tickMargin={6}
          interval={labelEvery - 1}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          width={44}
          tickFormatter={(value: number) => formatNumber(value, 0)}
        />
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              formatter={(value) => `${formatNumber(Number(value), 0)} kcal`}
            />
          }
        />
        <GoalLines limit={limit} tolerance={tolerance} />
        <Bar dataKey="kcal" radius={4}>
          {data.map((row) => (
            <Cell
              key={row.label}
              fill={statusColor(statusFor(row.kcal, limit, tolerance))}
            />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}

/**
 * Daily kcal as bars colored like the calendar, with the trailing 7-day average
 * as a line over them.
 */
export function KcalTrend({
  data,
  limit,
  tolerance,
  labelEvery = 1,
}: {
  data: Array<{ label: string; kcal: number | null; average: number | null }>
  limit: number
  tolerance: number
  labelEvery?: number
}) {
  return (
    <ChartContainer config={trendConfig} className="aspect-auto h-56 w-full">
      <ComposedChart data={data} margin={{ left: 0, right: 4, top: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tickMargin={6}
          interval={labelEvery - 1}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          width={44}
          tickFormatter={(value: number) => formatNumber(value, 0)}
        />
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              formatter={(value, name) => (
                <span className="flex w-full justify-between gap-3">
                  <span className="text-muted-foreground">
                    {name === "average" ? "7-day average" : "kcal"}
                  </span>
                  <span className="font-medium tabular-nums">
                    {formatNumber(Number(value), 0)} kcal
                  </span>
                </span>
              )}
            />
          }
        />
        <GoalLines limit={limit} tolerance={tolerance} />
        <Bar dataKey="kcal" radius={3}>
          {data.map((row) => (
            <Cell
              key={row.label}
              fill={statusColor(statusFor(row.kcal, limit, tolerance))}
            />
          ))}
        </Bar>
        <Line
          dataKey="average"
          type="monotone"
          stroke="var(--foreground)"
          strokeWidth={2}
          dot={false}
          connectNulls
        />
      </ComposedChart>
    </ChartContainer>
  )
}

/** The energy split per period, as stacked percentages. Empty periods leave a gap. */
export function SplitBars({
  data,
  labelEvery = 1,
}: {
  data: Array<{ label: string; split: Array<EnergyPart> | null }>
  labelEvery?: number
}) {
  const rows = data.map(({ label, split }) => ({
    label,
    ...Object.fromEntries(
      (split ?? []).map((part) => [part.key, part.share * 100])
    ),
  }))
  return (
    <ChartContainer config={splitConfig} className="aspect-auto h-48 w-full">
      <BarChart data={rows} margin={{ left: 0, right: 4, top: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tickMargin={6}
          interval={labelEvery - 1}
        />
        <YAxis
          domain={[0, 100]}
          tickLine={false}
          axisLine={false}
          width={44}
          tickFormatter={(value: number) => `${value}%`}
        />
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              formatter={(value, name) => (
                <span className="flex w-full justify-between gap-3">
                  <span className="text-muted-foreground">
                    {MACROS.find((macro) => macro.key === name)?.label}
                  </span>
                  <span className="font-medium tabular-nums">
                    {formatNumber(Number(value), 0)}%
                  </span>
                </span>
              )}
            />
          }
        />
        {MACROS.map((macro, index) => (
          <Bar
            key={macro.key}
            dataKey={macro.key}
            stackId="split"
            fill={macro.color}
            radius={index === MACROS.length - 1 ? [4, 4, 0, 0] : 0}
          />
        ))}
      </BarChart>
    </ChartContainer>
  )
}
