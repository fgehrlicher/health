import { useSuspenseQuery } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { ArrowLeftIcon, PlusIcon } from "lucide-react"
import { useState } from "react"
import { FoodGroupPicker } from "@/components/food-group-picker"
import { groupIcon } from "@/components/food-groups"
import { MealSheet } from "@/components/log/meal-sheet"
import { VariantOfPicker } from "@/components/variant-of-picker"
import { CompositionBar } from "@/components/nutrition/composition-bar"
import { EnergyDonut } from "@/components/nutrition/energy-donut"
import { ReferenceIntakeBars } from "@/components/nutrition/reference-intake-bars"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table"
import { capitalize, formatNumber, today } from "@/lib/format"
import { energySplit } from "@/lib/macros"
import { foodQuery } from "@/lib/queries"
import type { Source, SourceNutrient } from "@/lib/api/types"

export const Route = createFileRoute("/foods/$slug")({
  loader: ({ context, params }) =>
    context.queryClient.ensureQueryData(foodQuery(params.slug)),
  head: ({ loaderData }) => ({
    meta: [{ title: loaderData ? `${loaderData.name} · Health` : "Health" }],
  }),
  component: FoodPage,
})

function FoodPage() {
  const { slug } = Route.useParams()
  const { data: food } = useSuspenseQuery(foodQuery(slug))
  const [logging, setLogging] = useState(false)
  const unit = food.sources[0]?.reference_unit ?? "g"
  const GroupIcon = groupIcon(food.food_group ?? undefined)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <Button
          variant="ghost"
          size="sm"
          className="self-start"
          nativeButton={false}
          render={<Link to="/foods" />}
        >
          <ArrowLeftIcon /> Foods
        </Button>
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="font-heading text-2xl font-semibold sm:text-3xl">
              {food.name}
            </h1>
            {food.aliases.length > 0 && (
              <p className="text-sm text-muted-foreground">
                {food.aliases.join(" · ")}
              </p>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {food.kind === "generic" ? (
                food.food_group && (
                  <Badge
                    variant="secondary"
                    render={
                      <Link to="/foods" search={{ group: food.food_group }} />
                    }
                  >
                    <GroupIcon aria-hidden />
                    {food.food_group_name}
                  </Badge>
                )
              ) : (
                <FoodGroupPicker food={food} />
              )}
              <Badge variant="outline">{food.kind}</Badge>
              {food.brand && (
                <Badge
                  variant="outline"
                  render={<Link to="/foods" search={{ brand: food.brand }} />}
                >
                  {food.brand}
                </Badge>
              )}
              {food.preparation_state && (
                <Badge variant="outline">{food.preparation_state}</Badge>
              )}
              {food.barcode && <Badge variant="outline">{food.barcode}</Badge>}
              {food.portions.map((portion) => (
                <Badge key={portion.name} variant="outline">
                  {portion.name} · {formatNumber(portion.quantity)}{" "}
                  {portion.unit}
                </Badge>
              ))}
            </div>
          </div>
          <Button onClick={() => setLogging(true)}>
            <PlusIcon /> Log this food
          </Button>
        </div>
        {food.kind === "branded" && <VariantOfPicker food={food} />}
      </div>

      {food.variants.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-medium text-muted-foreground">
            Products of this kind
          </h2>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {food.variants.map((variant) => (
              <Link
                key={variant.slug}
                to="/foods/$slug"
                params={{ slug: variant.slug }}
                className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2.5 text-sm transition-colors hover:bg-muted/60"
              >
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate font-medium">{variant.name}</span>
                  <span className="truncate text-xs text-muted-foreground">
                    {variant.brand ?? "No brand"}
                  </span>
                </span>
                <span className="shrink-0 text-right text-xs text-muted-foreground tabular-nums">
                  {formatNumber(variant.energy_kcal, 0)} kcal ·{" "}
                  {formatNumber(variant.protein_g)} g protein
                  <br />
                  per {formatNumber(variant.reference_quantity)}{" "}
                  {variant.reference_unit}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {food.sources.map((source) => (
        <SourceView
          key={source.id}
          source={source}
          single={food.sources.length === 1}
        />
      ))}

      <MealSheet
        date={today()}
        meal={null}
        open={logging}
        onOpenChange={setLogging}
        initialFood={{ slug: food.slug, name: food.name, unit }}
      />
    </div>
  )
}

/** Rows in EU label order; indented rows are the "davon" parts. */
const LABEL_ROWS: Array<{
  field: keyof Source
  label: string
  sub?: boolean
  optional?: boolean
}> = [
  { field: "fat_g", label: "Fat" },
  { field: "saturated_fat_g", label: "of which saturated", sub: true },
  {
    field: "monounsaturated_fat_g",
    label: "of which monounsaturated",
    sub: true,
    optional: true,
  },
  {
    field: "polyunsaturated_fat_g",
    label: "of which polyunsaturated",
    sub: true,
    optional: true,
  },
  { field: "carbs_g", label: "Carbohydrate" },
  { field: "sugars_g", label: "of which sugars", sub: true },
  { field: "polyols_g", label: "of which polyols", sub: true, optional: true },
  { field: "starch_g", label: "of which starch", sub: true, optional: true },
  { field: "fiber_g", label: "Fiber" },
  { field: "protein_g", label: "Protein" },
  { field: "salt_g", label: "Salt" },
  { field: "alcohol_g", label: "Alcohol", optional: true },
]

const CATEGORY_TITLES: Record<string, string> = {
  vitamin: "Vitamins",
  mineral: "Minerals",
  fat: "Fats",
  other: "Other",
}

function SourceView({ source, single }: { source: Source; single: boolean }) {
  const parts = energySplit(source)
  const per100g =
    source.reference_unit === "g" && Number(source.reference_quantity) === 100
  const basis = `per ${formatNumber(source.reference_quantity)} ${source.reference_unit}`
  const water = source.nutrients.find((nutrient) => nutrient.key === "water")

  return (
    <section className="flex flex-col gap-4">
      {!single && (
        <h2 className="font-heading text-lg font-semibold">
          {source.source_name}
        </h2>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat
          label={`Energy ${basis}`}
          value={formatNumber(source.energy_kcal, 0)}
          unit="kcal"
        />
        <Stat label="Protein" value={formatNumber(source.protein_g)} unit="g" />
        <Stat
          label="Protein / 100 kcal"
          value={formatNumber(source.protein_per_100_kcal)}
          unit="g"
          highlight
        />
        <Stat
          label="Energy"
          value={formatNumber(source.energy_kj, 0)}
          unit="kJ"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Where the energy comes from</CardTitle>
            <CardDescription>
              Calories from each macronutrient, with EU conversion factors.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {parts ? (
              <EnergyDonut parts={parts} />
            ) : (
              <p className="text-sm text-muted-foreground">
                Unknown: this source lists no macronutrients.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>What 100 g contain</CardTitle>
            <CardDescription>
              By weight, including water where known.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {parts && per100g ? (
              <CompositionBar
                parts={parts}
                water={water ? Number(water.amount) : null}
              />
            ) : (
              <p className="text-sm text-muted-foreground">
                Only shown for values per 100 g.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Nutrition label</CardTitle>
            <CardDescription>
              {source.source_name} · {source.food_name}
              {source.external_id && ` · ${source.external_id}`}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <LabelTable source={source} basis={basis} />
            {source.ingredients_text && (
              <div className="text-sm">
                <div className="mb-1 font-medium">Ingredients</div>
                <p className="text-muted-foreground">
                  {source.ingredients_text}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {source.nutrients.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Vitamins & minerals</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <ReferenceIntakeBars nutrients={source.nutrients} basis={basis} />
              <details className="text-sm">
                <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                  All values
                </summary>
                <div className="mt-3 grid gap-4 sm:grid-cols-2">
                  {Object.entries(CATEGORY_TITLES).map(([category, title]) => (
                    <NutrientGroup
                      key={category}
                      title={title}
                      nutrients={source.nutrients.filter(
                        (nutrient) => nutrient.category === category
                      )}
                    />
                  ))}
                </div>
              </details>
            </CardContent>
          </Card>
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        A dash means unknown, not zero. Values {basis}.
      </p>
    </section>
  )
}

function Stat({
  label,
  value,
  unit,
  highlight,
}: {
  label: string
  value: string
  unit: string
  highlight?: boolean
}) {
  return (
    <div
      className={
        highlight
          ? "rounded-xl bg-secondary p-3 text-secondary-foreground"
          : "rounded-xl bg-card p-3 ring-1 ring-foreground/10"
      }
    >
      <div className="text-xs opacity-75">{label}</div>
      <div className="mt-1 font-heading text-2xl font-semibold tabular-nums">
        {value}
        <span className="ml-1 text-sm font-normal opacity-75">{unit}</span>
      </div>
    </div>
  )
}

function LabelTable({ source, basis }: { source: Source; basis: string }) {
  const rows = LABEL_ROWS.filter(
    (row) => !row.optional || Number(source[row.field]) > 0
  )
  const upper = new Set(source.upper_bounds)
  return (
    <Table>
      <TableBody>
        <TableRow>
          <TableCell className="font-medium">Energy</TableCell>
          <TableCell className="text-right tabular-nums">
            {formatNumber(source.energy_kj, 0)} kJ /{" "}
            {formatNumber(source.energy_kcal, 0)} kcal
          </TableCell>
        </TableRow>
        {rows.map((row) => (
          <TableRow key={row.field}>
            <TableCell className={row.sub ? "pl-6 text-muted-foreground" : ""}>
              {row.label}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {source[row.field] === null
                ? "–"
                : `${upper.has(row.field) ? "< " : ""}${formatNumber(source[row.field] as string, 2)} g`}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
      <caption className="mt-2 caption-bottom text-left text-xs text-muted-foreground">
        Values {basis}
      </caption>
    </Table>
  )
}

function NutrientGroup({
  title,
  nutrients,
}: {
  title: string
  nutrients: Array<SourceNutrient>
}) {
  if (nutrients.length === 0) return null
  return (
    <div>
      <div className="mb-1 text-xs font-medium text-muted-foreground">
        {capitalize(title)}
      </div>
      <Table>
        <TableBody>
          {nutrients.map((nutrient) => (
            <TableRow key={nutrient.key}>
              <TableCell>{nutrient.name}</TableCell>
              <TableCell className="text-right tabular-nums">
                {nutrient.upper_bound ? "< " : ""}
                {formatNumber(nutrient.amount, 3)} {nutrient.unit}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
