import { useMutation } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { IngredientEditor } from "@/components/recipes/ingredient-editor"
import { TagInput } from "@/components/recipes/tag-input"
import { draftFromAmount, toInput } from "@/components/log/meal-sheet"
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
import type { ItemDraft } from "@/components/log/meal-sheet"
import type { Amount, Issue } from "@/lib/api/types"
import type { ItemInput } from "@/server/log"
import type { Result } from "@/server/recipes"

export type RecipeFormValues = {
  name: string
  note: string
  tags: Array<string>
  portions: number
  instructions: string
  items: Array<ItemInput & { food: string }>
  /** Whether ingredients or portions differ from the start values. */
  changed: boolean
}

/**
 * A recipe or version form: name, note, portions, ingredients, and steps,
 * started from an existing version or cook. The caller decides what saving does.
 */
export function RecipeFormSheet({
  open,
  onOpenChange,
  title,
  description,
  submitLabel,
  showName = false,
  noteLabel,
  notePlaceholder,
  start,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  submitLabel: string
  showName?: boolean
  noteLabel: string
  notePlaceholder: string
  start: {
    name?: string
    tags?: Array<string>
    portions?: string
    instructions?: string | null
    items?: Array<Amount>
  }
  onSubmit: (values: RecipeFormValues) => Promise<Result<unknown>>
}) {
  const [name, setName] = useState("")
  const [tags, setTags] = useState<Array<string>>([])
  const [note, setNote] = useState("")
  const [portions, setPortions] = useState("")
  const [instructions, setInstructions] = useState("")
  const [items, setItems] = useState<Array<ItemDraft>>([])
  const [changed, setChanged] = useState(false)
  const [issues, setIssues] = useState<Array<Issue>>([])

  useEffect(() => {
    if (!open) return
    setName(start.name ?? "")
    setTags(start.tags ?? [])
    setNote("")
    setPortions(start.portions ?? "")
    setInstructions(start.instructions ?? "")
    setItems((start.items ?? []).map(draftFromAmount))
    setChanged(false)
    setIssues([])
  }, [open, start])

  const input = toInput(items) as RecipeFormValues["items"]
  const incomplete = items.length > input.length || items.length === 0
  const save = useMutation({
    mutationFn: () =>
      onSubmit({
        name: name.trim(),
        tags,
        note,
        portions: Number(portions),
        instructions,
        items: input,
        changed,
      }),
    onSuccess: (result) => {
      if (result.ok) onOpenChange(false)
      else setIssues(result.issues)
    },
    onError: (error) => setIssues([{ field: "", message: error.message }]),
  })

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 sm:max-w-md">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription>{description}</SheetDescription>
        </SheetHeader>
        <form
          id="recipe-form"
          className="flex-1 overflow-y-auto px-4"
          onSubmit={(event) => {
            event.preventDefault()
            setIssues([])
            save.mutate()
          }}
        >
          <FieldGroup>
            {showName && (
              <Field>
                <FieldLabel htmlFor="recipe-name">Name</FieldLabel>
                <Input
                  id="recipe-name"
                  required
                  maxLength={200}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </Field>
            )}
            {showName && (
              <Field>
                <FieldLabel>Tags</FieldLabel>
                <TagInput tags={tags} onChange={setTags} />
              </Field>
            )}
            <Field>
              <FieldLabel htmlFor="recipe-note">{noteLabel}</FieldLabel>
              <Textarea
                id="recipe-note"
                rows={2}
                maxLength={2000}
                placeholder={notePlaceholder}
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="recipe-portions">Portions</FieldLabel>
              <Input
                id="recipe-portions"
                type="number"
                inputMode="decimal"
                min="0"
                step="any"
                required
                className="w-24"
                value={portions}
                onChange={(event) => {
                  setPortions(event.target.value)
                  setChanged(true)
                }}
              />
              <FieldDescription>
                Equal parts the pot is split into.
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel>Ingredients</FieldLabel>
              <IngredientEditor
                items={items}
                onChange={(next) => {
                  setItems(next)
                  setChanged(true)
                }}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="recipe-steps">Steps</FieldLabel>
              <Textarea
                id="recipe-steps"
                rows={5}
                maxLength={20000}
                placeholder="Free text, as detailed as you like"
                value={instructions}
                onChange={(event) => setInstructions(event.target.value)}
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
          <Button
            type="submit"
            form="recipe-form"
            disabled={save.isPending || incomplete}
          >
            {incomplete ? "Add ingredients with amounts" : submitLabel}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
