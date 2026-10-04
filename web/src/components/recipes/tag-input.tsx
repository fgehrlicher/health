import { useQuery } from "@tanstack/react-query"
import { XIcon } from "lucide-react"
import { useId, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { tagsQuery } from "@/lib/queries"
import { cn } from "@/lib/utils"

/** The API's spelling: lowercase and single-spaced. */
export function cleanTag(tag: string): string {
  return tag.trim().replace(/\s+/g, " ").toLowerCase()
}

/**
 * Edit a recipe's tags: chips to remove, and a field that suggests existing
 * tags so "ice cream" is not also typed as "icecream". Enter or comma adds.
 */
export function TagInput({
  tags,
  onChange,
  disabled = false,
  className,
}: {
  tags: Array<string>
  onChange: (tags: Array<string>) => void
  disabled?: boolean
  className?: string
}) {
  const [text, setText] = useState("")
  const listId = useId()
  const known = useQuery(tagsQuery()).data ?? []
  const suggestions = known
    .map((entry) => entry.tag)
    .filter((tag) => !tags.includes(tag))

  const add = (value: string) => {
    const tag = cleanTag(value)
    setText("")
    if (tag && !tags.includes(tag) && tags.length < 20) onChange([...tags, tag])
  }

  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      {tags.map((tag) => (
        <Badge key={tag} variant="secondary" className="gap-1 pr-1">
          {tag}
          <button
            type="button"
            aria-label={`Remove tag ${tag}`}
            disabled={disabled}
            className="rounded-sm opacity-60 hover:opacity-100"
            onClick={() => onChange(tags.filter((other) => other !== tag))}
          >
            <XIcon className="size-3" />
          </button>
        </Badge>
      ))}
      <Input
        aria-label="Add tag"
        placeholder="Add tag"
        list={listId}
        maxLength={40}
        disabled={disabled}
        className="h-7 w-40 text-sm"
        value={text}
        onChange={(event) => {
          const value = event.target.value
          const native = event.nativeEvent
          // Picking a suggestion adds it directly; typing never does, so "ice"
          // is not added on the way to "ice cream".
          const picked =
            !(native instanceof InputEvent) ||
            native.inputType === "insertReplacementText"
          if (picked && suggestions.includes(value)) add(value)
          else setText(value)
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === ",") {
            event.preventDefault()
            add(text)
          } else if (event.key === "Backspace" && !text && tags.length) {
            onChange(tags.slice(0, -1))
          }
        }}
        onBlur={() => text && add(text)}
      />
      <datalist id={listId}>
        {suggestions.map((tag) => (
          <option key={tag} value={tag} />
        ))}
      </datalist>
    </div>
  )
}
