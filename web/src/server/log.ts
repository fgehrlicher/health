import { createServerFn } from "@tanstack/react-start"
import { z } from "zod"
import { api, toIssues, unwrap } from "./api"
import type { Issue, Meal } from "@/lib/api/types"

/** A catalog food and how much: an amount, or a named portion times count. */
export const foodAmountSchema = z.object({
  food: z.string().min(1).max(200),
  source_id: z.number().int().optional(),
  amount: z.number().positive().optional(),
  portion: z.string().min(1).max(60).optional(),
  count: z.number().positive().optional(),
  estimated: z.boolean().optional(),
})

/** A food, or portions of a cook (`cook` with `amount`). */
const itemSchema = z.object({
  food: z.string().min(1).max(200).optional(),
  cook: z.number().int().optional(),
  source_id: z.number().int().optional(),
  amount: z.number().positive().optional(),
  portion: z.string().min(1).max(60).optional(),
  count: z.number().positive().optional(),
  estimated: z.boolean().optional(),
})

const kindSchema = z.enum(["breakfast", "lunch", "dinner", "snack"]).nullable()

/** One food of a meal as the form sends it. */
export type ItemInput = z.infer<typeof itemSchema>

/** A mutation either succeeds with the meal or reports issues to show inline. */
export type MealResult =
  { ok: true; meal: Meal } | { ok: false; issues: Array<Issue> }

export const getDay = createServerFn({ method: "GET" })
  .validator(z.object({ date: z.iso.date() }))
  .handler(async ({ data }) =>
    unwrap(
      await api.GET("/api/log/days/{day}", {
        params: { path: { day: data.date } },
      })
    )
  )

export const createMeal = createServerFn({ method: "POST" })
  .validator(
    z.object({
      eaten_at: z.string().optional(),
      kind: kindSchema.optional(),
      note: z.string().max(2000).nullable().optional(),
      items: z.array(itemSchema).max(100),
      dry_run: z.boolean().optional(),
    })
  )
  .handler(async ({ data }): Promise<MealResult> => {
    const { dry_run, ...body } = data
    const result = await api.POST("/api/log/meals", {
      params: { query: { dry_run: dry_run ?? false } },
      body,
    })
    return result.data
      ? { ok: true, meal: result.data }
      : { ok: false, issues: toIssues(result.error) }
  })

export const updateMeal = createServerFn({ method: "POST" })
  .validator(
    z.object({
      id: z.number().int(),
      eaten_at: z.string().optional(),
      kind: kindSchema.optional(),
      note: z.string().max(2000).nullable().optional(),
      items: z.array(itemSchema).max(100).optional(),
    })
  )
  .handler(async ({ data }): Promise<MealResult> => {
    const { id, ...body } = data
    const result = await api.PATCH("/api/log/meals/{meal_id}", {
      params: { path: { meal_id: id } },
      body,
    })
    return result.data
      ? { ok: true, meal: result.data }
      : { ok: false, issues: toIssues(result.error) }
  })

export const deleteMeal = createServerFn({ method: "POST" })
  .validator(z.object({ id: z.number().int() }))
  .handler(async ({ data }) => {
    const result = await api.DELETE("/api/log/meals/{meal_id}", {
      params: { path: { meal_id: data.id } },
    })
    if (!result.response.ok) {
      throw new Error(
        toIssues(result.error)
          .map((issue) => issue.message)
          .join("; ")
      )
    }
    return { deleted: data.id }
  })
