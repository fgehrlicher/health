import { expect, test } from "@playwright/test"
import type { APIRequestContext, Page } from "@playwright/test"

const API = "http://127.0.0.1:8010"

async function open(page: Page, path: string) {
  await page.goto(path)
  await page.locator("html[data-hydrated]").waitFor()
}

function todayInBerlin(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Berlin" }).format(
    new Date()
  )
}

/** Remove today's meals and its incomplete mark, so each test starts clean. */
async function resetToday(request: APIRequestContext) {
  const day = await (
    await request.get(`${API}/api/log/days/${todayInBerlin()}`)
  ).json()
  for (const meal of day.meals) {
    await request.delete(`${API}/api/log/meals/${meal.id}`)
  }
  await request.put(`${API}/api/log/days/${todayInBerlin()}/incomplete`, {
    data: { incomplete: false },
  })
}

async function logRice(request: APIRequestContext, grams: number) {
  const meal = await request.post(`${API}/api/log/meals`, {
    data: { kind: "lunch", items: [{ food: "bls4-c352032", amount: grams }] },
  })
  expect(meal.status()).toBe(201)
}

test("the stats color each day by its calories and open the day", async ({
  page,
  request,
}) => {
  await resetToday(request)
  await logRice(request, 400)

  await open(page, "/stats")
  await expect(page.getByRole("heading", { name: "Stats" })).toBeVisible()
  // Today is selected at first, and its cell shows the kcal in its label.
  const todayCell = page.getByRole("button", {
    name: /^Today: .*kcal, within limit$/,
  })
  await expect(todayCell).toBeVisible()
  await expect(todayCell).toHaveAttribute("aria-pressed", "true")
  await expect(page.getByText("1 meal", { exact: true })).toBeVisible()

  // A day without meals says so.
  await page
    .getByRole("button", { name: /: no meals$/ })
    .last()
    .click()
  await expect(page.getByText("No meals logged this day.")).toBeVisible()

  await todayCell.click()
  await page.getByRole("button", { name: "Open this day" }).click()
  await expect(page).toHaveURL(new RegExp(`date=${todayInBerlin()}`))
  await expect(page.getByRole("heading", { name: "Today" })).toBeVisible()
})

test("a day above the daily limit is marked, and the limit can be changed", async ({
  page,
  request,
}) => {
  await resetToday(request)
  await logRice(request, 400)
  try {
    await open(page, "/stats")
    await page.getByLabel("Daily limit, kcal").fill("300")
    await page.getByRole("button", { name: "Save" }).click()
    await expect(
      page.getByRole("button", { name: /^Today: .*kcal, above limit$/ })
    ).toBeVisible()
    await expect(
      page.getByText("Daily limit saved", { exact: true })
    ).toBeVisible()
  } finally {
    await request.put(`${API}/api/log/goals`, {
      data: { daily_kcal_limit: 2000 },
    })
  }
})

test("an incomplete day stays on the calendar but leaves the stats", async ({
  page,
  request,
}) => {
  await resetToday(request)
  await logRice(request, 400)
  try {
    // Marked on the day view, where the meals are.
    await open(page, "/")
    const toggle = page.getByRole("switch", { name: "Incomplete day" })
    await toggle.click()
    await expect(toggle).toBeChecked()

    // The stats show the day as incomplete, and keep it on the calendar.
    await open(page, "/stats")
    await expect(
      page.getByText("Incomplete days", { exact: true })
    ).toBeVisible()
    await expect(
      page.getByRole("button", { name: /^Today: .*incomplete$/ })
    ).toBeVisible()
  } finally {
    await resetToday(request)
  }
})
