import {
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router"
import {
  ArrowLeftIcon,
  CookingPotIcon,
  GitBranchIcon,
  GitForkIcon,
  MoreHorizontalIcon,
  PencilIcon,
  PlusIcon,
} from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"
import { ChangeList } from "@/components/recipes/change-list"
import { CookRow } from "@/components/recipes/cook-row"
import { CookSheet } from "@/components/recipes/cook-sheet"
import { IngredientList } from "@/components/recipes/ingredient-list"
import { PortionNutrition } from "@/components/recipes/portion-nutrition"
import { RecipeFormSheet } from "@/components/recipes/recipe-form-sheet"
import { TagInput } from "@/components/recipes/tag-input"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { dayLabel, formatNumber } from "@/lib/format"
import { recipeQuery } from "@/lib/queries"
import {
  addVersion,
  createRecipe,
  updateRecipe,
  updateVersion,
} from "@/server/recipes"
import type { CookStart } from "@/components/recipes/cook-sheet"
import type { Recipe, Version } from "@/lib/api/types"
import { itemNames } from "@/lib/names"

export const Route = createFileRoute("/recipes/$slug")({
  loader: ({ context, params }) =>
    context.queryClient.ensureQueryData(recipeQuery(params.slug)),
  head: ({ loaderData }) => ({
    meta: [{ title: loaderData ? `${loaderData.name} · Health` : "Health" }],
  }),
  component: RecipePage,
})

/** The open form: a new version from a parent, or a fork of a version. */
type Editing = { kind: "edit" | "version" | "fork"; version: Version } | null

function RecipePage() {
  const { slug } = Route.useParams()
  const { data: recipe } = useSuspenseQuery(recipeQuery(slug))
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [editing, setEditing] = useState<Editing>(null)
  const [cooking, setCooking] = useState<CookStart | null>(null)
  const saveTags = useMutation({
    mutationFn: (tags: Array<string>) =>
      updateRecipe({ data: { slug: recipe.slug, tags } }),
    onSuccess: async (result) => {
      if (!result.ok) {
        toast.error(result.issues.map((issue) => issue.message).join("; "))
        return
      }
      queryClient.setQueryData(["recipe", slug], result.value)
      await queryClient.invalidateQueries({ queryKey: ["recipes"] })
    },
    onError: (error) => toast.error(error.message),
  })
  // The name and description are not versioned: changing them keeps every version.
  const [details, setDetails] = useState<{ name: string; note: string } | null>(
    null
  )
  const saveDetails = useMutation({
    mutationFn: (values: { name: string; note: string }) =>
      updateRecipe({
        data: {
          slug: recipe.slug,
          name: values.name.trim(),
          note: values.note.trim() || null,
        },
      }),
    onSuccess: async (result) => {
      if (!result.ok) {
        toast.error(result.issues.map((issue) => issue.message).join("; "))
        return
      }
      queryClient.setQueryData(["recipe", slug], result.value)
      await queryClient.invalidateQueries({ queryKey: ["recipes"] })
      setDetails(null)
    },
    onError: (error) => toast.error(error.message),
  })
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
            note: editing.kind === "edit" ? editing.version.note : undefined,
            tags: recipe.tags,
            portions: editing.version.portions,
            instructions: editing.version.instructions,
            items: editing.version.items,
          }
        : {},
    [editing, recipe.name, recipe.tags]
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
            <Button
              variant="ghost"
              size="sm"
              className="-ml-2"
              onClick={() =>
                setDetails({ name: recipe.name, note: recipe.note ?? "" })
              }
            >
              <PencilIcon /> Edit name and description
            </Button>
            <Dialog
              open={details !== null}
              onOpenChange={(open) => !open && setDetails(null)}
            >
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Edit name and description</DialogTitle>
                  <DialogDescription>
                    This does not create a new version. Every version keeps its
                    own note and steps.
                  </DialogDescription>
                </DialogHeader>
                {details && (
                  <form
                    className="flex flex-col gap-3"
                    onSubmit={(event) => {
                      event.preventDefault()
                      saveDetails.mutate(details)
                    }}
                  >
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="recipe-name">Name</Label>
                      <Input
                        id="recipe-name"
                        required
                        maxLength={200}
                        value={details.name}
                        onChange={(event) =>
                          setDetails({ ...details, name: event.target.value })
                        }
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="recipe-note">Description</Label>
                      <Textarea
                        id="recipe-note"
                        maxLength={2000}
                        value={details.note}
                        onChange={(event) =>
                          setDetails({ ...details, note: event.target.value })
                        }
                      />
                    </div>
                    <DialogFooter>
                      <Button
                        type="submit"
                        disabled={saveDetails.isPending || !details.name.trim()}
                      >
                        Save
                      </Button>
                    </DialogFooter>
                  </form>
                )}
              </DialogContent>
            </Dialog>
            {recipe.note && (
              <p className="text-sm text-muted-foreground">{recipe.note}</p>
            )}
            <TagInput
              className="mt-2"
              tags={recipe.tags}
              disabled={saveTags.isPending}
              onChange={(tags) => saveTags.mutate(tags)}
            />
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
                onEdit={() => setEditing({ kind: "edit", version })}
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
            : editing?.kind === "edit"
              ? `Edit v${editing.version.number}`
              : `New version from v${editing?.version.number ?? ""}`
        }
        description={
          editing?.kind === "fork"
            ? "A variation that develops on its own, linked to where it came from."
            : editing?.kind === "edit"
              ? "Fix ingredients, portions or steps in place; no new version. Cooks keep what went into them."
              : "Change ingredients or portions and say why; the old version stays."
        }
        submitLabel={
          editing?.kind === "fork"
            ? "Create variation"
            : editing?.kind === "edit"
              ? "Save changes"
              : "Save version"
        }
        showName={editing?.kind === "fork"}
        noteLabel={
          editing?.kind === "fork"
            ? "About"
            : editing?.kind === "edit"
              ? "Note"
              : "What changed and why?"
        }
        notePlaceholder={
          editing?.kind === "fork"
            ? "e.g. mango instead of berries"
            : editing?.kind === "edit"
              ? "e.g. what this version is about"
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
                tags: values.tags,
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
          if (editing.kind === "edit") {
            const edited = await updateVersion({
              data: {
                slug: recipe.slug,
                number: editing.version.number,
                note: values.note,
                portions: values.portions,
                items: values.items,
                instructions: values.instructions,
              },
            })
            if (edited.ok) {
              toast.success(`Saved v${edited.value.number}`)
              await queryClient.invalidateQueries({
                queryKey: ["recipe", slug],
              })
              await queryClient.invalidateQueries({ queryKey: ["recipes"] })
              await queryClient.invalidateQueries({ queryKey: ["cook"] })
            }
            return edited
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
  onEdit,
  onNewVersion,
  onFork,
}: {
  recipe: Recipe
  version: Version
  latest: boolean
  onCook: () => void
  onEdit: () => void
  onNewVersion: () => void
  onFork: () => void
}) {
  const parent =
    version.parent?.recipe === recipe.slug
      ? recipe.versions.find((other) => other.number === version.parent?.number)
      : undefined
  const generic = version.items
    .filter((item) => item.variants > 0)
    .map((item) => itemNames(item).primary)
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
              <DropdownMenuItem onClick={onEdit}>
                <PencilIcon /> Edit this version
              </DropdownMenuItem>
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
        {version.changes.length > 0 && <ChangeList changes={version.changes} />}
        <PortionNutrition perPortion={version.per_portion} compact={!latest} />
        {generic.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Generic values for {generic.join(", ")}; cooks count the products
            that actually went in.
          </p>
        )}

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
