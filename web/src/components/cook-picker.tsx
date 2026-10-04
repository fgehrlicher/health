import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { CookingPotIcon } from "lucide-react"
import { useDeferredValue, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Spinner } from "@/components/ui/spinner"
import { dayLabel, formatNumber } from "@/lib/format"
import { totalOf } from "@/lib/macros"
import { cooksQuery } from "@/lib/queries"
import type { CookSummary } from "@/lib/api/types"

/** Pick a cook from the cooking log, newest first, e.g. Monday's curry. */
export function CookPicker({
  onPick,
}: {
  onPick: (cook: CookSummary) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const deferred = useDeferredValue(query.trim())
  const cooks = useQuery({
    ...cooksQuery(deferred ? { q: deferred } : {}),
    enabled: open,
    placeholderData: keepPreviousData,
  })

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={<Button variant="outline" className="w-full" />}>
        <CookingPotIcon /> Cooked dish
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="end">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search the cooking log"
            value={query}
            onValueChange={setQuery}
          />
          <CommandList>
            {!cooks.data ? (
              <div className="flex justify-center py-6">
                <Spinner />
              </div>
            ) : (
              <>
                <CommandEmpty>Nothing cooked yet.</CommandEmpty>
                <CommandGroup>
                  {cooks.data.map((cook) => (
                    <CommandItem
                      key={cook.id}
                      value={String(cook.id)}
                      onSelect={() => {
                        onPick(cook)
                        setOpen(false)
                        setQuery("")
                      }}
                    >
                      <div className="flex min-w-0 flex-col">
                        <span className="truncate">{cook.name}</span>
                        <span className="truncate text-xs text-muted-foreground">
                          {dayLabel(cook.cooked_at.slice(0, 10))} ·{" "}
                          {formatNumber(cook.portions_left)} of{" "}
                          {formatNumber(cook.portions)} left
                        </span>
                      </div>
                      <span className="ml-auto shrink-0 text-xs text-muted-foreground tabular-nums">
                        {formatNumber(totalOf(cook.per_portion.energy_kcal), 0)}{" "}
                        kcal/portion
                      </span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
