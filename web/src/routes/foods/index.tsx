import {
  useSuspenseInfiniteQuery,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router"
import { ListFilterIcon, SearchIcon, XIcon } from "lucide-react"
import { useEffect, useState } from "react"
import { z } from "zod"
import { FoodGroupNav, groupIcon } from "@/components/food-groups"
import { MacroBar } from "@/components/nutrition/macro-bar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { Spinner } from "@/components/ui/spinner"
import { capitalize, formatNumber } from "@/lib/format"
import { energySplit } from "@/lib/macros"
import { facetsQuery, foodsInfiniteQuery } from "@/lib/queries"
import type { FoodSummary } from "@/lib/api/types"

const SORTS = [
  { value: "relevance", label: "Best match" },
  { value: "name", label: "Name" },
  { value: "protein_density_desc", label: "Most protein per kcal" },
  { value: "protein_desc", label: "Most protein" },
  { value: "energy_asc", label: "Fewest calories" },
  { value: "energy_desc", label: "Most calories" },
  { value: "fiber_desc", label: "Most fiber" },
] as const

const searchSchema = z.object({
  q: z.string().max(100).optional(),
  group: z.string().length(1).optional(),
  kind: z.string().optional(),
  prep: z.string().optional(),
  sort: z.string().optional(),
})
type Search = z.infer<typeof searchSchema>

function listSearch(search: Search) {
  return {
    q: search.q,
    group: search.group,
    kind: search.kind,
    preparation_state: search.prep,
    // Without a query the API lists alphabetically for "relevance".
    sort: search.sort,
  }
}

function facetFilters(search: Search) {
  return {
    q: search.q,
    group: search.group,
    kind: search.kind,
    preparation_state: search.prep,
  }
}

/** Facet values as select options, with their counts. */
function facetOptions(values: Array<{ value: string; count: number }>) {
  return values.map(({ value, count }) => ({
    value,
    label: `${capitalize(value)} (${formatNumber(count, 0)})`,
  }))
}

export const Route = createFileRoute("/foods/")({
  validateSearch: searchSchema,
  loaderDeps: ({ search }) => search,
  loader: ({ context, deps }) =>
    Promise.all([
      context.queryClient.ensureInfiniteQueryData(
        foodsInfiniteQuery(listSearch(deps))
      ),
      context.queryClient.ensureQueryData(facetsQuery(facetFilters(deps))),
    ]),
  component: FoodsPage,
})

function FoodsPage() {
  const search = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const { data: facets } = useSuspenseQuery(facetsQuery(facetFilters(search)))
  const foods = useSuspenseInfiniteQuery(foodsInfiniteQuery(listSearch(search)))
  const items = foods.data.pages.flatMap((page) => page.items)
  const total = foods.data.pages[0]?.total ?? 0

  // Type freely; the URL (and the query) follows after a short pause.
  const [text, setText] = useState(search.q ?? "")
  useEffect(() => {
    const handle = setTimeout(() => {
      if ((search.q ?? "") !== text) {
        void navigate({
          search: (prev) => ({ ...prev, q: text || undefined }),
          replace: true,
        })
      }
    }, 250)
    return () => clearTimeout(handle)
  }, [text, search.q, navigate])

  // Search, category, type, and preparation filter; the sort is a view
  // preference and survives clearing (except "relevance", which needs a search).
  const activeFilters = [
    search.q,
    search.group,
    search.kind,
    search.prep,
  ].filter(Boolean).length
  const clearFilters = () => {
    setText("")
    return navigate({
      search: (prev) => ({
        sort: prev.sort === "relevance" ? undefined : prev.sort,
      }),
    })
  }

  const set = (key: keyof Search, value: string | undefined) =>
    navigate({
      search: (prev) => ({ ...prev, [key]: value || undefined }),
      replace: true,
    })

  const activeGroup = facets.groups.find((group) => group.code === search.group)
  const GroupIcon = groupIcon(search.group)
  const [groupsOpen, setGroupsOpen] = useState(false)

  return (
    <div className="grid gap-6 lg:grid-cols-[17rem_minmax(0,1fr)]">
      {/* Food groups: a sidebar on wide screens, a sheet on phones. */}
      <aside className="hidden lg:block">
        <div className="sticky top-18 max-h-[calc(100svh-5.5rem)] overflow-y-auto pr-1 pb-4">
          <div className="mb-2 px-2.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Categories
          </div>
          <FoodGroupNav facets={facets} active={search.group} />
        </div>
      </aside>

      <div className="flex min-w-0 flex-col gap-4">
        <div className="flex items-center gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-secondary text-secondary-foreground">
            <GroupIcon className="size-5" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="truncate font-heading text-2xl font-semibold">
              {activeGroup ? activeGroup.name : "All foods"}
            </h1>
            <div className="text-sm text-muted-foreground tabular-nums">
              {formatNumber(total, 0)} {total === 1 ? "food" : "foods"}
              {search.q && ` for “${search.q}”`}
            </div>
          </div>
          <Sheet open={groupsOpen} onOpenChange={setGroupsOpen}>
            <SheetTrigger
              render={<Button variant="outline" className="lg:hidden" />}
            >
              <ListFilterIcon /> Categories
            </SheetTrigger>
            <SheetContent side="left" className="w-72 gap-0">
              <SheetHeader>
                <SheetTitle>Categories</SheetTitle>
              </SheetHeader>
              <div className="overflow-y-auto px-2 pb-6">
                <FoodGroupNav
                  facets={facets}
                  active={search.group}
                  onNavigate={() => setGroupsOpen(false)}
                />
              </div>
            </SheetContent>
          </Sheet>
        </div>

        <div className="sticky top-14 z-30 -mx-4 flex flex-col gap-3 bg-background/90 px-4 py-2 backdrop-blur lg:mx-0 lg:px-0">
          <InputGroup className="h-10 bg-card">
            <InputGroupAddon>
              <SearchIcon />
            </InputGroupAddon>
            <InputGroupInput
              type="search"
              placeholder="Search foods, German names, codes, barcodes"
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
          </InputGroup>

          <div className="flex flex-wrap items-center gap-2">
            <SmallSelect
              label="Type"
              value={search.kind}
              placeholder="All types"
              options={facetOptions(facets.kinds)}
              onChange={(value) => set("kind", value)}
            />
            <SmallSelect
              label="Preparation"
              value={search.prep}
              placeholder="Any preparation"
              options={facetOptions(facets.preparation_states)}
              onChange={(value) => set("prep", value)}
            />
            {activeFilters > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void clearFilters()}
              >
                <XIcon /> Clear filters ({activeFilters})
              </Button>
            )}
            <div className="ml-auto">
              <SmallSelect
                label="Sort"
                value={search.sort}
                placeholder={search.q ? "Best match" : "Name"}
                options={SORTS.filter(
                  (sort) => search.q || sort.value !== "relevance"
                ).map((sort) => ({ value: sort.value, label: sort.label }))}
                onChange={(value) => set("sort", value)}
              />
            </div>
          </div>
        </div>

        {items.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-12 text-center text-muted-foreground">
            <p>No matching foods.</p>
            {activeFilters > 0 && (
              <Button variant="outline" onClick={() => void clearFilters()}>
                <XIcon /> Clear filters
              </Button>
            )}
          </div>
        ) : (
          <ul className="grid gap-2 xl:grid-cols-2">
            {items.map((food) => (
              <li key={food.slug}>
                <FoodCard food={food} />
              </li>
            ))}
          </ul>
        )}

        {foods.hasNextPage && (
          <Button
            variant="outline"
            className="self-center"
            disabled={foods.isFetchingNextPage}
            onClick={() => void foods.fetchNextPage()}
          >
            {foods.isFetchingNextPage && <Spinner />}
            Load more ({formatNumber(total - items.length, 0)} left)
          </Button>
        )}
      </div>
    </div>
  )
}

