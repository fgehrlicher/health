import { addDays, today } from "@/lib/format"

/** Weeks on the calendar; the last one holds today. */
export const CALENDAR_WEEKS = 53

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

/**
 * A day against the daily limit: within it or below it, above it, or without
 * known energy (no meals, or only unknown ones).
 */
export type DayStatus = "within" | "above" | "none"

export function statusFor(kcal: number | null, limit: number): DayStatus {
  if (kcal === null || kcal <= 0) return "none"
  return kcal <= limit ? "within" : "above"
}

/** Green within the limit, red above it, the empty color without known energy. */
export function statusColor(status: DayStatus): string {
  if (status === "within") {
    return "color-mix(in oklab, var(--primary) 80%, var(--muted))"
  }
  if (status === "above") {
    return "color-mix(in oklab, var(--destructive) 80%, var(--muted))"
  }
  return "var(--muted)"
}

/** The words a screen reader hears for a status, or nothing without known energy. */
export function statusWords(status: DayStatus): string | null {
  if (status === "within") return "within limit"
  if (status === "above") return "above limit"
  return null
}
