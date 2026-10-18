import { notFound } from "@tanstack/react-router"
import { createServerFn } from "@tanstack/react-start"
import { z } from "zod"
import { api, toIssues, unwrap } from "./api"
import type { FoodDeletion, Issue } from "@/lib/api/types"

export const foodSearchSchema = z.object({
  q: z.string().max(100).optional(),
  group: z.string().length(1).optional(),
  brand: z.string().max(100).optional(),
  kind: z.string().max(60).optional(),
  source_name: z.string().max(100).optional(),
  preparation_state: z.string().max(60).optional(),
  incomplete: z.boolean().optional(),
  sort: z.string().max(40).optional(),
  limit: z.number().int().min(1).max(100).optional(),
  offset: z.number().int().min(0).optional(),
})
export type FoodSearch = z.infer<typeof foodSearchSchema>

export const searchFoods = createServerFn({ method: "GET" })
  .validator(foodSearchSchema)
  .handler(async ({ data }) =>
    unwrap(
      await api.GET("/api/foods", {
        // The API validates `sort` against its own list.
        params: { query: data as never },
      })
    )
  )

export const getFood = createServerFn({ method: "GET" })
  .validator(z.object({ slug: z.string().min(1).max(200) }))
  .handler(async ({ data }) => {
    const result = await api.GET("/api/foods/{slug}", {
      params: { path: { slug: data.slug } },
    })
    // Lets the route render its not-found page instead of an error.
    if (result.response.status === 404) throw notFound()
    return unwrap(result)
  })

export const facetFiltersSchema = foodSearchSchema.pick({
  q: true,
  group: true,
  brand: true,
  kind: true,
  source_name: true,
  preparation_state: true,
  incomplete: true,
})
export type FacetFilters = z.infer<typeof facetFiltersSchema>

export const getFacets = createServerFn({ method: "GET" })
  .validator(facetFiltersSchema)
  .handler(async ({ data }) =>
    unwrap(await api.GET("/api/foods/facets", { params: { query: data } }))
  )

/** Set a food's group, brand, or generic food; null clears it. */
export const updateFood = createServerFn({ method: "POST" })
  .validator(
    z.object({
      slug: z.string().min(1).max(200),
      food_group: z.string().length(1).nullable().optional(),
      brand: z.string().min(1).max(100).nullable().optional(),
      variant_of: z.string().min(1).max(200).nullable().optional(),
    })
  )
  .handler(async ({ data }) => {
    const { slug, ...body } = data
    return unwrap(
      await api.PATCH("/api/foods/{slug}", { params: { path: { slug } }, body })
    )
  })

export type DeletionResult =
  { ok: true; deletion: FoodDeletion } | { ok: false; issues: Array<Issue> }

/**
 * Delete a registered product. One still used in meals, recipes or cooks needs
 * `replace_with`: its uses move to that food first. A dry run only reports.
 */
export const deleteFood = createServerFn({ method: "POST" })
  .validator(
    z.object({
      slug: z.string().min(1).max(200),
      replace_with: z.string().min(1).max(200).optional(),
      dry_run: z.boolean().optional(),
    })
  )
  .handler(async ({ data }): Promise<DeletionResult> => {
    const result = await api.DELETE("/api/foods/{slug}", {
      params: {
        path: { slug: data.slug },
        query: {
          replace_with: data.replace_with,
          dry_run: data.dry_run ?? false,
        },
      },
    })
    return result.data
      ? { ok: true, deletion: result.data }
      : { ok: false, issues: toIssues(result.error) }
  })
