import { addDays, today } from "@/lib/format"

/** Weeks on the calendar; the last one holds today. */
export const CALENDAR_WEEKS = 53

/**
 * Where each level starts, in kcal: below the first step is level 1, below the
 * second is level 2, and so on. From the last step up is the darkest level.
 */
export const LEVEL_STEPS = [1000, 1500, 2000, 2500] as const

/** Levels 1 to 5 by kcal; level 0 is a day without meals. */
export const LEVELS = LEVEL_STEPS.length + 1

/** How much of the primary color each level uses, over the empty color. */
const LEVEL_SHARE = [0, 25, 40, 60, 80, 100]

export type CalendarCell = { date: string; future: boolean }

/**
 * The weeks shown, oldest first, each Monday to Sunday. The last week holds
 * today; days after today are marked future and left empty.
 */
export function calendarWeeks(
  now: string = today()
): Array<Array<CalendarCell>> {
  // Monday is 0. Dates are shifted in UTC, so the host zone does not matter.
  const weekday = (new Date(`${now}T00:00:00Z`).getUTCDay() + 6) % 7
  const firstMonday = addDays(now, -weekday - 7 * (CALENDAR_WEEKS - 1))
  return Array.from({ length: CALENDAR_WEEKS }, (_week, week) =>
    Array.from({ length: 7 }, (_day, day) => {
      const date = addDays(firstMonday, week * 7 + day)
      return { date, future: date > now }
    })
  )
}

/** The first and last date the calendar shows, inclusive. */
export function calendarRange(weeks: Array<Array<CalendarCell>>) {
  return {
    start: weeks[0][0].date,
    end: weeks[weeks.length - 1][6].date,
  }
}

/** 0 for a day without meals; 1 to 5 by kcal. A day with only unknown meals is 1. */
export function levelFor(kcal: number | null): number {
  if (kcal === null) return 0
  const index = LEVEL_STEPS.findIndex((step) => kcal < step)
  return index === -1 ? LEVELS : index + 1
}

export function levelColor(level: number): string {
  if (level === 0) return "var(--muted)"
  return `color-mix(in oklab, var(--primary) ${LEVEL_SHARE[level]}%, var(--muted))`
}

/** The kcal range of each level, for the legend, e.g. "1,500–1,999". */
export function levelRanges(): Array<string> {
  const kcal = (value: number) => value.toLocaleString("en-GB")
  const ranges = LEVEL_STEPS.map((step, index) =>
    index === 0
      ? `under ${kcal(step)}`
      : `${kcal(LEVEL_STEPS[index - 1])}–${kcal(step - 1)}`
  )
  return [...ranges, `${kcal(LEVEL_STEPS[LEVEL_STEPS.length - 1])} or more`]
}
