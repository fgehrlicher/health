import { describe, expect, it } from "vitest"
import type { CalendarDay } from "@/lib/api/types"
import { CALENDAR_WEEKS, calendarWeeks, statusFor } from "@/lib/calendar"
import { countedDays, dailyKcal, weekdayAverages } from "@/lib/stats"

const none = { measured: "0", estimated: "0", items_without_value: 0 }

function day(date: string, kcal: number, incomplete = false): CalendarDay {
  return {
    date,
    incomplete,
    meals: 1,
    unknown_meals: 0,
    // Measured and estimated both count, as on Today.
    energy_kcal: { ...none, measured: String(kcal - 100), estimated: "100" },
    protein_g: none,
    fat_g: none,
    carbs_g: none,
    fiber_g: none,
    polyols_g: none,
    alcohol_g: none,
  }
}

describe("statusFor", () => {
  it("judges a day against the limit and the tolerance above it", () => {
    expect(statusFor(2200, 2200, 300)).toBe("within")
    expect(statusFor(2201, 2200, 300)).toBe("caution")
    expect(statusFor(2500, 2200, 300)).toBe("caution")
    expect(statusFor(2501, 2200, 300)).toBe("above")
  })

  it("has no status for a day without known energy", () => {
    expect(statusFor(null, 2200, 300)).toBe("none")
    expect(statusFor(0, 2200, 300)).toBe("none")
  })
})

describe("calendarWeeks", () => {
  it("runs Monday to Sunday and ends with the week that holds today", () => {
    // 2026-10-17 is a Saturday.
    const weeks = calendarWeeks("2026-10-17")
    expect(weeks).toHaveLength(CALENDAR_WEEKS)
    const last = weeks[weeks.length - 1]
    expect(last.map((cell) => cell.date)).toEqual([
      "2026-10-12",
      "2026-10-13",
      "2026-10-14",
      "2026-10-15",
      "2026-10-16",
      "2026-10-17",
      "2026-10-18",
    ])
    expect(last.map((cell) => cell.future)).toEqual([
      false,
      false,
      false,
      false,
      false,
      false,
      true,
    ])
  })
})

describe("counted days", () => {
  const days = [
    day("2026-10-12", 2000),
    day("2026-10-13", 3000, true),
    day("2026-10-14", 1000),
  ]

  it("leaves out incomplete days and days without energy", () => {
    const counted = countedDays([...days, day("2026-10-15", 0)])
    expect(counted.map((d) => d.date)).toEqual(["2026-10-12", "2026-10-14"])
  })

  it("keeps an incomplete day out of the weekday averages", () => {
    const averages = weekdayAverages(days)
    expect(averages.map((weekday) => weekday.kcal)).toEqual([
      2000,
      null,
      1000,
      null,
      null,
      null,
      null,
    ])
  })

  it("averages each day with the six before it", () => {
    const series = dailyKcal(["2026-10-13", "2026-10-14"], days)
    expect(series).toEqual([
      { date: "2026-10-13", kcal: null, average: 2000 },
      { date: "2026-10-14", kcal: 1000, average: 1500 },
    ])
  })
})
