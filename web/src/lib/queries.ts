import { infiniteQueryOptions, queryOptions } from "@tanstack/react-query"
import { getFacets, getFood, searchFoods } from "@/server/catalog"
import type { FoodSearch } from "@/server/catalog"
import { getDay } from "@/server/log"

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

export const facetsQuery = () =>
  queryOptions({
    queryKey: ["facets"],
    queryFn: () => getFacets(),
    staleTime: 10 * 60 * 1000,
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
