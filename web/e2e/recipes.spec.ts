import { expect, test } from "@playwright/test"
import type { APIRequestContext, Page } from "@playwright/test"

const API = "http://127.0.0.1:8010"

/** Open a page and wait until React handles clicks (see HydrationMarker). */
async function open(page: Page, path: string) {
  await page.goto(path)
  await page.locator("html[data-hydrated]").waitFor()
}

function todayInBerlin(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Berlin" }).format(
    new Date()
  )
}

/** Remove what earlier runs left: today's meals, E2E cooks, and E2E recipes. */
async function clean(request: APIRequestContext) {
  const day = await (
    await request.get(`${API}/api/log/days/${todayInBerlin()}`)
  ).json()
  for (const meal of day.meals) {
    await request.delete(`${API}/api/log/meals/${meal.id}`)
  }
  const cooks = await (await request.get(`${API}/api/cooks?q=E2E`)).json()
  for (const cook of cooks) await request.delete(`${API}/api/cooks/${cook.id}`)
  const recipes = await (await request.get(`${API}/api/recipes?q=E2E`)).json()
  for (const recipe of recipes) {
    await request.delete(`${API}/api/recipes/${recipe.slug}`)
  }
}

async function addIngredient(page: Page, search: string, grams: string) {
  const sheet = page.getByRole("dialog")
  await sheet.getByRole("button", { name: "Add food" }).click()
  await page.getByPlaceholder(/Search foods/).fill(search)
  await page
    .getByRole("option", { name: new RegExp(search, "i") })
    .first()
    .click()
  await sheet.getByLabel("Amount").last().fill(grams)
}

test.beforeEach(async ({ request }) => {
  await clean(request)
})

test("create a recipe, cook it differently, eat a portion, and improve it", async ({
  page,
}) => {
  await open(page, "/recipes")
  await page.getByRole("button", { name: "New recipe" }).first().click()
  const sheet = page.getByRole("dialog")
  await sheet.getByLabel("Name").fill("E2E Chili")
  await sheet.getByLabel("Portions").fill("4")
  await addIngredient(page, "Broccoli boiled", "300")
  await addIngredient(page, "White rice boiled", "600")
  await sheet.getByRole("button", { name: "Create recipe" }).click()

  await expect(page.getByRole("heading", { name: "E2E Chili" })).toBeVisible()
  await expect(page.getByText("v1", { exact: true })).toBeVisible()

  // Cook it with more broccoli than written.
  await page.getByRole("button", { name: "Cook v1" }).click()
  const cookSheet = page.getByRole("dialog")
  await expect(cookSheet.getByLabel("Amount")).toHaveCount(2)
  await cookSheet.getByLabel("Amount").first().fill("500")
  await cookSheet.getByLabel("How did it turn out?").fill("needs more spice")
  await expect(cookSheet.getByText("kcal ·")).toBeVisible()
  await cookSheet.getByRole("button", { name: "Log cook" }).click()

  await expect(page.getByText("Compared with v1")).toBeVisible()
  await expect(page.getByText("300 → 500 g")).toBeVisible()
  await expect(page.getByText("needs more spice")).toBeVisible()
  await expect(page.getByText("4 of 4 portions left")).toBeVisible()

  // One portion of it is lunch.
  await page.getByRole("button", { name: "Eat a portion" }).click()
  const mealSheet = page.getByRole("dialog")
  await mealSheet.getByRole("button", { name: "Lunch" }).click()
  await expect(mealSheet.getByText(/^Cooked Today/)).toBeVisible()
  await mealSheet.getByRole("button", { name: "Log meal" }).click()
  await expect(page.getByText("Meal logged")).toBeVisible()
  await expect(page.getByText("3 of 4 portions left")).toBeVisible()

  await open(page, "/")
  const card = page
    .getByRole("link", { name: /E2E Chili/ })
    .locator("xpath=ancestor::*[@data-slot='card'][1]")
  await expect(card.getByText("Lunch")).toBeVisible()
  await expect(card.getByText("1 portion")).toBeVisible()

  // The cook worked out: it becomes v2.
  await card.getByRole("link", { name: /E2E Chili/ }).click()
  await page.getByRole("button", { name: "Save as new version" }).click()
  const versionSheet = page.getByRole("dialog")
  await versionSheet
    .getByLabel("What changed and why?")
    .fill("more broccoli, it was better")
  await versionSheet.getByRole("button", { name: "Save version" }).click()

  await expect(page.getByRole("heading", { name: "E2E Chili" })).toBeVisible()
  await expect(page.getByText("v2", { exact: true })).toBeVisible()
  await expect(page.getByText("more broccoli, it was better")).toBeVisible()
  await expect(page.getByText("300 → 500 g")).toBeVisible()
  await expect(
    page.getByRole("link", { name: "saved from a cook" })
  ).toBeVisible()
})

