import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { XIcon } from "lucide-react"
import { useDeferredValue, useEffect, useState } from "react"
import { toast } from "sonner"
import { CookPicker } from "@/components/cook-picker"
import { FoodPicker } from "@/components/food-picker"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  capitalize,
  dayLabel,
  formatNumber,
  nowLocal,
  today,
} from "@/lib/format"
import { foodQuery } from "@/lib/queries"
import { MEAL_KINDS } from "@/lib/api/types"
import { createMeal, updateMeal } from "@/server/log"
import type { ItemInput } from "@/server/log"
import type { Issue, Meal, MealKind } from "@/lib/api/types"

/**
 * A food in the form. `unit` is the source unit or a portion name. With
 * `cookId` it is portions of a cook instead, and `food` is empty.
 */
export type ItemDraft = {
  key: string
  food: string
  foodName: string
  sourceId?: number
  cookId?: number
  /** For a cook: when it was cooked, shown under the name. */
  detail?: string
  baseUnit: string
  unit: string
  quantity: string
  estimated: boolean
}

let nextKey = 0
export function newDraft(food: {
  slug: string
  name: string
  unit: string
}): ItemDraft {
  nextKey += 1
  return {
    key: `item-${nextKey}`,
    food: food.slug,
    foodName: food.name,
    baseUnit: food.unit,
    unit: food.unit,
    quantity: "",
    estimated: false,
  }
}

/** One portion of a cook, as a form row. */
export function cookDraft(cook: {
  id: number
  name: string
  cooked_at: string
}): ItemDraft {
  return {
    ...newDraft({ slug: "", name: cook.name, unit: "portion" }),
    cookId: cook.id,
    detail: `Cooked ${dayLabel(cook.cooked_at.slice(0, 10))}`,
    quantity: "1",
  }
}

/** An amount of a catalog source (a meal item, an ingredient) as a form row. */
export function draftFromAmount(item: {
  food: string
  food_name: string
  unit: string
  source_id: number
  amount: string
  estimated: boolean
}): ItemDraft {
  return {
    ...newDraft({ slug: item.food, name: item.food_name, unit: item.unit }),
    sourceId: item.source_id,
    quantity: item.amount,
    estimated: item.estimated,
  }
}

function draftsFromMeal(meal: Meal): Array<ItemDraft> {
  return meal.items.map((item) =>
    item.cook_id !== null && item.cooked_at !== null
      ? {
          ...cookDraft({
            id: item.cook_id,
            name: item.food_name,
            cooked_at: item.cooked_at,
          }),
          quantity: item.amount,
          estimated: item.estimated,
        }
      : draftFromAmount({
          ...item,
          food: item.food ?? "",
          source_id: item.source_id ?? 0,
        })
  )
}

/** API items for drafts with a usable quantity. */
export function toInput(drafts: Array<ItemDraft>): Array<ItemInput> {
  return drafts
    .filter((draft) => Number(draft.quantity) > 0)
    .map((draft) => {
      if (draft.cookId !== undefined) {
        return {
          cook: draft.cookId,
          amount: Number(draft.quantity),
          estimated: draft.estimated,
        }
      }
      const base = {
        food: draft.food,
        source_id: draft.sourceId,
        estimated: draft.estimated,
      }
      return draft.unit === draft.baseUnit
        ? { ...base, amount: Number(draft.quantity) }
        : { ...base, portion: draft.unit, count: Number(draft.quantity) }
    })
}

