import { useSuspenseQuery } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { cn } from "cn"
import { useEffect, useMemo, useRef, useState } from "react"
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

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
const MONTHS = new Intl.DateTimeFormat("en-GB", {
  month: "short",
  timeZone: "UTC",
})

export const Route = createFileRoute("/calendar")({
  loader: ({ context }) => {
    const { start, end } = calendarRange(calendarWeeks())
    return context.queryClient.ensureQueryData(calendarQuery(start, end))
  },
  component: CalendarPage,
})

function CalendarPage() {
  const weeks = useMemo(() => calendarWeeks(), [])
  const { start, end } = calendarRange(weeks)
  const { data } = useSuspenseQuery(calendarQuery(start, end))
  const byDate = useMemo(
    () => new Map(data.days.map((day) => [day.date, day])),
    [data.days]
  )
  const [selected, setSelected] = useState(today)
  const scroller = useRef<HTMLDivElement>(null)

  // The latest weeks are the ones worth seeing, so start at the right edge.
  useEffect(() => {
    const element = scroller.current
    if (element) element.scrollLeft = element.scrollWidth
  }, [])

  const kcalOf = (date: string): number | null => {
    const day = byDate.get(date)
    return day ? kcal(day.energy_kcal) : null
  }
  const selectedDay = byDate.get(selected)
  const knownDays = data.days
    .map((day) => kcal(day.energy_kcal))
    .filter((value) => value > 0)
  const average = knownDays.length
    ? knownDays.reduce((sum, value) => sum + value, 0) / knownDays.length
    : null

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-heading text-2xl font-semibold">Calendar</h1>
        <p className="text-sm text-muted-foreground">
          Calories per day over the last {CALENDAR_WEEKS} weeks. Darker days had
          more.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Stat label="Days logged" value={String(data.days.length)} />
        <Stat
          label="Average on logged days"
          value={average === null ? "–" : `${formatNumber(average, 0)} kcal`}
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
                            energy={kcalOf(cell.date)}
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
                  {formatNumber(kcal(selectedDay.energy_kcal), 0)}
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
          <Button
            variant="outline"
            nativeButton={false}
            render={<Link to="/" search={{ date: selected }} />}
          >
            Open this day
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

/** Energy as the day view counts it: measured plus estimated. */
function kcal(total: { measured: string; estimated: string }): number {
  return Number(total.measured) + Number(total.estimated)
}

/** The month name over the first week that starts a month (or the first week). */
function monthName(week: Array<CalendarCell>, index: number): string {
  const first =
    week.find((cell) => cell.date.endsWith("-01")) ??
    (index === 0 ? week[0] : undefined)
  return first ? MONTHS.format(new Date(`${first.date}T00:00:00Z`)) : ""
}

function DayCell({
  date,
  energy,
  active,
  onSelect,
}: {
  date: string
  /** The day's kcal, or null when nothing was logged. */
  energy: number | null
  active: boolean
  onSelect: () => void
}) {
  const label = `${dayLabel(date)}: ${energy === null ? "no meals" : `${formatNumber(energy, 0)} kcal`}`
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
      <p>kcal per day: {levelRanges().join(", ")}</p>
    </div>
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