test("swap a generic ingredient for a branded variant when cooking", async ({
  page,
  request,
}) => {
  const soy = "bls4-h841100" // Sojadrink ungesüßt
  const product = await request.post(`${API}/api/foods`, {
    data: {
      name: "E2E Soja Drink",
      brand: "E2E",
      barcode: "4000000000044", // valid check digit, not a real product
      food_group: "H",
      variant_of: soy,
      nutrition: {
        reference_unit: "ml",
        energy_kcal: 33,
        fat_g: 1.8,
        carbs_g: 0.2,
        protein_g: 3.3,
      },
    },
  })
  expect([201, 409]).toContain(product.status())
  const recipe = await request.post(`${API}/api/recipes`, {
    data: {
      name: "E2E Porridge",
      portions: 1,
      items: [{ food: soy, amount: 300 }],
    },
  })
  expect(recipe.status()).toBe(201)

  // The generic food lists the product.
  await open(page, `/foods/${soy}`)
  await expect(page.getByText("Products of this kind")).toBeVisible()
  await expect(page.getByRole("link", { name: /E2E Soja Drink/ })).toBeVisible()

  await open(page, "/recipes/e2e-porridge")
  await expect(page.getByText(/Generic values for Sojadrink/)).toBeVisible()
  await page.getByRole("button", { name: "Cook v1" }).click()
  const sheet = page.getByRole("dialog")
  await sheet.getByRole("combobox", { name: "Product" }).click()
  await page.getByRole("option", { name: "E2E E2E Soja Drink" }).click()
  await sheet.getByLabel("Amount").fill("300")
  await sheet.getByRole("button", { name: "Log cook" }).click()

  await expect(page.getByText("Compared with v1")).toBeVisible()
  await expect(
    page.getByText("instead of Sojadrink ungesüßt")
  ).toBeVisible()
  await expect(page.getByText("99", { exact: true })).toBeVisible()
})

test("browse recipes by tag and edit a recipe's tags", async ({
  page,
  request,
}) => {
  const created = await request.post(`${API}/api/recipes`, {
    data: {
      name: "E2E Sorbet",
      tags: ["E2E Dessert"],
      portions: 2,
      items: [{ food: "bls4-c352032", amount: 100 }],
    },
  })
  expect(created.status()).toBe(201)

  await open(page, "/recipes")
  await page.getByRole("link", { name: /^e2e dessert/i }).click()
  await expect(page).toHaveURL(/tag=e2e/)
  await expect(page.getByRole("heading", { name: "E2e dessert" })).toBeVisible()
  await page.getByRole("link", { name: /E2E Sorbet/ }).click()

  await expect(page.getByRole("heading", { name: "E2E Sorbet" })).toBeVisible()
  const input = page.getByLabel("Add tag")
  await input.fill("E2E  Ice Cream")
  await input.press("Enter")
  await expect(page.getByText("e2e ice cream", { exact: true })).toBeVisible()

  await open(page, "/recipes?tag=e2e%20ice%20cream")
  await expect(page.getByRole("link", { name: /E2E Sorbet/ })).toBeVisible()
})
