import { infiniteQueryOptions, queryOptions } from "@tanstack/react-query"
import { getFacets, getFood, searchFoods } from "@/server/catalog"
import type { FacetFilters, FoodSearch } from "@/server/catalog"
import { getDay } from "@/server/log"
import { getCook, getRecipe, listCooks, listRecipes } from "@/server/recipes"

export const dayQuery = (date: string) =>
  queryOptions({
    queryKey: ["day", date],
    queryFn: () => getDay({ data: { date } }),
  })

export const foodsQuery = (search: FoodSearch) =>
  queryOptions({
    queryKey: ["foods", search],
    queryFn: () => searchFoods({ data: search }),
  })

export const foodQuery = (slug: string) =>
  queryOptions({
    queryKey: ["food", slug],
    queryFn: () => getFood({ data: { slug } }),
  })

/** Filter values with counts under the other active filters. */
export const facetsQuery = (filters: FacetFilters = {}) =>
  queryOptions({
    queryKey: ["facets", filters],
    queryFn: () => getFacets({ data: filters }),
    staleTime: 5 * 60 * 1000,
  })

export const FOODS_PAGE = 40

/** The catalog list, loaded page by page for "Load more". */
export const foodsInfiniteQuery = (
  search: Omit<FoodSearch, "limit" | "offset">
) =>
  infiniteQueryOptions({
    queryKey: ["foods-infinite", search],
    queryFn: ({ pageParam }) =>
      searchFoods({
        data: { ...search, limit: FOODS_PAGE, offset: pageParam },
      }),
    initialPageParam: 0,
    getNextPageParam: (last, _pages, offset) =>
      offset + FOODS_PAGE < last.total ? offset + FOODS_PAGE : undefined,
  })

export const recipesQuery = (q?: string) =>
  queryOptions({
    queryKey: ["recipes", q ?? ""],
    queryFn: () => listRecipes({ data: q ? { q } : {} }),
  })

export const recipeQuery = (slug: string) =>
  queryOptions({
    queryKey: ["recipe", slug],
    queryFn: () => getRecipe({ data: { slug } }),
  })

export const cooksQuery = (search: { recipe?: string; q?: string } = {}) =>
  queryOptions({
    queryKey: ["cooks", search],
    queryFn: () => listCooks({ data: search }),
  })

export const cookQuery = (id: number) =>
  queryOptions({
    queryKey: ["cook", id],
    queryFn: () => getCook({ data: { id } }),
  })
