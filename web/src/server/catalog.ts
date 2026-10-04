import { notFound } from "@tanstack/react-router"
import { createServerFn } from "@tanstack/react-start"
import { z } from "zod"
import { api, unwrap } from "./api"

export const foodSearchSchema = z.object({
  q: z.string().max(100).optional(),
  group: z.string().length(1).optional(),
  brand: z.string().max(100).optional(),
  kind: z.string().max(60).optional(),
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
