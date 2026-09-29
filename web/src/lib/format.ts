// Formatting and dates. Fixed locale and zone so server and browser render the
// same text; the zone matches the API's HEALTH_TIMEZONE default.
export const TIME_ZONE = "Europe/Berlin"
const LOCALE = "en-GB"

const numberFormats = new Map<number, Intl.NumberFormat>()

/** A decimal string or number for display; a dash means unknown, never zero. */
export function formatNumber(
  value: string | number | null | undefined,
  digits = 1
): string {
  if (value === null || value === undefined || value === "") return "–"
  let format = numberFormats.get(digits)
  if (!format) {
    format = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: digits })
    numberFormats.set(digits, format)
  }
  return format.format(Number(value))
}

/** Today's date (YYYY-MM-DD) in the app's zone. */
export function today(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE }).format(
    new Date()
  )
}

/** Shift a YYYY-MM-DD date by whole days, independent of the host zone. */
export function addDays(date: string, days: number): string {
  const [year, month, day] = date.split("-").map(Number)
  const shifted = new Date(Date.UTC(year, month - 1, day + days))
  return shifted.toISOString().slice(0, 10)
}

/** "Today", "Yesterday", or e.g. "Mon, 28 Sep". */
export function dayLabel(date: string): string {
  const now = today()
  if (date === now) return "Today"
  if (date === addDays(now, -1)) return "Yesterday"
  if (date === addDays(now, 1)) return "Tomorrow"
  const [year, month, day] = date.split("-").map(Number)
  return new Intl.DateTimeFormat(LOCALE, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: year === Number(now.slice(0, 4)) ? undefined : "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, day)))
}

/** "08:40" from an ISO time that already carries the local offset. */
export function clockTime(iso: string): string {
  return iso.slice(11, 16)
}

/** The current local time as a datetime-local value, e.g. 2026-09-29T08:40. */
export function nowLocal(): string {
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date())
  return parts.replace(" ", "T")
}

export function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}
