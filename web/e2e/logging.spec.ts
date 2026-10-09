import { expect, test } from "@playwright/test"
import type { APIRequestContext, Page } from "@playwright/test"

const API = "http://127.0.0.1:8010"
const FOOD = {
  name: "E2E Quark-Creme",
  brand: "E2E",
  barcode: "4000000000020",
  food_group: "M", // valid check digit, not a real product
  ingredients_text: "Speisequark, Joghurterzeugnis",
  nutrition: {
    energy_kj: 287,
    energy_kcal: 68,
    fat_g: 0.4,
    saturated_fat_g: 0.3,
    carbs_g: 3.5,
    sugars_g: 3.0,
    fiber_g: 0.2,
    protein_g: 12.4,
    salt_g: 0.13,
  },
  portions: [{ name: "Becher", kind: "package", quantity: 400, unit: "g" }],
}

/** Open a page and wait until React handles clicks (see HydrationMarker). */
async function open(page: Page, path: string) {
  const response = await page.goto(path)
  await page.locator("html[data-hydrated]").waitFor()
  return response
}

function todayInBerlin(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Berlin" }).format(
    new Date()
  )
}

/** A known branded food with a portion, and an empty day to log into. */
async function prepare(request: APIRequestContext) {
  const created = await request.post(`${API}/api/foods`, { data: FOOD })
  expect([201, 409]).toContain(created.status())
  const day = await (
    await request.get(`${API}/api/log/days/${todayInBerlin()}`)
  ).json()
  for (const meal of day.meals) {
    await request.delete(`${API}/api/log/meals/${meal.id}`)
  }
}

test.beforeEach(async ({ request }) => {
  await prepare(request)
})

test("log, edit, and delete a meal", async ({ page }) => {
  await open(page, "/")
  await expect(page.getByText("Nothing logged yet")).toBeVisible()

  await page.getByRole("button", { name: "Log meal" }).first().click()
  const sheet = page.getByRole("dialog")
  await sheet.getByRole("button", { name: "Snack" }).click()
  await sheet.getByLabel("Note").fill("Tasted like peach yogurt")
  await sheet.getByRole("button", { name: "Add food" }).click()
  await page.getByPlaceholder(/Search foods/).fill("e2e quark")
  await page.getByRole("option", { name: /E2E Quark-Creme/ }).click()

  // Switching to the label portion fills in one cup.
  await sheet.getByRole("combobox", { name: "Unit" }).click()
  await page.getByRole("option", { name: /Becher/ }).click()
  await expect(sheet.getByText("272")).toBeVisible()
  await sheet.getByRole("button", { name: "Log meal" }).click()

  await expect(page.getByText("Meal logged")).toBeVisible()
  const card = page
    .getByText("E2E Quark-Creme")
    .locator("xpath=ancestor::*[@data-slot='card'][1]")
  await expect(card.getByText("Snack")).toBeVisible()
  await expect(card.getByText("Tasted like peach yogurt")).toBeVisible()
  await expect(card.getByText("272 kcal").first()).toBeVisible()

  // Half a cup instead; editing shows the stored grams.
  await card.getByRole("button", { name: "Meal actions" }).click()
  await page.getByRole("menuitem", { name: "Edit" }).click()
  await sheet.getByLabel("Amount").fill("200")
  await expect(sheet.getByText("136")).toBeVisible()
  await sheet.getByRole("button", { name: "Save changes" }).click()
  await expect(page.getByText("Meal updated")).toBeVisible()
  await expect(card.getByText("136 kcal").first()).toBeVisible()

  await card.getByRole("button", { name: "Meal actions" }).click()
  await page.getByRole("menuitem", { name: "Delete" }).click()
  await page.getByRole("button", { name: "Delete" }).click()
  await expect(page.getByText("Nothing logged yet")).toBeVisible()
})

