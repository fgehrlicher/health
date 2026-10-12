import { useSuspenseQuery } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { cn } from "cn"
import { useEffect, useMemo, useRef, useState } from "react"
import type { ReactNode } from "react"
import { EnergyDonut } from "@/components/nutrition/energy-donut"
import { MacroLegend } from "@/components/nutrition/macro-bar"
import { KcalBars, SplitBars } from "@/components/stats/charts"
import { IncompleteSwitch } from "@/components/stats/incomplete-switch"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  CALENDAR_WEEKS,
  LEVELS,
  calendarRange,
  calendarWeeks,
  levelColor,
  levelFor,
  levelRanges,
} from "@/lib/calendar"
import type { CalendarCell } from "@/lib/calendar"
import { dayLabel, formatNumber, today } from "@/lib/format"
import { calendarQuery } from "@/lib/queries"
import {
  WEEKDAYS,
  amountOf,
  average,
  countedDays,
  energySplitOf,
  weekdayAverages,
  weeklyStats,
} from "@/lib/stats"

/** Weeks in the charts that show a week per bar; the heatmap shows all of them. */
const CHART_WEEKS = 26

const WEEK_LABEL = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  timeZone: "UTC",
})
const MONTHS = new Intl.DateTimeFormat("en-GB", {
  month: "short",
  timeZone: "UTC",
})

export const Route = createFileRoute("/stats")({
  loader: ({ context }) => {
    const { start, end } = calendarRange(calendarWeeks())
    return context.queryClient.ensureQueryData(calendarQuery(start, end))
  },
  component: StatsPage,
})

