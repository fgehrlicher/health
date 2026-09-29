import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { PlusIcon } from "lucide-react"
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
import { formatNumber } from "@/lib/format"
import { foodsQuery } from "@/lib/queries"
import type { FoodSummary } from "@/lib/api/types"

/** Search the catalog and pick a food; ranking comes from the API. */
export function FoodPicker({
  onPick,
}: {
  onPick: (food: FoodSummary) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const deferred = useDeferredValue(query.trim())
  const results = useQuery({
    ...foodsQuery({ q: deferred, limit: 12 }),
    enabled: open && deferred.length >= 2,
    placeholderData: keepPreviousData,
  })

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={<Button variant="outline" className="w-full" />}>
        <PlusIcon /> Add food
      </PopoverTrigger>
      <PopoverContent className="w-(--anchor-width) min-w-72 p-0" align="start">
        {/* The API ranks results, so cmdk must not filter them again. */}
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search foods, e.g. quark, Haferflocken"
            value={query}
            onValueChange={setQuery}
          />
          <CommandList>
            {deferred.length < 2 ? (
              <CommandEmpty>Type at least two letters.</CommandEmpty>
            ) : results.isFetching && !results.data ? (
              <div className="flex justify-center py-6">
                <Spinner />
              </div>
            ) : (
              <>
                <CommandEmpty>No matching food.</CommandEmpty>
                <CommandGroup>
                  {results.data?.items.map((food) => (
                    <CommandItem
                      key={food.slug}
                      value={food.slug}
                      onSelect={() => {
                        onPick(food)
                        setOpen(false)
                        setQuery("")
                      }}
                    >
                      <div className="flex min-w-0 flex-col">
                        <span className="truncate">{food.name}</span>
                        <span className="truncate text-xs text-muted-foreground">
                          {food.brand ??
                            food.aliases.at(0) ??
                            food.source?.source_name}
                        </span>
                      </div>
                      <span className="ml-auto shrink-0 text-xs text-muted-foreground tabular-nums">
                        {formatNumber(food.source?.energy_kcal, 0)} kcal/
                        {formatNumber(food.source?.reference_quantity, 0)}
                        {food.source?.reference_unit}
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
