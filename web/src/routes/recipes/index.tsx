import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query"
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router"
import { CookingPotIcon, PlusIcon, SearchIcon } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"
import { CookRow } from "@/components/recipes/cook-row"
import { CookSheet } from "@/components/recipes/cook-sheet"
import { PortionNutrition } from "@/components/recipes/portion-nutrition"
import { RecipeFormSheet } from "@/components/recipes/recipe-form-sheet"
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
import { dayLabel } from "@/lib/format"
import { cooksQuery, recipesQuery } from "@/lib/queries"
import { createRecipe } from "@/server/recipes"
import type { CookStart } from "@/components/recipes/cook-sheet"

export const Route = createFileRoute("/recipes/")({
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.ensureQueryData(recipesQuery()),
      context.queryClient.ensureQueryData(cooksQuery()),
    ]),
  head: () => ({ meta: [{ title: "Recipes · Health" }] }),
  component: RecipesPage,
})

const EMPTY_START = {}

function RecipesPage() {
  const { data: recipes } = useSuspenseQuery(recipesQuery())
  const { data: cooks } = useSuspenseQuery(cooksQuery())
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
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-auto font-heading text-2xl font-semibold">Recipes</h1>
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
            Cooks appear here with what went in and how many portions are left.
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
        start={EMPTY_START}
        onSubmit={async (values) => {
          const result = await createRecipe({
            data: {
              name: values.name,
              note: values.note,
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
  )
}
