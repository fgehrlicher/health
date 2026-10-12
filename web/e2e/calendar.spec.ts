import { expect, test } from "@playwright/test"
import type { Page } from "@playwright/test"

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

test("the calendar colors each day by its calories and opens the day", async ({
  page,
  request,
}) => {
  // Start from an empty today, then log 400 g of rice.
  const day = await (
    await request.get(`${API}/api/log/days/${todayInBerlin()}`)
  ).json()
  for (const meal of day.meals) {
    await request.delete(`${API}/api/log/meals/${meal.id}`)
  }
  const meal = await request.post(`${API}/api/log/meals`, {
    data: {
      kind: "lunch",
      items: [{ food: "bls4-c352032", amount: 400 }],
    },
  })
  expect(meal.status()).toBe(201)

  await open(page, "/calendar")
  await expect(page.getByRole("heading", { name: "Calendar" })).toBeVisible()
  // Today is selected at first, and its cell shows the kcal in its label.
  const todayCell = page.getByRole("button", { name: /^Today: .*kcal$/ })
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
