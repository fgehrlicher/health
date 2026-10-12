import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useId, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { setDailyKcalLimit } from "@/server/log"

/**
 * The daily kcal limit. Days at or below it count as within it; days above it
 * are marked. The parent gives it a key from the saved limit, so the field
 * starts again whenever the saved value changes.
 */
export function DailyLimitForm({ limit }: { limit: number }) {
  const id = useId()
  const queryClient = useQueryClient()
  const [value, setValue] = useState(String(limit))
  const parsed = Number(value)
  const valid = Number.isInteger(parsed) && parsed > 0 && parsed <= 10000
  const save = useMutation({
    mutationFn: (next: number) => setDailyKcalLimit({ data: { limit: next } }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["calendar"] })
      toast.success("Daily limit saved")
    },
    onError: (error) => toast.error(error.message),
  })

  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (valid) save.mutate(parsed)
      }}
    >
      <Label htmlFor={id}>Daily limit, kcal</Label>
      <div className="flex gap-2">
        <Input
          id={id}
          type="number"
          inputMode="numeric"
          min={1}
          max={10000}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          className="w-36"
        />
        <Button
          type="submit"
          variant="outline"
          disabled={!valid || parsed === limit || save.isPending}
        >
          Save
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Days at or below the limit are green, days above it are red.
      </p>
    </form>
  )
}
