import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query"
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router"
import {
  ArrowLeftIcon,
  CookingPotIcon,
  GitBranchIcon,
  GitForkIcon,
  MoreHorizontalIcon,
  PlusIcon,
} from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"
import { ChangeList, diffAmounts } from "@/components/recipes/change-list"
import { CookRow } from "@/components/recipes/cook-row"
import { CookSheet } from "@/components/recipes/cook-sheet"
import { IngredientList } from "@/components/recipes/ingredient-list"
import { PortionNutrition } from "@/components/recipes/portion-nutrition"
import { RecipeFormSheet } from "@/components/recipes/recipe-form-sheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { dayLabel, formatNumber } from "@/lib/format"
import { recipeQuery } from "@/lib/queries"
import { addVersion, createRecipe } from "@/server/recipes"
import type { CookStart } from "@/components/recipes/cook-sheet"
import type { Recipe, Version } from "@/lib/api/types"

export const Route = createFileRoute("/recipes/$slug")({
  loader: ({ context, params }) =>
    context.queryClient.ensureQueryData(recipeQuery(params.slug)),
  head: ({ loaderData }) => ({
    meta: [{ title: loaderData ? `${loaderData.name} · Health` : "Health" }],
  }),
  component: RecipePage,
})

/** The open form: a new version from a parent, or a fork of a version. */
type Editing = { kind: "version" | "fork"; version: Version } | null

