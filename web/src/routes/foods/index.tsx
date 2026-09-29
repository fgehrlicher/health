import {
  useSuspenseInfiniteQuery,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router"
import { SearchIcon } from "lucide-react"
import { useEffect, useState } from "react"
import { z } from "zod"
import type { ReactNode } from "react"
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

export const Route = createFileRoute("/foods/")({
  validateSearch: searchSchema,
  loaderDeps: ({ search }) => search,
  loader: ({ context, deps }) =>
    Promise.all([
      context.queryClient.ensureInfiniteQueryData(
        foodsInfiniteQuery(listSearch(deps))
      ),
      context.queryClient.ensureQueryData(facetsQuery()),
    ]),
  component: FoodsPage,
})

function FoodsPage() {
  const search = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const { data: facets } = useSuspenseQuery(facetsQuery())
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

  const set = (key: keyof Search, value: string | undefined) =>
    navigate({
      search: (prev) => ({ ...prev, [key]: value || undefined }),
      replace: true,
    })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="font-heading text-2xl font-semibold">Foods</h1>
        <span className="text-sm text-muted-foreground tabular-nums">
          {formatNumber(total, 0)} {total === 1 ? "food" : "foods"}
        </span>
      </div>

      <div className="sticky top-14 z-30 -mx-4 flex flex-col gap-3 bg-background/90 px-4 py-2 backdrop-blur">
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

        {/* Food groups as chips; scrolls sideways on narrow screens. */}
        <div
          className="-mx-4 flex [scrollbar-width:none] gap-2 overflow-x-auto px-4 pb-1"
          role="group"
          aria-label="Food group"
        >
          <Chip active={!search.group} onClick={() => set("group", undefined)}>
            All groups
          </Chip>
          {facets.groups.map((group) => {
            const code = String(group.code)
            return (
              <Chip
                key={code}
                active={search.group === code}
                onClick={() =>
                  set("group", search.group === code ? undefined : code)
                }
              >
                {group.name}
                <span className="ml-1 tabular-nums opacity-60">
                  {formatNumber(group.count, 0)}
                </span>
              </Chip>
            )
          })}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <SmallSelect
            label="Type"
            value={search.kind}
            placeholder="All types"
            options={facets.kinds.map((kind) => ({
              value: kind,
              label: capitalize(kind),
            }))}
            onChange={(value) => set("kind", value)}
          />
          <SmallSelect
            label="Preparation"
            value={search.prep}
            placeholder="Any preparation"
            options={facets.preparation_states.map((state) => ({
              value: state,
              label: capitalize(state),
            }))}
            onChange={(value) => set("prep", value)}
          />
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
        <p className="py-12 text-center text-muted-foreground">
          No matching foods.
        </p>
      ) : (
        <ul className="grid gap-2 lg:grid-cols-2">
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

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={
        active
          ? "shrink-0 rounded-full bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          : "shrink-0 rounded-full bg-card px-3 py-1.5 text-sm ring-1 ring-foreground/10 hover:bg-accent"
      }
    >
      {children}
    </button>
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
