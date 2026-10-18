import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Trash2Icon } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"
import { FoodPicker } from "@/components/food-picker"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { foodNames } from "@/lib/names"
import { deleteFood } from "@/server/catalog"
import type { FoodDeletion, FoodDetail } from "@/lib/api/types"

type Replacement = { slug: string; name: string }

function counted(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

/** What uses a product, e.g. "2 meals and 1 recipe". */
export function usesPhrase(uses: FoodDeletion["uses"]): string {
  const parts: Array<string> = []
  if (uses.meals > 0) parts.push(counted(uses.meals, "meal", "meals"))
  if (uses.recipes > 0) parts.push(counted(uses.recipes, "recipe", "recipes"))
  if (uses.cooks > 0) parts.push(counted(uses.cooks, "cook", "cooks"))
  if (parts.length < 2) return parts.join("")
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`
}

/**
 * Delete a registered product. One that is in use needs a replacement first:
 * every meal, recipe and cook that used it gets the chosen food, with the same
 * amount. Its generic food ("Kind of") is suggested.
 */
export function DeleteFood({ food }: { food: FoodDetail }) {
  const [open, setOpen] = useState(false)
  const [replacement, setReplacement] = useState<Replacement | null>(
    food.variant_of
      ? { slug: food.variant_of.slug, name: food.variant_of.name }
      : null
  )
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const name = foodNames(food).primary

  // Dry runs: what uses it, then whether the chosen replacement can take over.
  const uses = useQuery({
    queryKey: ["food-uses", food.slug],
    queryFn: () => deleteFood({ data: { slug: food.slug, dry_run: true } }),
    enabled: open,
    staleTime: 0,
  })
  const deletion = uses.data?.ok ? uses.data.deletion : null
  const used = deletion?.blocked ?? false
  const fit = useQuery({
    queryKey: ["food-replacement", food.slug, replacement?.slug],
    queryFn: () =>
      deleteFood({
        data: {
          slug: food.slug,
          replace_with: replacement?.slug,
          dry_run: true,
        },
      }),
    enabled: open && used && replacement !== null,
    staleTime: 0,
  })
  const issues = [
    ...(uses.data && !uses.data.ok ? uses.data.issues : []),
    ...(fit.data && !fit.data.ok ? fit.data.issues : []),
  ]
  const ready =
    deletion !== null &&
    issues.length === 0 &&
    (!used || (replacement !== null && fit.data?.ok === true))

  const remove = useMutation({
    mutationFn: () =>
      deleteFood({
        data: {
          slug: food.slug,
          replace_with: used ? replacement?.slug : undefined,
        },
      }),
    onSuccess: async (result) => {
      if (!result.ok) {
        toast.error(result.issues.map((issue) => issue.message).join("; "))
        return
      }
      toast.success(
        used && replacement
          ? `${name} deleted. ${usesPhrase(result.deletion.uses)} now use ${replacement.name}.`
          : `${name} deleted.`
      )
      setOpen(false)
      await navigate({ to: "/foods" })
      // The page is gone; refresh what showed it (lists, meals, recipes, cooks).
      queryClient.removeQueries({ queryKey: ["food", food.slug] })
      await queryClient.invalidateQueries()
    },
    onError: (error) => toast.error(error.message),
  })

  let description = "Checking where it is used…"
  if (deletion) {
    description = used
      ? `It is used in ${usesPhrase(deletion.uses)}. Pick a food to take its place there, with the same amounts; then the product is deleted.`
      : "Nothing uses it. It will be removed from the catalog."
  }

  return (
    <>
      <Button
        variant="outline"
        className="self-start text-destructive"
        onClick={() => setOpen(true)}
      >
        <Trash2Icon /> Delete product
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {name}?</DialogTitle>
            <DialogDescription>{description}</DialogDescription>
          </DialogHeader>
          {used && (
            <div className="flex flex-col gap-2">
              {replacement && (
                <div className="flex flex-col rounded-lg border p-3 text-sm">
                  <span className="text-xs text-muted-foreground">
                    Takes its place
                  </span>
                  <span className="font-medium">{replacement.name}</span>
                </div>
              )}
              <FoodPicker
                label={replacement ? "Choose another food" : "Choose a food"}
                onPick={(picked) =>
                  setReplacement({
                    slug: picked.slug,
                    name: foodNames(picked).primary,
                  })
                }
              />
            </div>
          )}
          {issues.length > 0 && (
            <Alert variant="destructive">
              <AlertDescription>
                {issues.map((issue) => issue.message).join("; ")}
              </AlertDescription>
            </Alert>
          )}
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />}>
              Cancel
            </DialogClose>
            <Button
              variant="destructive"
              disabled={!ready || remove.isPending}
              onClick={() => remove.mutate()}
            >
              {used ? "Replace and delete" : "Delete product"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
