import {
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router"
import {
  ArrowLeftIcon,
  GitBranchIcon,
  MoreHorizontalIcon,
  PencilIcon,
  Trash2Icon,
  UtensilsIcon,
} from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"
import { MealSheet } from "@/components/log/meal-sheet"
import { ChangeList } from "@/components/recipes/change-list"
import { CookSheet } from "@/components/recipes/cook-sheet"
import { IngredientList } from "@/components/recipes/ingredient-list"
import { PortionNutrition } from "@/components/recipes/portion-nutrition"
import { RecipeFormSheet } from "@/components/recipes/recipe-form-sheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { clockTime, dayLabel, formatNumber, today } from "@/lib/format"
import { cookQuery } from "@/lib/queries"
import { addVersion, createRecipe, deleteCook } from "@/server/recipes"
import type { CookStart } from "@/components/recipes/cook-sheet"

export const Route = createFileRoute("/cooks/$id")({
  params: {
    parse: ({ id }) => ({ id: Number(id) }),
    stringify: ({ id }) => ({ id: String(id) }),
  },
  loader: ({ context, params }) =>
    context.queryClient.ensureQueryData(cookQuery(params.id)),
  head: ({ loaderData }) => ({
    meta: [{ title: loaderData ? `${loaderData.name} · Health` : "Health" }],
  }),
  component: CookPage,
})

function CookPage() {
  const { id } = Route.useParams()
  const { data: cook } = useSuspenseQuery(cookQuery(id))
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [eating, setEating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState<CookStart | null>(null)
  const [confirming, setConfirming] = useState(false)
  const eaten = Number(cook.portions_eaten)
  const initialCook = useMemo(
    () => ({ id: cook.id, name: cook.name, cooked_at: cook.cooked_at }),
    [cook.id, cook.name, cook.cooked_at]
  )
  const start = useMemo(
    () => ({
      name: cook.name,
      portions: cook.portions,
      items: cook.items,
    }),
    [cook]
  )
  const remove = useMutation({
    mutationFn: () => deleteCook({ data: { id: cook.id } }),
    onSuccess: async () => {
      toast.success("Cook deleted")
      await queryClient.invalidateQueries({ queryKey: ["cooks"] })
      await queryClient.invalidateQueries({ queryKey: ["recipe"] })
      await navigate({ to: "/recipes" })
    },
    onError: (error) => toast.error(error.message),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <Button
          variant="ghost"
          size="sm"
          className="self-start"
          nativeButton={false}
          render={
            cook.recipe ? (
              <Link to="/recipes/$slug" params={{ slug: cook.recipe.slug }} />
            ) : (
              <Link to="/recipes" />
            )
          }
        >
          <ArrowLeftIcon /> {cook.recipe ? cook.recipe.name : "Recipes"}
        </Button>
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-64 flex-1">
            <h1 className="font-heading text-2xl font-semibold sm:text-3xl">
              {cook.name}
            </h1>
            <p className="text-sm text-muted-foreground">
              Cooked {dayLabel(cook.cooked_at.slice(0, 10))},{" "}
              {clockTime(cook.cooked_at)}
              {cook.version !== null
                ? ` from v${cook.version}`
                : ", improvised"}
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge variant="secondary">
                {formatNumber(cook.portions_left)} of{" "}
                {formatNumber(cook.portions)} portions left
              </Badge>
              {cook.weight_g && (
                <Badge variant="outline">
                  {formatNumber(cook.weight_g, 0)} g cooked
                </Badge>
              )}
              {cook.status === "estimated" && (
                <Badge variant="outline">estimated amounts</Badge>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setSaving(true)}>
              <GitBranchIcon />
              {cook.recipe ? "Save as new version" : "Save as recipe"}
            </Button>
            <Button onClick={() => setEating(true)}>
              <UtensilsIcon /> Eat a portion
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Cook actions"
                  />
                }
              >
                <MoreHorizontalIcon />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  onClick={() => setEditing({ kind: "edit", cook })}
                >
                  <PencilIcon /> Edit
                </DropdownMenuItem>
                <DropdownMenuItem
                  variant="destructive"
                  onClick={() => setConfirming(true)}
                >
                  <Trash2Icon /> Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>

      {cook.note && (
        <p className="border-l-2 border-primary/40 pl-3 whitespace-pre-wrap">
          {cook.note}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>One portion</CardTitle>
          </CardHeader>
          <CardContent>
            <PortionNutrition perPortion={cook.per_portion} />
          </CardContent>
        </Card>
        {cook.version !== null && (
          <Card>
            <CardHeader>
              <CardTitle>Compared with v{cook.version}</CardTitle>
            </CardHeader>
            <CardContent>
              {cook.changes.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Cooked exactly as written.
                </p>
              ) : (
                <ChangeList changes={cook.changes} />
              )}
            </CardContent>
          </Card>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>What went in</CardTitle>
        </CardHeader>
        <CardContent>
          <IngredientList items={cook.items} />
        </CardContent>
      </Card>

      <MealSheet
        date={today()}
        meal={null}
        open={eating}
        onOpenChange={(open) => {
          setEating(open)
          if (!open) void queryClient.invalidateQueries({ queryKey: ["cook"] })
        }}
        initialCook={initialCook}
      />
      <CookSheet
        start={editing}
        onOpenChange={(open) => !open && setEditing(null)}
      />
      <RecipeFormSheet
        open={saving}
        onOpenChange={setSaving}
        title={cook.recipe ? "Save as new version" : "Save as recipe"}
        description={
          cook.recipe
            ? `What went into this cook becomes the next version of ${cook.recipe.name}.`
            : "What went into this cook becomes version 1 of a new recipe."
        }
        submitLabel={cook.recipe ? "Save version" : "Create recipe"}
        showName={!cook.recipe}
        noteLabel={cook.recipe ? "What changed and why?" : "About"}
        notePlaceholder={
          cook.recipe ? "e.g. the whole can works better" : "Optional"
        }
        start={start}
        onSubmit={async (values) => {
          // Unchanged ingredients come from the cook itself.
          const items = values.changed ? values.items : undefined
          const portions = values.changed ? values.portions : undefined
          if (cook.recipe) {
            const result = await addVersion({
              data: {
                slug: cook.recipe.slug,
                note: values.note,
                items,
                portions,
                from_cook: cook.id,
                ...(values.instructions
                  ? { instructions: values.instructions }
                  : {}),
              },
            })
            if (result.ok) {
              toast.success(`Saved as v${result.value.number}`)
              await queryClient.invalidateQueries({ queryKey: ["recipe"] })
              await navigate({
                to: "/recipes/$slug",
                params: { slug: cook.recipe.slug },
              })
            }
            return result
          }
          const result = await createRecipe({
            data: {
              name: values.name,
              note: values.note,
              tags: values.tags,
              items,
              portions,
              instructions: values.instructions,
              from_cook: cook.id,
            },
          })
          if (result.ok) {
            toast.success("Recipe created")
            await queryClient.invalidateQueries()
            await navigate({
              to: "/recipes/$slug",
              params: { slug: result.value.slug },
            })
          }
          return result
        }}
      />
      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this cook?</DialogTitle>
            <DialogDescription>
              {eaten > 0
                ? `${formatNumber(eaten)} portions of it are in the log. Remove those meals first.`
                : "It disappears from the cooking log."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />}>
              Cancel
            </DialogClose>
            <Button
              variant="destructive"
              disabled={eaten > 0 || remove.isPending}
              onClick={() => remove.mutate()}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
