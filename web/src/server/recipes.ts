import { notFound } from "@tanstack/react-router"
import { createServerFn } from "@tanstack/react-start"
import { z } from "zod"
import { api, toIssues, unwrap } from "./api"
import { foodAmountSchema } from "./log"
import type { Cook, Issue, Recipe, Version } from "@/lib/api/types"

/** A mutation either succeeds with its result or reports issues to show inline. */
export type Result<T> =
  { ok: true; value: T } | { ok: false; issues: Array<Issue> }

function result<T>(response: { data?: T; error?: unknown }): Result<T> {
  return response.data !== undefined
    ? { ok: true, value: response.data }
    : { ok: false, issues: toIssues(response.error) }
}

const items = z.array(foodAmountSchema).min(1).max(100)
const note = z.string().max(2000).nullable().optional()
const portions = z.number().positive().max(100)
const instructions = z.string().max(20000).nullable().optional()

export const listRecipes = createServerFn({ method: "GET" })
  .validator(z.object({ q: z.string().max(200).optional() }))
  .handler(async ({ data }) =>
    unwrap(await api.GET("/api/recipes", { params: { query: data } }))
  )

export const getRecipe = createServerFn({ method: "GET" })
  .validator(z.object({ slug: z.string().min(1).max(200) }))
  .handler(async ({ data }) => {
    const response = await api.GET("/api/recipes/{slug}", {
      params: { path: { slug: data.slug } },
    })
    if (response.response.status === 404) throw notFound()
    return unwrap(response)
  })

export const createRecipe = createServerFn({ method: "POST" })
  .validator(
    z.object({
      name: z.string().min(1).max(200),
      note,
      items: items.optional(),
      portions: portions.optional(),
      instructions,
      forked_from: z
        .object({ recipe: z.string(), version: z.number().int().optional() })
        .optional(),
      from_cook: z.number().int().optional(),
    })
  )
  .handler(async ({ data }): Promise<Result<Recipe>> =>
    result(await api.POST("/api/recipes", { body: data }))
  )

export const addVersion = createServerFn({ method: "POST" })
  .validator(
    z.object({
      slug: z.string().min(1).max(200),
      note,
      items: items.optional(),
      portions: portions.optional(),
      instructions,
      parent: z.number().int().optional(),
      from_cook: z.number().int().optional(),
    })
  )
  .handler(async ({ data }): Promise<Result<Version>> => {
    const { slug, ...body } = data
    return result(
      await api.POST("/api/recipes/{slug}/versions", {
        params: { path: { slug } },
        body,
      })
    )
  })

export const listCooks = createServerFn({ method: "GET" })
  .validator(
    z.object({
      recipe: z.string().max(200).optional(),
      q: z.string().max(200).optional(),
      limit: z.number().int().min(1).max(200).optional(),
    })
  )
  .handler(async ({ data }) =>
    unwrap(await api.GET("/api/cooks", { params: { query: data } }))
  )

export const getCook = createServerFn({ method: "GET" })
  .validator(z.object({ id: z.number().int() }))
  .handler(async ({ data }) => {
    const response = await api.GET("/api/cooks/{cook_id}", {
      params: { path: { cook_id: data.id } },
    })
    if (response.response.status === 404) throw notFound()
    return unwrap(response)
  })

const cookFields = {
  name: z.string().min(1).max(200).optional(),
  cooked_at: z.string().optional(),
  portions: portions.optional(),
  weight_g: z.number().positive().max(50000).nullable().optional(),
  note,
  items: items.optional(),
}

export const createCook = createServerFn({ method: "POST" })
  .validator(
    z.object({
      recipe: z.string().min(1).max(200).optional(),
      version: z.number().int().optional(),
      ...cookFields,
      dry_run: z.boolean().optional(),
    })
  )
  .handler(async ({ data }): Promise<Result<Cook>> => {
    const { dry_run, ...body } = data
    return result(
      await api.POST("/api/cooks", {
        params: { query: { dry_run: dry_run ?? false } },
        body,
      })
    )
  })

export const updateCook = createServerFn({ method: "POST" })
  .validator(z.object({ id: z.number().int(), ...cookFields }))
  .handler(async ({ data }): Promise<Result<Cook>> => {
    const { id, ...body } = data
    return result(
      await api.PATCH("/api/cooks/{cook_id}", {
        params: { path: { cook_id: id } },
        body,
      })
    )
  })

export const deleteCook = createServerFn({ method: "POST" })
  .validator(z.object({ id: z.number().int() }))
  .handler(async ({ data }) => {
    const response = await api.DELETE("/api/cooks/{cook_id}", {
      params: { path: { cook_id: data.id } },
    })
    if (!response.response.ok) {
      throw new Error(
        toIssues(response.error)
          .map((issue) => issue.message)
          .join("; ")
      )
    }
    return { deleted: data.id }
  })