test("a meal without foods is logged as unknown", async ({ page }) => {
  await open(page, "/")
  await page.getByRole("button", { name: "Log meal" }).first().click()
  const sheet = page.getByRole("dialog")
  await sheet.getByRole("button", { name: "Dinner" }).click()
  await sheet.getByRole("button", { name: "Log meal" }).click()

  await expect(page.getByText("Meal logged")).toBeVisible()
  await expect(page.getByText("1 unknown meal")).toBeVisible()
  await expect(page.getByText(/No foods yet/)).toBeVisible()
})

test("search the catalog and open a food", async ({ page }) => {
  await open(page, "/foods")
  await page.getByPlaceholder(/German names/).fill("brocoli")
  await expect(page).toHaveURL(/q=brocoli/)
  // A card's link name starts with the food name, then its details.
  await page.getByRole("link", { name: /^Broccoli roh / }).click()

  await expect(
    page.getByRole("heading", { name: "Broccoli roh" })
  ).toBeVisible()
  await expect(page.getByText("Where the energy comes from")).toBeVisible()
  await expect(page.getByText("Vitamin C").first()).toBeVisible()
})

test("clear filters resets everything but the sort", async ({ page }) => {
  await open(page, "/foods?group=F&prep=raw&sort=energy_asc")
  await expect(page.getByRole("heading", { name: "Fruit" })).toBeVisible()
  await page.getByRole("button", { name: "Clear filters (2)" }).click()
  await expect(page.getByRole("heading", { name: "All foods" })).toBeVisible()
  await expect(page).toHaveURL(/\/foods\?sort=energy_asc$/)
  await expect(page.getByRole("button", { name: /Clear filters/ })).toHaveCount(
    0
  )

  // An empty result offers the way back.
  await page.getByPlaceholder(/German names/).fill("zzzqqq")
  await expect(page.getByText("No matching foods.")).toBeVisible()
  await page.getByRole("button", { name: "Clear filters", exact: true }).click()
  await expect(page.getByPlaceholder(/German names/)).toHaveValue("")
  await expect(page.getByText("No matching foods.")).toHaveCount(0)
})

test("branded foods have a category and a brand filter", async ({
  page,
  isMobile,
}) => {
  await open(page, "/foods?kind=branded")
  // Phones show the groups in a sheet behind the Categories button.
  if (isMobile) await page.getByRole("button", { name: "Categories" }).click()
  const groups = page
    .getByRole("navigation", { name: "Food groups" })
    .locator("visible=true")
  await expect(groups.getByRole("link", { name: /Dairy/ })).toBeVisible()
  await expect(groups.getByRole("link", { name: /Fruit/ })).toHaveCount(0)
  if (isMobile) await page.keyboard.press("Escape")

  await page.getByRole("combobox", { name: "Brand" }).click()
  await page.getByRole("option", { name: /^E2E \(/ }).click()
  await expect(page).toHaveURL(/brand=E2E/)
  await page.getByRole("link", { name: /^E2E Quark-Creme/ }).click()

  // A product's category can be changed where it is shown.
  await page.getByRole("combobox", { name: "Category" }).click()
  await page.getByRole("option", { name: "Sweets" }).click()
  await expect(page.getByText("Moved to Sweets")).toBeVisible()
  await page.getByRole("combobox", { name: "Category" }).click()
  await page.getByRole("option", { name: "Dairy" }).click()
  await expect(page.getByText("Moved to Dairy")).toBeVisible()
})

test("an unknown food shows the not-found page", async ({ page }) => {
  const response = await open(page, "/foods/does-not-exist")
  expect(response?.status()).toBe(404)
  await expect(page.getByText("This page does not exist.")).toBeVisible()
})

test("products with an incomplete label are marked and filterable", async ({
  page,
}) => {
  // The e2e product has no legal name, so its label is incomplete.
  await open(page, "/foods?kind=branded")
  await page.getByRole("button", { name: /Needs photos/ }).click()
  await expect(page).toHaveURL(/incomplete=true/)
  const card = page.getByRole("link", { name: /E2E Quark-Creme/ })
  await expect(card.getByText("needs photos")).toBeVisible()
  await card.click()
  await expect(
    page.getByText("Label incomplete: photograph next time")
  ).toBeVisible()
  await expect(page.getByText(/^Legal name:/)).toBeVisible()
})