export function MealSheet({
  date,
  meal,
  open,
  onOpenChange,
  initialFood,
  initialCook,
}: {
  date: string
  /** The meal to edit, or null to log a new one. */
  meal: Meal | null
  open: boolean
  onOpenChange: (open: boolean) => void
  initialFood?: { slug: string; name: string; unit: string }
  /** Start with one portion of this cook. */
  initialCook?: { id: number; name: string; cooked_at: string }
}) {
  const queryClient = useQueryClient()
  const [kind, setKind] = useState<MealKind | null>(null)
  const [eatenAt, setEatenAt] = useState("")
  const [note, setNote] = useState("")
  const [items, setItems] = useState<Array<ItemDraft>>([])
  const [issues, setIssues] = useState<Array<Issue>>([])

  // Reset the form whenever the sheet opens for a meal or a new one.
  useEffect(() => {
    if (!open) return
    setIssues([])
    if (meal) {
      setKind(meal.kind)
      setNote(meal.note ?? "")
      setEatenAt(meal.eaten_at.slice(0, 16))
      setItems(draftsFromMeal(meal))
    } else {
      setKind(null)
      setNote("")
      setEatenAt(date === today() ? nowLocal() : `${date}T12:00`)
      setItems(
        initialFood
          ? [newDraft(initialFood)]
          : initialCook
            ? [cookDraft(initialCook)]
            : []
      )
    }
  }, [open, meal, date, initialFood, initialCook])

  const input = toInput(items)
  const incomplete = items.length > input.length
  const deferredInput = useDeferredValue(input)
  // Preview what would be stored, calculated by the API from the catalog.
  const preview = useQuery({
    queryKey: ["meal-preview", deferredInput],
    queryFn: () =>
      createMeal({ data: { items: deferredInput, dry_run: true } }),
    enabled: open && deferredInput.length > 0,
    staleTime: Infinity,
  })

  const save = useMutation({
    mutationFn: () =>
      meal
        ? updateMeal({
            data: { id: meal.id, kind, note, eaten_at: eatenAt, items: input },
          })
        : createMeal({ data: { kind, note, eaten_at: eatenAt, items: input } }),
    onSuccess: async (result) => {
      if (!result.ok) {
        setIssues(result.issues)
        return
      }
      toast.success(meal ? "Meal updated" : "Meal logged")
      await queryClient.invalidateQueries({ queryKey: ["day"] })
      onOpenChange(false)
    },
    onError: (error) => setIssues([{ field: "", message: error.message }]),
  })

  const previewMeal = preview.data?.ok ? preview.data.meal : null
  const previewIssues =
    preview.data && !preview.data.ok ? preview.data.issues : []
  const shownIssues = issues.length ? issues : previewIssues

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 sm:max-w-md">
        <SheetHeader>
          <SheetTitle>{meal ? "Edit meal" : "Log meal"}</SheetTitle>
          <SheetDescription>
            Nutrition comes from the catalog. A meal without foods is logged as
            unknown.
          </SheetDescription>
        </SheetHeader>

        <form
          id="meal-form"
          className="flex-1 overflow-y-auto px-4"
          onSubmit={(event) => {
            event.preventDefault()
            setIssues([])
            save.mutate()
          }}
        >
          <FieldGroup>
            <Field>
              <FieldLabel>Meal</FieldLabel>
              <ToggleGroup
                variant="outline"
                spacing={0}
                className="w-full"
                value={kind ? [kind] : []}
                onValueChange={(value) =>
                  setKind((value[0] as MealKind | undefined) ?? null)
                }
              >
                {MEAL_KINDS.map((option) => (
                  <ToggleGroupItem
                    key={option}
                    value={option}
                    className="flex-1"
                  >
                    {capitalize(option)}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </Field>

            <Field>
              <FieldLabel htmlFor="eaten-at">Time</FieldLabel>
              <Input
                id="eaten-at"
                type="datetime-local"
                value={eatenAt}
                onChange={(event) => setEatenAt(event.target.value)}
                required
              />
            </Field>

            <Field>
              <FieldLabel htmlFor="meal-note">Note</FieldLabel>
              <Textarea
                id="meal-note"
                placeholder="Raw thoughts, e.g. too salty, felt full for hours"
                maxLength={2000}
                rows={3}
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </Field>

            <Field>
              <FieldLabel>Foods</FieldLabel>
              <div className="flex flex-col gap-2">
                {items.map((item) => (
                  <ItemRow
                    key={item.key}
                    item={item}
                    onChange={(changed) =>
                      setItems((all) =>
                        all.map((other) =>
                          other.key === item.key ? changed : other
                        )
                      )
                    }
                    onRemove={() =>
                      setItems((all) =>
                        all.filter((other) => other.key !== item.key)
                      )
                    }
                  />
                ))}
                <div className="grid grid-cols-2 gap-2">
                  <FoodPicker
                    onPick={(food) =>
                      setItems((all) => [
                        ...all,
                        newDraft({
                          slug: food.slug,
                          name: food.name,
                          unit: food.source?.reference_unit ?? "g",
                        }),
                      ])
                    }
                  />
                  <CookPicker
                    onPick={(cook) =>
                      setItems((all) => [...all, cookDraft(cook)])
                    }
                  />
                </div>
              </div>
            </Field>

            {shownIssues.length > 0 && (
              <Alert variant="destructive">
                <AlertDescription>
                  <ul className="list-disc pl-4">
                    {shownIssues.map((issue, index) => (
                      <li key={index}>{issue.message}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}
          </FieldGroup>
        </form>

        <SheetFooter className="border-t">
          <div className="flex items-baseline justify-between text-sm">
            <span className="text-muted-foreground">
              {input.length === 0
                ? "Unknown meal"
                : previewMeal?.status === "estimated"
                  ? "Estimated"
                  : "Measured"}
            </span>
            <span className="tabular-nums">
              {previewMeal && input.length > 0 ? (
                <>
                  <strong>
                    {formatNumber(
                      Number(previewMeal.totals.energy_kcal.measured) +
                        Number(previewMeal.totals.energy_kcal.estimated),
                      0
                    )}
                  </strong>{" "}
                  kcal ·{" "}
                  {formatNumber(
                    Number(previewMeal.totals.protein_g.measured) +
                      Number(previewMeal.totals.protein_g.estimated)
                  )}{" "}
                  g protein
                </>
              ) : (
                "–"
              )}
            </span>
          </div>
          <Button
            type="submit"
            form="meal-form"
            disabled={save.isPending || incomplete}
          >
            {incomplete
              ? "Enter an amount for every food"
              : meal
                ? "Save changes"
                : "Log meal"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

export function ItemRow({
  item,
  onChange,
  onRemove,
}: {
  item: ItemDraft
  onChange: (item: ItemDraft) => void
  onRemove: () => void
}) {
  // Portions ("Becher", "Portion") come with the food's details.
  const food = useQuery({
    ...foodQuery(item.food),
    enabled: item.cookId === undefined,
  })
  const portions = (food.data?.portions ?? []).filter(
    (portion) => portion.unit === item.baseUnit
  )
  const units = [item.baseUnit, ...portions.map((portion) => portion.name)]

  return (
    <div className="flex flex-col gap-2 rounded-lg border p-3">
      <div className="flex items-start gap-2">
        <span className="flex min-w-0 flex-1 flex-col text-sm font-medium">
          {item.foodName}
          {item.detail && (
            <span className="text-xs font-normal text-muted-foreground">
              {item.detail}
            </span>
          )}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label="Remove"
          onClick={onRemove}
        >
          <XIcon />
        </Button>
      </div>
      <div className="flex items-center gap-2">
        <Input
          type="number"
          inputMode="decimal"
          min="0"
          step="any"
          placeholder={item.unit === item.baseUnit ? "Amount" : "Count"}
          aria-label="Amount"
          className="w-24"
          value={item.quantity}
          onChange={(event) =>
            onChange({ ...item, quantity: event.target.value })
          }
        />
        {item.cookId !== undefined ? (
          <span className="text-sm text-muted-foreground">
            {Number(item.quantity) === 1 ? "portion" : "portions"}
          </span>
        ) : (
          <Select
            value={item.unit}
            onValueChange={(unit) =>
              onChange({
                ...item,
                unit: unit as string,
                // One portion is the usual answer; grams need typing.
                quantity: unit === item.baseUnit ? "" : "1",
              })
            }
          >
            <SelectTrigger className="min-w-24" aria-label="Unit">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {units.map((unit) => {
                const portion = portions.find((option) => option.name === unit)
                return (
                  <SelectItem key={unit} value={unit}>
                    {portion
                      ? `${portion.name} (${formatNumber(portion.quantity)} ${portion.unit})`
                      : unit}
                  </SelectItem>
                )
              })}
            </SelectContent>
          </Select>
        )}
        <label className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
          <Switch
            checked={item.estimated}
            onCheckedChange={(estimated) => onChange({ ...item, estimated })}
          />
          Guessed
        </label>
      </div>
    </div>
  )
}
