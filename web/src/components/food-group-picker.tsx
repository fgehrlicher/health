import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { groupIcon } from "@/components/food-groups"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { facetsQuery } from "@/lib/queries"
import { updateFood } from "@/server/catalog"
import type { FoodDetail } from "@/lib/api/types"

const NONE = "__none__"

/** Choose a registered product's food group, so it appears in browsing. */
export function FoodGroupPicker({ food }: { food: FoodDetail }) {
  const queryClient = useQueryClient()
  const groups = useQuery(facetsQuery()).data?.groups ?? []
  const save = useMutation({
    mutationFn: (group: string | null) =>
      updateFood({ data: { slug: food.slug, food_group: group } }),
    onSuccess: async (updated) => {
      toast.success(
        updated.food_group_name
          ? `Moved to ${updated.food_group_name}`
          : "Category removed"
      )
      queryClient.setQueryData(["food", food.slug], updated)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["facets"] }),
        queryClient.invalidateQueries({ queryKey: ["foods-infinite"] }),
      ])
    },
    onError: (error) => toast.error(error.message),
  })

  const items = [
    { value: NONE, label: "No category" },
    ...groups.map((group) => ({ value: group.code, label: group.name })),
  ]
  return (
    <Select
      value={food.food_group ?? NONE}
      items={items}
      disabled={save.isPending}
      onValueChange={(value) => save.mutate(value === NONE ? null : value)}
    >
      <SelectTrigger size="sm" aria-label="Category" className="bg-card">
        <SelectValue />
      </SelectTrigger>
      <SelectContent
        alignItemWithTrigger={false}
        align="start"
        className="min-w-72"
      >
        <SelectItem value={NONE}>No category</SelectItem>
        {groups.map((group) => {
          const Icon = groupIcon(group.code)
          return (
            <SelectItem key={group.code} value={group.code}>
              <Icon aria-hidden /> {group.name}
            </SelectItem>
          )
        })}
      </SelectContent>
    </Select>
  )
}
