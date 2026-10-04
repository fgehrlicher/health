import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query"
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router"
import { CookingPotIcon, PlusIcon, SearchIcon } from "lucide-react"
import { useMemo, useState } from "react"
import { z } from "zod"
import { toast } from "sonner"
import { CookRow } from "@/components/recipes/cook-row"
import { CookSheet } from "@/components/recipes/cook-sheet"
import { PortionNutrition } from "@/components/recipes/portion-nutrition"
import { RecipeFormSheet } from "@/components/recipes/recipe-form-sheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group"
import { capitalize, dayLabel, formatNumber } from "@/lib/format"
import { cooksQuery, recipesQuery, tagsQuery } from "@/lib/queries"
import { cn } from "@/lib/utils"
import { createRecipe } from "@/server/recipes"
import type { CookStart } from "@/components/recipes/cook-sheet"

const searchSchema = z.object({ tag: z.string().max(40).optional() })

export const Route = createFileRoute("/recipes/")({
  validateSearch: searchSchema,
  loaderDeps: ({ search }) => ({ tag: search.tag }),
  loader: ({ context, deps }) =>
    Promise.all([
      context.queryClient.ensureQueryData(recipesQuery()),
      context.queryClient.ensureQueryData(tagsQuery()),
      context.queryClient.ensureQueryData(cooksQuery(byTag(deps.tag))),
    ]),
  head: () => ({ meta: [{ title: "Recipes · Health" }] }),
  component: RecipesPage,
})

function byTag(tag: string | undefined) {
  return tag ? { tag } : {}
}

