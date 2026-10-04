import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { XIcon } from "lucide-react"
import { toast } from "sonner"
import { FoodPicker } from "@/components/food-picker"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { updateFood } from "@/server/catalog"
import type { FoodDetail } from "@/lib/api/types"

/**
 * Link a product to the generic food it is a kind of, e.g. a brand's soy drink
 * to "Soya drink unsweetened", so recipes can name the generic food.
 */
export function VariantOfPicker({ food }: { food: FoodDetail }) {
  const queryClient = useQueryClient()
  const save = useMutation({
    mutationFn: (generic: string | null) =>
      updateFood({ data: { slug: food.slug, variant_of: generic } }),
    onSuccess: async (updated) => {
      toast.success(
        updated.variant_of
          ? `Now a kind of ${updated.variant_of.name}`
          : "No longer linked to a generic food"
      )
      queryClient.setQueryData(["food", food.slug], updated)
      await queryClient.invalidateQueries({ queryKey: ["food"] })
    },
    onError: (error) => toast.error(error.message),
  })

  return (
    <div className="flex flex-wrap items-center gap-1.5 text-sm">
      <span className="text-muted-foreground">Kind of</span>
      {food.variant_of ? (
        <>
          <Badge
            variant="secondary"
            render={
              <Link to="/foods/$slug" params={{ slug: food.variant_of.slug }} />
            }
          >
            {food.variant_of.name}
          </Badge>
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label="Remove the generic food"
            disabled={save.isPending}
            onClick={() => save.mutate(null)}
          >
            <XIcon />
          </Button>
        </>
      ) : (
        <FoodPicker
          kind="generic"
          size="sm"
          label="Choose generic food"
          onPick={(generic) => save.mutate(generic.slug)}
        />
      )}
    </div>
  )
}
