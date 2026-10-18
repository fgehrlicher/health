import { expect, test } from "@playwright/test"
import type { APIRequestContext, Page } from "@playwright/test"

const API = "http://127.0.0.1:8010"

/** Open a page and wait until React handles clicks (see HydrationMarker). */
async function open(page: Page, path: string) {
  await page.goto(path)
  await page.locator("html[data-hydrated]").waitFor()
}

/** A product of its own per test and project, so parallel runs never share one. */
async function product(request: APIRequestContext, name: string) {
  const created = await request.post(`${API}/api/foods`, {
    data: {
      name,
      food_group: "M",
      nutrition: {
        energy_kj: 254,
        energy_kcal: 60,
        fat_g: 0.2,
        saturated_fat_g: 0.1,
        carbs_g: 3.5,
        sugars_g: 3.5,
        protein_g: 11,
        salt_g: 0.1,
      },
    },
  })
  expect(created.status()).toBe(201)
  return ((await created.json()) as { food: { slug: string } }).food.slug
}

test("an unused product is deleted from its page", async ({
  page,
  request,
}, testInfo) => {
  const slug = await product(request, `E2E Unused ${testInfo.project.name}`)
  await open(page, `/foods/${slug}`)
  await page.getByRole("button", { name: "Delete product" }).click()
  const dialog = page.getByRole("dialog")
  await expect(dialog.getByText("Nothing uses it.")).toBeVisible()
  await dialog.getByRole("button", { name: "Delete product" }).click()

  await expect(page.getByText(/deleted\./)).toBeVisible()
  await expect(page).toHaveURL(/\/foods$/)
  expect((await request.get(`${API}/api/foods/${slug}`)).status()).toBe(404)
})

test("a used product is replaced in its meals, then deleted", async ({
  page,
  request,
}, testInfo) => {
  const slug = await product(request, `E2E Used ${testInfo.project.name}`)
  // A day of its own, so the logging tests, which clear today, leave it alone.
  const day = testInfo.project.name === "mobile" ? "2026-01-06" : "2026-01-05"
  const meal = await request.post(`${API}/api/log/meals`, {
    data: { eaten_at: `${day}T12:00`, items: [{ food: slug, amount: 150 }] },
  })
  expect(meal.status()).toBe(201)
  const mealId = ((await meal.json()) as { id: number }).id

  await open(page, `/foods/${slug}`)
  await page.getByRole("button", { name: "Delete product" }).click()
  const dialog = page.getByRole("dialog")
  await expect(dialog.getByText(/It is used in 1 meal\./)).toBeVisible()
  const confirm = dialog.getByRole("button", { name: "Replace and delete" })
  await expect(confirm).toBeDisabled()

  await dialog.getByRole("button", { name: "Choose a food" }).click()
  await page.getByPlaceholder(/Search foods/).fill("apple")
  await page.getByRole("option").first().click()
  await expect(dialog.getByText("Takes its place")).toBeVisible()
  await expect(confirm).toBeEnabled()
  await confirm.click()

  await expect(page.getByText(/1 meal now use/)).toBeVisible()
  await expect(page).toHaveURL(/\/foods$/)
  expect((await request.get(`${API}/api/foods/${slug}`)).status()).toBe(404)
  const moved = (await (
    await request.get(`${API}/api/log/meals/${mealId}`)
  ).json()) as { items: Array<{ food: string; amount: string }> }
  expect(moved.items).toHaveLength(1)
  expect(moved.items[0].food).not.toBe(slug)
  expect(Number(moved.items[0].amount)).toBe(150)
  await request.delete(`${API}/api/log/meals/${mealId}`)
})
