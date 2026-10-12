import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
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
  kcal: { label: "kcal per day" },
} satisfies ChartConfig

const splitConfig = Object.fromEntries(
  MACROS.map((macro) => [macro.key, { label: macro.label, color: macro.color }])
) satisfies ChartConfig

/**
 * One bar per label, colored by the daily limit like the calendar. A dashed
 * line marks the limit; a null value leaves its bar out.
 */
export function KcalBars({
  data,
  limit,
  labelEvery = 1,
}: {
  data: Array<{ label: string; kcal: number | null }>
  limit: number
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
        <ReferenceLine
          y={limit}
          stroke="var(--foreground)"
          strokeOpacity={0.5}
          strokeDasharray="4 4"
        />
        <Bar dataKey="kcal" radius={4}>
          {data.map((row) => (
            <Cell
              key={row.label}
              fill={statusColor(statusFor(row.kcal, limit))}
            />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}

/** The energy split per week, as stacked percentages. Weeks without data are empty. */
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
      (split ?? []).map((part) => [
        part.key,
        Math.round(part.share * 1000) / 10,
      ])
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
