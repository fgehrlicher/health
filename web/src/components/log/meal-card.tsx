import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { MoreHorizontalIcon, PencilIcon, Trash2Icon } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
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
import { capitalize, clockTime, formatNumber } from "@/lib/format"
import { deleteMeal } from "@/server/log"
import type { Meal } from "@/lib/api/types"

export function MealCard({ meal, onEdit }: { meal: Meal; onEdit: () => void }) {
  const [confirming, setConfirming] = useState(false)
  const queryClient = useQueryClient()
  const remove = useMutation({
    mutationFn: () => deleteMeal({ data: { id: meal.id } }),
    onSuccess: () => {
      setConfirming(false)
      toast.success("Meal deleted")
      return queryClient.invalidateQueries({ queryKey: ["day"] })
    },
    onError: (error) => toast.error(error.message),
  })
  const kcal =
    Number(meal.totals.energy_kcal.measured) +
    Number(meal.totals.energy_kcal.estimated)

  return (
    <Card size="sm">
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <span className="font-medium tabular-nums">
            {clockTime(meal.eaten_at)}
          </span>
          {meal.kind && (
            <span className="text-muted-foreground">
              {capitalize(meal.kind)}
            </span>
          )}
          {meal.status !== "measured" && (
            <Badge
              variant={meal.status === "unknown" ? "outline" : "secondary"}
            >
              {meal.status}
            </Badge>
          )}
          <span className="ml-auto text-sm text-muted-foreground tabular-nums">
            {meal.status === "unknown" ? "–" : `${formatNumber(kcal, 0)} kcal`}
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Meal actions"
                />
              }
            >
              <MoreHorizontalIcon />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={onEdit}>
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

        {meal.items.length === 0 ? (
          <button
            type="button"
            onClick={onEdit}
            className="text-left text-sm text-muted-foreground hover:text-foreground"
          >
            No foods yet. Add what it was to count it.
          </button>
        ) : (
          <ul className="flex flex-col gap-1.5 text-sm">
            {meal.items.map((item) => (
              <li key={item.id} className="flex items-baseline gap-2">
                <Link
                  to="/foods/$slug"
                  params={{ slug: item.food }}
                  className="min-w-0 truncate hover:underline"
                >
                  {item.food_name}
                </Link>
                <span className="shrink-0 text-muted-foreground tabular-nums">
                  {item.estimated ? "~" : ""}
                  {formatNumber(item.amount)} {item.unit}
                </span>
                <span className="ml-auto shrink-0 text-muted-foreground tabular-nums">
                  {formatNumber(item.nutrition.energy_kcal, 0)} kcal
                </span>
              </li>
            ))}
          </ul>
        )}
        {meal.note && (
          <p className="border-l-2 border-primary/40 pl-3 text-sm whitespace-pre-wrap text-muted-foreground">
            {meal.note}
          </p>
        )}
      </CardContent>

      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this meal?</DialogTitle>
            <DialogDescription>
              The meal at {clockTime(meal.eaten_at)} and its {meal.items.length}{" "}
              {meal.items.length === 1 ? "food" : "foods"} will be removed.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />}>
              Cancel
            </DialogClose>
            <Button
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
