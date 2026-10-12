import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useId } from "react"
import { toast } from "sonner"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { setDayIncomplete } from "@/server/log"

/** Marks a day incomplete: it stays visible, but the stats leave it out. */
export function IncompleteSwitch({
  date,
  incomplete,
}: {
  date: string
  incomplete: boolean
}) {
  const id = useId()
  const queryClient = useQueryClient()
  const mark = useMutation({
    mutationFn: (next: boolean) =>
      setDayIncomplete({ data: { date, incomplete: next } }),
    onSuccess: async (_result, next) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["day"] }),
        queryClient.invalidateQueries({ queryKey: ["calendar"] }),
      ])
      toast.success(
        next ? "Left out of your stats" : "Counts in your stats again"
      )
    },
    onError: (error) => toast.error(error.message),
  })

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
      <div className="flex min-w-0 flex-col gap-0.5">
        <Label htmlFor={id}>Incomplete day</Label>
        <span className="text-sm text-muted-foreground">
          Some meals are missing. The day stays visible but is left out of your
          stats.
        </span>
      </div>
      <Switch
        id={id}
        checked={incomplete}
        disabled={mark.isPending}
        onCheckedChange={(next) => mark.mutate(next)}
      />
    </div>
  )
}
