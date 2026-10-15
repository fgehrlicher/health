import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useId, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { setGoals } from "@/server/log"

const MAX_KCAL = 10000

function isKcal(value: number): boolean {
  return Number.isInteger(value) && value >= 0 && value <= MAX_KCAL
}

/**
 * The daily kcal limit, and the tolerance above it. The parent gives the form a
 * key from the saved values, so the fields start again when they change.
 */
export function GoalsForm({
  limit,
  tolerance,
}: {
  limit: number
  tolerance: number
}) {
  const limitId = useId()
  const toleranceId = useId()
  const queryClient = useQueryClient()
  const [limitText, setLimitText] = useState(String(limit))
  const [toleranceText, setToleranceText] = useState(String(tolerance))
  const parsedLimit = Number(limitText)
  const parsedTolerance = Number(toleranceText)
  const valid =
    isKcal(parsedLimit) && parsedLimit > 0 && isKcal(parsedTolerance)
  const unchanged = parsedLimit === limit && parsedTolerance === tolerance
  const save = useMutation({
    mutationFn: () =>
      setGoals({
        data: { limit: parsedLimit, tolerance: parsedTolerance },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["calendar"] })
      toast.success("Goals saved")
    },
    onError: (error) => toast.error(error.message),
  })

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        if (valid) save.mutate()
      }}
    >
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={limitId}>Daily limit, kcal</Label>
          <Input
            id={limitId}
            type="number"
            inputMode="numeric"
            min={1}
            max={MAX_KCAL}
            value={limitText}
            onChange={(event) => setLimitText(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={toleranceId}>Tolerance above, kcal</Label>
          <Input
            id={toleranceId}
            type="number"
            inputMode="numeric"
            min={0}
            max={MAX_KCAL}
            value={toleranceText}
            onChange={(event) => setToleranceText(event.target.value)}
          />
        </div>
      </div>
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          Within the limit is green, up to the tolerance above it yellow, beyond
          that red.
        </p>
        <Button
          type="submit"
          variant="outline"
          disabled={!valid || unchanged || save.isPending}
        >
          Save
        </Button>
      </div>
    </form>
  )
}
