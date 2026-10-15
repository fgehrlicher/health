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
 * A day against the goals: within the limit (green), up to the tolerance above
 * it (yellow), beyond that (red), or without known energy (gray).
 */
export type DayStatus = "within" | "caution" | "above" | "none"

export function statusFor(
  kcal: number | null,
  limit: number,
  tolerance: number
): DayStatus {
  if (kcal === null || kcal <= 0) return "none"
  if (kcal <= limit) return "within"
  return kcal <= limit + tolerance ? "caution" : "above"
}

/** The color of a status; the empty color for a day without known energy. */
export function statusColor(status: DayStatus): string {
  if (status === "within") {
    return "color-mix(in oklab, var(--primary) 80%, var(--muted))"
  }
  if (status === "caution") {
    return "color-mix(in oklab, var(--caution) 85%, var(--muted))"
  }
  if (status === "above") {
    return "color-mix(in oklab, var(--destructive) 80%, var(--muted))"
  }
  return "var(--muted)"
}

/** The words a screen reader hears for a status, or nothing without known energy. */
export function statusWords(status: DayStatus): string | null {
  if (status === "within") return "within limit"
  if (status === "caution") return "above limit, within tolerance"
  if (status === "above") return "above limit, beyond tolerance"
  return null
}