function StatsPage() {
  const weeks = useMemo(() => calendarWeeks(), [])
  const { start, end } = calendarRange(weeks)
  const { data } = useSuspenseQuery(calendarQuery(start, end))
  const days = data.days
  const byDate = useMemo(
    () => new Map(days.map((day) => [day.date, day])),
    [days]
  )
  const counted = countedDays(days)
  const incompleteCount = days.filter((day) => day.incomplete).length
  const [selected, setSelected] = useState(today)
  const scroller = useRef<HTMLDivElement>(null)

  // The latest weeks are the ones worth seeing, so start at the right edge.
  useEffect(() => {
    const element = scroller.current
    if (element) element.scrollLeft = element.scrollWidth
  }, [])

  const averageKcal = average(counted.map((day) => amountOf(day.energy_kcal)))
  const averageProtein = average(counted.map((day) => amountOf(day.protein_g)))
  const overall = energySplitOf(counted)
  const weekly = weeklyStats(weeks.slice(-CHART_WEEKS), days)
  const selectedDay = byDate.get(selected)
  const energyOf = (date: string): number | null => {
    const day = byDate.get(date)
    return day ? amountOf(day.energy_kcal) : null
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-heading text-2xl font-semibold">Stats</h1>
        <p className="text-sm text-muted-foreground">
          The last {CALENDAR_WEEKS} weeks. Incomplete days stay on the calendar,
          but the numbers leave them out.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Stat label="Days counted" value={String(counted.length)} />
        <Stat label="Incomplete days" value={String(incompleteCount)} />
        <Stat
          label="Average kcal"
          value={
            averageKcal === null ? "–" : `${formatNumber(averageKcal, 0)} kcal`
          }
        />
        <Stat
          label="Average protein"
          value={
            averageProtein === null ? "–" : `${formatNumber(averageProtein)} g`
          }
        />
      </div>

      <Card>
        <CardContent className="flex flex-col gap-4">
          <div className="flex gap-2">
            <div
              aria-hidden
              className="flex shrink-0 flex-col gap-1 pt-[22px] text-xs leading-4 text-muted-foreground"
            >
              {WEEKDAYS.map((name, index) => (
                <span key={name} className="h-4">
                  {index % 2 === 0 ? name : ""}
                </span>
              ))}
            </div>
            <div ref={scroller} className="min-w-0 flex-1 overflow-x-auto pb-1">
              {/* The padding keeps the outline of the selected day inside the scroll area. */}
              <div className="flex w-max flex-col gap-1 p-0.5">
                <div className="flex gap-1 text-xs leading-4 text-muted-foreground">
                  {weeks.map((week, index) => (
                    <span
                      key={week[0].date}
                      className="w-4 shrink-0 whitespace-nowrap"
                    >
                      {monthName(week, index)}
                    </span>
                  ))}
                </div>
                <div className="flex gap-1">
                  {weeks.map((week) => (
                    <div key={week[0].date} className="flex flex-col gap-1">
                      {week.map((cell) =>
                        cell.future ? (
                          <span key={cell.date} className="size-4" />
                        ) : (
                          <DayCell
                            key={cell.date}
                            date={cell.date}
                            energy={energyOf(cell.date)}
                            incomplete={
                              byDate.get(cell.date)?.incomplete ?? false
                            }
                            active={cell.date === selected}
                            onSelect={() => setSelected(cell.date)}
                          />
                        )
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <Legend />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col gap-3">
          <h2 className="font-heading font-semibold">{dayLabel(selected)}</h2>
          {selectedDay ? (
            <>
              <div>
                <span className="font-heading text-4xl font-semibold tabular-nums">
                  {formatNumber(amountOf(selectedDay.energy_kcal), 0)}
                </span>
                <span className="ml-1 text-muted-foreground">kcal</span>
              </div>
              <p className="text-sm text-muted-foreground">
                {selectedDay.meals} {selectedDay.meals === 1 ? "meal" : "meals"}
                {selectedDay.unknown_meals > 0 &&
                  ` · ${selectedDay.unknown_meals} unknown, not counted`}
              </p>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              No meals logged this day.
            </p>
          )}
          <IncompleteSwitch
            date={selected}
            incomplete={selectedDay?.incomplete ?? false}
          />
          <Button
            variant="outline"
            nativeButton={false}
            render={<Link to="/" search={{ date: selected }} />}
          >
            Open this day
          </Button>
        </CardContent>
      </Card>

      <ChartCard
        title="Calories per day, by week"
        note={`Average of counted days, the last ${CHART_WEEKS} weeks.`}
      >
        <KcalBars
          data={weekly.map((week) => ({
            label: weekLabel(week.start),
            kcal: week.kcal,
          }))}
          labelEvery={4}
        />
      </ChartCard>

      <ChartCard
        title="Calories per day, by weekday"
        note="Average of counted days over the whole period."
      >
        <KcalBars data={weekdayAverages(days)} />
      </ChartCard>

      <ChartCard
        title="Energy split, by week"
        note={`Where the energy came from, the last ${CHART_WEEKS} weeks.`}
      >
        <SplitBars
          data={weekly.map((week) => ({
            label: weekLabel(week.start),
            split: week.split,
          }))}
          labelEvery={4}
        />
      </ChartCard>

      <ChartCard
        title="Energy split, whole period"
        note="Where the energy came from, over the counted days."
      >
        {overall ? (
          <div className="flex flex-col items-center gap-4">
            <EnergyDonut parts={overall} />
            <MacroLegend parts={overall} mode="share" />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No counted days yet.</p>
        )}
      </ChartCard>
    </div>
  )
}

/** The month name over the first week that starts a month (or the first week). */
function monthName(week: Array<CalendarCell>, index: number): string {
  const first =
    week.find((cell) => cell.date.endsWith("-01")) ??
    (index === 0 ? week[0] : undefined)
  return first ? MONTHS.format(new Date(`${first.date}T00:00:00Z`)) : ""
}

function weekLabel(start: string): string {
  return WEEK_LABEL.format(new Date(`${start}T00:00:00Z`))
}

function DayCell({
  date,
  energy,
  incomplete,
  active,
  onSelect,
}: {
  date: string
  /** The day's kcal, or null when nothing was logged. */
  energy: number | null
  incomplete: boolean
  active: boolean
  onSelect: () => void
}) {
  const amount =
    energy === null ? "no meals" : `${formatNumber(energy, 0)} kcal`
  const label = `${dayLabel(date)}: ${amount}${incomplete ? ", incomplete" : ""}`
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={active}
      title={label}
      onClick={onSelect}
      style={{ background: levelColor(levelFor(energy)) }}
      className={cn(
        "size-4 rounded-[4px] outline-none focus-visible:ring-2 focus-visible:ring-ring",
        incomplete && "border border-dashed border-foreground/60",
        active && "ring-2 ring-foreground"
      )}
    />
  )
}

function Legend() {
  const levels = Array.from({ length: LEVELS }, (_, index) => index + 1)
  return (
    <div className="flex flex-col gap-2 text-xs text-muted-foreground">
      <div className="flex flex-wrap items-center gap-1.5">
        <span>Less</span>
        {levels.map((level) => (
          <span
            key={level}
            aria-hidden
            className="size-3.5 rounded-[3px]"
            style={{ background: levelColor(level) }}
          />
        ))}
        <span>More</span>
        <span className="ml-auto flex items-center gap-1.5">
          <span
            aria-hidden
            className="size-3.5 rounded-[3px]"
            style={{ background: levelColor(0) }}
          />
          No meals
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <span
          aria-hidden
          className="size-3.5 rounded-[3px] border border-dashed border-foreground/60"
        />
        Incomplete, left out of the stats
      </div>
      <p>kcal per day: {levelRanges().join(", ")}</p>
    </div>
  )
}

function ChartCard({
  title,
  note,
  children,
}: {
  title: string
  note: string
  children: ReactNode
}) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <div>
          <h2 className="font-heading font-semibold">{title}</h2>
          <p className="text-sm text-muted-foreground">{note}</p>
        </div>
        {children}
      </CardContent>
    </Card>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-muted/60 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-medium tabular-nums">{value}</div>
    </div>
  )
}
