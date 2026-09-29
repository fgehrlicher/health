import { notFound } from "@tanstack/react-router"
import { createServerFn } from "@tanstack/react-start"
import { z } from "zod"
import { api, unwrap } from "./api"

export const foodSearchSchema = z.object({
  q: z.string().max(100).optional(),
  group: z.string().length(1).optional(),
  kind: z.string().max(60).optional(),
  preparation_state: z.string().max(60).optional(),
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

export const getFacets = createServerFn({ method: "GET" }).handler(async () =>
  unwrap(await api.GET("/api/foods/facets"))
)
