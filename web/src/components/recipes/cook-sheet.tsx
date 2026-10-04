import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { useDeferredValue, useEffect, useState } from "react"
import { toast } from "sonner"
import { draftFromAmount, toInput } from "@/components/log/meal-sheet"
import { IngredientEditor } from "@/components/recipes/ingredient-editor"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Textarea } from "@/components/ui/textarea"
import { formatNumber, nowLocal } from "@/lib/format"
import { totalOf } from "@/lib/macros"
import { createCook, updateCook } from "@/server/recipes"
import type { ItemDraft } from "@/components/log/meal-sheet"
import type { Cook, Issue, Version } from "@/lib/api/types"

/** What the form starts from: a recipe version, nothing (improvised), or a cook to edit. */
export type CookStart =
  | { kind: "version"; recipe: string; recipeName: string; version: Version }
  | { kind: "improvised" }
  | { kind: "edit"; cook: Cook }

/** Log a cook, or correct one: when, what went in, and how many portions. */
export function CookSheet({
  start,
  onOpenChange,
}: {
  start: CookStart | null
  onOpenChange: (open: boolean) => void
}) {
  const open = start !== null
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState("")
  const [cookedAt, setCookedAt] = useState("")
  const [portions, setPortions] = useState("")
  const [weight, setWeight] = useState("")
  const [note, setNote] = useState("")
  const [items, setItems] = useState<Array<ItemDraft>>([])
  const [issues, setIssues] = useState<Array<Issue>>([])

  useEffect(() => {
    if (!start) return
    setIssues([])
    if (start.kind === "edit") {
      const cook = start.cook
      setName(cook.name)
      setCookedAt(cook.cooked_at.slice(0, 16))
      setPortions(cook.portions)
      setWeight(cook.weight_g ?? "")
      setNote(cook.note ?? "")
      setItems(cook.items.map(draftFromAmount))
    } else {
      setName("")
      setCookedAt(nowLocal())
      setPortions(start.kind === "version" ? start.version.portions : "")
      setWeight("")
      setNote("")
      setItems(
        start.kind === "version" ? start.version.items.map(draftFromAmount) : []
      )
    }
  }, [start])

  const input = toInput(items) as Array<
    ReturnType<typeof toInput>[number] & { food: string }
  >
  const incomplete = items.length > input.length || items.length === 0
  const fields = {
    cooked_at: cookedAt,
    portions: Number(portions) || undefined,
    weight_g: weight ? Number(weight) : null,
    note,
    items: input,
  }
  const source =
    start?.kind === "version"
      ? { recipe: start.recipe, version: start.version.number }
      : { name: name.trim() || undefined }

  // Per-portion preview for a new cook, calculated by the API.
  const deferred = useDeferredValue({
    ...source,
    portions: fields.portions,
    items: input,
  })
  const preview = useQuery({
    queryKey: ["cook-preview", deferred],
    queryFn: () => createCook({ data: { ...deferred, dry_run: true } }),
    enabled:
      start !== null &&
      start.kind !== "edit" &&
      deferred.items.length > 0 &&
      deferred.portions !== undefined &&
      (start.kind === "version" || deferred.name !== undefined),
    staleTime: Infinity,
  })
  const previewCook = preview.data?.ok ? preview.data.value : null

  const save = useMutation({
    mutationFn: () =>
      start?.kind === "edit"
        ? updateCook({
            data: { id: start.cook.id, name: name.trim(), ...fields },
          })
        : createCook({ data: { ...source, ...fields } }),
    onSuccess: async (result) => {
      if (!result.ok) {
        setIssues(result.issues)
        return
      }
      toast.success(start?.kind === "edit" ? "Cook updated" : "Cook logged")
      await Promise.all(
        ["cooks", "cook", "recipe", "recipes", "day"].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] })
        )
      )
      onOpenChange(false)
      if (start?.kind !== "edit") {
        await navigate({
          to: "/cooks/$id",
          params: { id: result.value.id },
        })
      }
    },
    onError: (error) => setIssues([{ field: "", message: error.message }]),
  })

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 sm:max-w-md">
        <SheetHeader>
          <SheetTitle>
            {start?.kind === "edit"
              ? "Edit cook"
              : start?.kind === "version"
                ? `Cook ${start.recipeName} v${start.version.number}`
                : "Log an improvised cook"}
          </SheetTitle>
          <SheetDescription>
            Record what actually went into the pot; changes to the recipe are
            fine and shown afterwards.
          </SheetDescription>
        </SheetHeader>
        <form
          id="cook-form"
          className="flex-1 overflow-y-auto px-4"
          onSubmit={(event) => {
            event.preventDefault()
            setIssues([])
            save.mutate()
          }}
        >
          <FieldGroup>
            {start?.kind !== "version" && (
              <Field>
                <FieldLabel htmlFor="cook-name">Name</FieldLabel>
                <Input
                  id="cook-name"
                  required
                  maxLength={200}
                  placeholder="e.g. Fridge stir fry"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </Field>
            )}
            <Field>
              <FieldLabel htmlFor="cooked-at">Cooked</FieldLabel>
              <Input
                id="cooked-at"
                type="datetime-local"
                required
                value={cookedAt}
                onChange={(event) => setCookedAt(event.target.value)}
              />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field>
                <FieldLabel htmlFor="cook-portions">Portions</FieldLabel>
                <Input
                  id="cook-portions"
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="any"
                  required
                  value={portions}
                  onChange={(event) => setPortions(event.target.value)}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="cook-weight">Weight (g)</FieldLabel>
                <Input
                  id="cook-weight"
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="any"
                  placeholder="Optional"
                  value={weight}
                  onChange={(event) => setWeight(event.target.value)}
                />
              </Field>
            </div>
            <Field>
              <FieldLabel>What went in</FieldLabel>
              <IngredientEditor items={items} onChange={setItems} />
              <FieldDescription>
                Change amounts freely, e.g. the whole can.
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="cook-note">How did it turn out?</FieldLabel>
              <Textarea
                id="cook-note"
                rows={3}
                maxLength={2000}
                placeholder="e.g. too watery, more coconut milk next time"
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </Field>
            {issues.length > 0 && (
              <Alert variant="destructive">
                <AlertDescription>
                  <ul className="list-disc pl-4">
                    {issues.map((issue, index) => (
                      <li key={index}>{issue.message}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}
          </FieldGroup>
        </form>
        <SheetFooter className="border-t">
          {previewCook && (
            <div className="flex items-baseline justify-between text-sm">
              <span className="text-muted-foreground">Per portion</span>
              <span className="tabular-nums">
                <strong>
                  {formatNumber(
                    totalOf(previewCook.per_portion.energy_kcal),
                    0
                  )}
                </strong>{" "}
                kcal ·{" "}
                {formatNumber(totalOf(previewCook.per_portion.protein_g))} g
                protein
              </span>
            </div>
          )}
          <Button
            type="submit"
            form="cook-form"
            disabled={save.isPending || incomplete}
          >
            {incomplete
              ? "Add ingredients with amounts"
              : start?.kind === "edit"
                ? "Save changes"
                : "Log cook"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