function RecipesPage() {
  const { tag } = Route.useSearch()
  const { data: all } = useSuspenseQuery(recipesQuery())
  const { data: tags } = useSuspenseQuery(tagsQuery())
  const { data: cooks } = useSuspenseQuery(cooksQuery(byTag(tag)))
  // All recipes are loaded once; the tag only narrows what is shown.
  const recipes = tag ? all.filter((recipe) => recipe.tags.includes(tag)) : all
  // A new recipe starts in the tag being browsed.
  const start = useMemo(() => ({ tags: tag ? [tag] : [] }), [tag])
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [text, setText] = useState("")
  const [creating, setCreating] = useState(false)
  const [cooking, setCooking] = useState<CookStart | null>(null)
  const words = text.toLowerCase().split(/\s+/).filter(Boolean)
  const shown = recipes.filter((recipe) =>
    words.every((word) => recipe.name.toLowerCase().includes(word))
  )

  return (
    <div className="grid gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
      <aside className="hidden lg:block" aria-label="Tags">
        <div className="sticky top-18 flex flex-col gap-0.5">
          <div className="mb-2 px-2.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Tags
          </div>
          <TagLink tag={undefined} count={all.length} active={!tag} />
          {tags.map((entry) => (
            <TagLink
              key={entry.tag}
              tag={entry.tag}
              count={entry.count}
              active={entry.tag === tag}
            />
          ))}
        </div>
      </aside>
      <div className="flex min-w-0 flex-col gap-8">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="mr-auto font-heading text-2xl font-semibold">
            {tag ? capitalize(tag) : "Recipes"}
          </h1>
          <Button
            variant="outline"
            onClick={() => setCooking({ kind: "improvised" })}
          >
            <CookingPotIcon /> Log improvised cook
          </Button>
          <Button onClick={() => setCreating(true)}>
            <PlusIcon /> New recipe
          </Button>
        </div>

        {tags.length > 0 && (
          <div
            className="-mt-4 flex flex-wrap gap-1.5 lg:hidden"
            aria-label="Tags"
          >
            <TagChip tag={undefined} count={all.length} active={!tag} />
            {tags.map((entry) => (
              <TagChip
                key={entry.tag}
                tag={entry.tag}
                count={entry.count}
                active={entry.tag === tag}
              />
            ))}
          </div>
        )}

        <section className="flex flex-col gap-3">
          {recipes.length > 0 && (
            <InputGroup className="max-w-sm bg-card">
              <InputGroupAddon>
                <SearchIcon />
              </InputGroupAddon>
              <InputGroupInput
                placeholder="Find a recipe"
                aria-label="Find a recipe"
                value={text}
                onChange={(event) => setText(event.target.value)}
              />
            </InputGroup>
          )}
          {recipes.length === 0 ? (
            <Empty className="border border-dashed">
              <EmptyHeader>
                <EmptyTitle>No recipes yet</EmptyTitle>
                <EmptyDescription>
                  A recipe is a list of catalog foods with amounts, split into
                  portions. Every improvement becomes a new version.
                </EmptyDescription>
              </EmptyHeader>
              <Button onClick={() => setCreating(true)}>
                <PlusIcon /> New recipe
              </Button>
            </Empty>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {shown.map((recipe) => (
                <Link
                  key={recipe.slug}
                  to="/recipes/$slug"
                  params={{ slug: recipe.slug }}
                  className="rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  <Card
                    size="sm"
                    className="h-full transition-colors hover:bg-muted/40"
                  >
                    <CardContent className="flex h-full flex-col gap-3">
                      <div>
                        <h2 className="font-heading font-semibold">
                          {recipe.name}
                        </h2>
                        <p className="text-xs text-muted-foreground">
                          v{recipe.latest_version} ·{" "}
                          {recipe.cooks === 0
                            ? "never cooked"
                            : `cooked ${recipe.cooks}× · last ${dayLabel(
                                (recipe.last_cooked_at ?? "").slice(0, 10)
                              )}`}
                        </p>
                        {recipe.tags.length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {recipe.tags.map((recipeTag) => (
                              <Badge key={recipeTag} variant="outline">
                                {recipeTag}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                      <PortionNutrition
                        perPortion={recipe.per_portion}
                        compact
                        className="mt-auto"
                      />
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-medium text-muted-foreground">
            Cooking log
          </h2>
          {cooks.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Cooks appear here with what went in and how many portions are
              left.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {cooks.map((cook) => (
                <CookRow key={cook.id} cook={cook} />
              ))}
            </div>
          )}
        </section>

        <RecipeFormSheet
          open={creating}
          onOpenChange={setCreating}
          title="New recipe"
          description="Ingredients and portions become version 1."
          submitLabel="Create recipe"
          showName
          noteLabel="About"
          notePlaceholder="Optional, e.g. meal prep for the week"
          start={start}
          onSubmit={async (values) => {
            const result = await createRecipe({
              data: {
                name: values.name,
                note: values.note,
                tags: values.tags,
                portions: values.portions,
                items: values.items,
                instructions: values.instructions,
              },
            })
            if (result.ok) {
              toast.success("Recipe created")
              await queryClient.invalidateQueries({ queryKey: ["recipes"] })
              await navigate({
                to: "/recipes/$slug",
                params: { slug: result.value.slug },
              })
            }
            return result
          }}
        />
        <CookSheet
          start={cooking}
          onOpenChange={(open) => !open && setCooking(null)}
        />
      </div>
    </div>
  )
}

/** A tag in the sidebar; no tag means all recipes. */
function TagLink({
  tag,
  count,
  active,
}: {
  tag: string | undefined
  count: number
  active: boolean
}) {
  return (
    <Link
      to="/recipes"
      search={tag ? { tag } : {}}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center justify-between rounded-lg px-2.5 py-1.5 text-sm transition-colors hover:bg-muted",
        active && "bg-primary text-primary-foreground hover:bg-primary/90"
      )}
    >
      <span className="truncate">{tag ? capitalize(tag) : "All recipes"}</span>
      <span className="text-xs tabular-nums opacity-70">
        {formatNumber(count, 0)}
      </span>
    </Link>
  )
}

/** A tag as a chip, for phones where the sidebar is hidden. */
function TagChip({
  tag,
  count,
  active,
}: {
  tag: string | undefined
  count: number
  active: boolean
}) {
  return (
    <Badge
      variant={active ? "default" : "outline"}
      render={<Link to="/recipes" search={tag ? { tag } : {}} />}
    >
      {tag ?? "all"} · {formatNumber(count, 0)}
    </Badge>
  )
}