function RecipePage() {
  const { slug } = Route.useParams()
  const { data: recipe } = useSuspenseQuery(recipeQuery(slug))
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [editing, setEditing] = useState<Editing>(null)
  const [cooking, setCooking] = useState<CookStart | null>(null)
  const latest = recipe.versions[0]
  const first = recipe.versions.at(-1)
  const forkedFrom =
    first?.parent && first.parent.recipe !== recipe.slug ? first.parent : null
  const start = useMemo(
    () =>
      editing
        ? {
            name:
              editing.kind === "fork"
                ? `${recipe.name} (variation)`
                : undefined,
            portions: editing.version.portions,
            instructions: editing.version.instructions,
            items: editing.version.items,
          }
        : {},
    [editing, recipe.name]
  )
  const cook = (version: Version) =>
    setCooking({
      kind: "version",
      recipe: recipe.slug,
      recipeName: recipe.name,
      version,
    })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <Button
          variant="ghost"
          size="sm"
          className="self-start"
          nativeButton={false}
          render={<Link to="/recipes" />}
        >
          <ArrowLeftIcon /> Recipes
        </Button>
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-64 flex-1">
            <h1 className="font-heading text-2xl font-semibold sm:text-3xl">
              {recipe.name}
            </h1>
            {recipe.note && (
              <p className="text-sm text-muted-foreground">{recipe.note}</p>
            )}
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge variant="secondary">
                {recipe.versions.length}{" "}
                {recipe.versions.length === 1 ? "version" : "versions"}
              </Badge>
              <Badge variant="outline">cooked {recipe.cooks.length}×</Badge>
              {forkedFrom && (
                <Badge
                  variant="outline"
                  render={
                    <Link
                      to="/recipes/$slug"
                      params={{ slug: forkedFrom.recipe }}
                    />
                  }
                >
                  <GitForkIcon aria-hidden /> from {forkedFrom.recipe_name} v
                  {forkedFrom.number}
                </Badge>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setEditing({ kind: "version", version: latest })}
            >
              <PlusIcon /> New version
            </Button>
            <Button onClick={() => cook(latest)}>
              <CookingPotIcon /> Cook v{latest.number}
            </Button>
          </div>
        </div>
      </div>

      {recipe.forks.length > 0 && (
        <p className="flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground">
          <GitForkIcon aria-hidden className="size-4" /> Variations:
          {recipe.forks.map((fork) => (
            <Badge
              key={fork.slug}
              variant="secondary"
              render={<Link to="/recipes/$slug" params={{ slug: fork.slug }} />}
            >
              {fork.name} (from v{fork.from_version})
            </Badge>
          ))}
        </p>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-muted-foreground">History</h2>
        <ol className="flex flex-col gap-3">
          {recipe.versions.map((version, index) => (
            <li key={version.id}>
              <VersionCard
                recipe={recipe}
                version={version}
                latest={index === 0}
                onCook={() => cook(version)}
                onNewVersion={() => setEditing({ kind: "version", version })}
                onFork={() => setEditing({ kind: "fork", version })}
              />
            </li>
          ))}
        </ol>
      </section>

      <RecipeFormSheet
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        title={
          editing?.kind === "fork"
            ? `New recipe from v${editing.version.number}`
            : `New version from v${editing?.version.number ?? ""}`
        }
        description={
          editing?.kind === "fork"
            ? "A variation that develops on its own, linked to where it came from."
            : "Change ingredients or portions and say why; the old version stays."
        }
        submitLabel={
          editing?.kind === "fork" ? "Create variation" : "Save version"
        }
        showName={editing?.kind === "fork"}
        noteLabel={editing?.kind === "fork" ? "About" : "What changed and why?"}
        notePlaceholder={
          editing?.kind === "fork"
            ? "e.g. mango instead of berries"
            : "e.g. less salt, v2 was too salty"
        }
        start={start}
        onSubmit={async (values) => {
          if (!editing) return { ok: false, issues: [] }
          if (editing.kind === "fork") {
            const result = await createRecipe({
              data: {
                name: values.name,
                note: values.note,
                portions: values.portions,
                items: values.items,
                instructions: values.instructions,
                forked_from: {
                  recipe: recipe.slug,
                  version: editing.version.number,
                },
              },
            })
            if (result.ok) {
              toast.success("Variation created")
              await queryClient.invalidateQueries({ queryKey: ["recipe"] })
              await queryClient.invalidateQueries({ queryKey: ["recipes"] })
              await navigate({
                to: "/recipes/$slug",
                params: { slug: result.value.slug },
              })
            }
            return result
          }
          const result = await addVersion({
            data: {
              slug: recipe.slug,
              note: values.note,
              portions: values.portions,
              items: values.items,
              instructions: values.instructions,
              parent: editing.version.number,
            },
          })
          if (result.ok) {
            toast.success(`Saved v${result.value.number}`)
            await queryClient.invalidateQueries({ queryKey: ["recipe", slug] })
            await queryClient.invalidateQueries({ queryKey: ["recipes"] })
          }
          return result
        }}
      />
      <CookSheet
        start={cooking}
        onOpenChange={(open) => !open && setCooking(null)}
      />
    </div>
  )
}

function VersionCard({
  recipe,
  version,
  latest,
  onCook,
  onNewVersion,
  onFork,
}: {
  recipe: Recipe
  version: Version
  latest: boolean
  onCook: () => void
  onNewVersion: () => void
  onFork: () => void
}) {
  const parent =
    version.parent?.recipe === recipe.slug
      ? recipe.versions.find((other) => other.number === version.parent?.number)
      : undefined
  const changes = parent ? diffAmounts(parent.items, version.items) : []
  const cooks = recipe.cooks.filter((cook) => cook.version === version.number)

  return (
    <Card size="sm">
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={latest ? "default" : "secondary"}>
            v{version.number}
          </Badge>
          <span className="text-sm text-muted-foreground">
            {dayLabel(version.created_at.slice(0, 10))}
            {parent && version.parent?.number !== version.number - 1 && (
              <> · from v{parent.number}</>
            )}
            {version.from_cook_id !== null && (
              <>
                {" · "}
                <Link
                  to="/cooks/$id"
                  params={{ id: version.from_cook_id }}
                  className="underline-offset-2 hover:underline"
                >
                  saved from a cook
                </Link>
              </>
            )}
          </span>
          <span className="ml-auto text-sm text-muted-foreground tabular-nums">
            {formatNumber(version.portions)} portions
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Actions for v${version.number}`}
                />
              }
            >
              <MoreHorizontalIcon />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={onCook}>
                <CookingPotIcon /> Cook this version
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onNewVersion}>
                <GitBranchIcon /> New version from here
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onFork}>
                <GitForkIcon /> New recipe from here
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {version.note && (
          <p className="border-l-2 border-primary/40 pl-3 text-sm whitespace-pre-wrap">
            {version.note}
          </p>
        )}
        {changes.length > 0 && <ChangeList changes={changes} />}
        <PortionNutrition perPortion={version.per_portion} compact={!latest} />

        <details open={latest} className="group text-sm">
          <summary className="cursor-pointer text-muted-foreground select-none hover:text-foreground">
            {version.items.length} ingredients
            {version.instructions ? " and steps" : ""}
          </summary>
          <div className="mt-3 flex flex-col gap-4">
            <IngredientList items={version.items} />
            {version.instructions && (
              <p className="whitespace-pre-wrap text-muted-foreground">
                {version.instructions}
              </p>
            )}
          </div>
        </details>

        {cooks.length > 0 && (
          <div className="flex flex-col gap-2">
            {cooks.map((cook) => (
              <CookRow key={cook.id} cook={cook} showName={false} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
