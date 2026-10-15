import type { CalendarDay } from "@/lib/api/types"
import type { CalendarCell } from "@/lib/calendar"
import { addDays } from "@/lib/format"
import { energySplit } from "@/lib/macros"
import type { EnergyPart } from "@/lib/macros"

type Total = { measured: string; estimated: string }

/** The nutrients the energy split uses, as the calendar sends them per day. */
type SplitField =
  "protein_g" | "fat_g" | "carbs_g" | "polyols_g" | "fiber_g" | "alcohol_g"

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

/** A day's amount as the app counts it: measured plus estimated. */
export function amountOf(total: Total): number {
  return Number(total.measured) + Number(total.estimated)
}

/**
 * Days that count in the stats: not marked incomplete, and with known energy.
 * An incomplete day still shows on the calendar, but it would pull every
 * average down, so it is left out here.
 */
export function countedDays(days: Array<CalendarDay>): Array<CalendarDay> {
  return days.filter((day) => !day.incomplete && amountOf(day.energy_kcal) > 0)
}

export function average(values: Array<number>): number | null {
  if (values.length === 0) return null
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

/** Monday is 0. Dates are read in UTC, so the host zone does not matter. */
export function weekdayIndex(date: string): number {
  return (new Date(`${date}T00:00:00Z`).getUTCDay() + 6) % 7
}

/** Average kcal per weekday over the counted days; null where there are none. */
export function weekdayAverages(
  days: Array<CalendarDay>
): Array<{ label: string; kcal: number | null }> {
  const counted = countedDays(days)
  return WEEKDAYS.map((label, index) => ({
    label,
    kcal: average(
      counted
        .filter((day) => weekdayIndex(day.date) === index)
        .map((day) => amountOf(day.energy_kcal))
    ),
  }))
}

/** The energy split of the given days, over their summed grams. */
export function energySplitOf(
  days: Array<CalendarDay>
): Array<EnergyPart> | null {
  const sum = (field: SplitField) =>
    String(days.reduce((total, day) => total + amountOf(day[field]), 0))
  return energySplit({
    protein_g: sum("protein_g"),
    fat_g: sum("fat_g"),
    carbs_g: sum("carbs_g"),
    polyols_g: sum("polyols_g"),
    fiber_g: sum("fiber_g"),
    alcohol_g: sum("alcohol_g"),
  })
}

export type WeekStat = {
  /** The Monday the week starts on, YYYY-MM-DD. */
  start: string
  /** Average kcal per counted day that week; null when none counted. */
  kcal: number | null
  split: Array<EnergyPart> | null
}

/** Each week's average kcal and energy split, from counted days only. */
export function weeklyStats(
  weeks: Array<Array<CalendarCell>>,
  days: Array<CalendarDay>
): Array<WeekStat> {
  const counted = countedDays(days)
  return weeks.map((week) => {
    const dates = new Set(week.map((cell) => cell.date))
    const inWeek = counted.filter((day) => dates.has(day.date))
    return {
      start: week[0].date,
      kcal: average(inWeek.map((day) => amountOf(day.energy_kcal))),
      split: energySplitOf(inWeek),
    }
  })
}

/** Each day's energy split, from counted days only; null for a day that does not count. */
export function dailySplits(
  dates: Array<string>,
  days: Array<CalendarDay>
): Array<{ date: string; split: Array<EnergyPart> | null }> {
  const counted = countedDays(days)
  return dates.map((date) => ({
    date,
    split: energySplitOf(counted.filter((day) => day.date === date)),
  }))
}

/**
 * Each day's kcal, and the average of that day and the six before it. Only
 * counted days take part, so an incomplete day never drags the trend down.
 */
export function dailyKcal(
  dates: Array<string>,
  days: Array<CalendarDay>
): Array<{ date: string; kcal: number | null; average: number | null }> {
  const byDate = new Map(
    countedDays(days).map((day) => [day.date, amountOf(day.energy_kcal)])
  )
  return dates.map((date) => {
    const window: Array<number> = []
    for (let offset = 0; offset < 7; offset += 1) {
      const kcal = byDate.get(addDays(date, -offset))
      if (kcal !== undefined) window.push(kcal)
    }
    return { date, kcal: byDate.get(date) ?? null, average: average(window) }
  })
}