function FoodCard({ food }: { food: FoodSummary }) {
  const source = food.source
  const parts = source ? energySplit(source) : null
  const secondary = food.brand ?? food.aliases.at(0)
  return (
    <Link
      to="/foods/$slug"
      params={{ slug: food.slug }}
      className="flex flex-col gap-2 rounded-xl bg-card p-3 ring-1 ring-foreground/10 transition-colors hover:bg-accent/60 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="leading-snug font-medium">{food.name}</div>
          {secondary && (
            <div className="truncate text-xs text-muted-foreground">
              {secondary}
            </div>
          )}
        </div>
        <div className="shrink-0 text-right">
          <span className="font-heading text-lg font-semibold tabular-nums">
            {formatNumber(source?.energy_kcal, 0)}
          </span>
          <span className="ml-1 text-xs text-muted-foreground">
            kcal/{formatNumber(source?.reference_quantity, 0)}
            {source?.reference_unit}
          </span>
        </div>
      </div>
      <MacroBar parts={parts} />
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <Macro
          color="var(--macro-protein)"
          label="Protein"
          value={source?.protein_g}
        />
        <Macro color="var(--macro-fat)" label="Fat" value={source?.fat_g} />
        <Macro
          color="var(--macro-carbs)"
          label="Carbs"
          value={source?.carbs_g}
        />
        {food.kind === "branded" ? (
          <Badge variant="secondary" className="ml-auto">
            branded
          </Badge>
        ) : (
          source?.protein_per_100_kcal && (
            <span className="ml-auto tabular-nums">
              {formatNumber(source.protein_per_100_kcal)} g P/100 kcal
            </span>
          )
        )}
      </div>
    </Link>
  )
}

function Macro({
  color,
  label,
  value,
}: {
  color: string
  label: string
  value: string | null | undefined
}) {
  return (
    <span className="flex items-center gap-1">
      <span
        aria-hidden
        className="size-2 rounded-full"
        style={{ background: color }}
      />
      {label}
      <span className="font-medium text-foreground tabular-nums">
        {formatNumber(value)} g
      </span>
    </span>
  )
}

function SmallSelect({
  label,
  value,
  placeholder,
  options,
  onChange,
}: {
  label: string
  value: string | undefined
  placeholder: string
  options: Array<{ value: string; label: string }>
  onChange: (value: string | undefined) => void
}) {
  const ALL = "__all__"
  return (
    <Select
      value={value ?? ALL}
      onValueChange={(next) =>
        onChange(next === ALL || next === null ? undefined : next)
      }
      items={[{ value: ALL, label: placeholder }, ...options]}
    >
      <SelectTrigger size="sm" aria-label={label} className="bg-card">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{placeholder}</SelectItem>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
