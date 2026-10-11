import { Badge } from "@/components/ui/badge"

// Short names for the catalog's sources: where a food's numbers come from.
const SHORT_NAMES: Record<string, string> = {
  "BLS 4.0": "BLS 4",
  "USDA FoodData Central": "USDA",
  "Product label": "Label",
}

/** A small label naming the catalog source a food comes from. */
export function SourceBadge({ name }: { name: string }) {
  return (
    <Badge variant="outline" className="text-[0.65rem]">
      {SHORT_NAMES[name] ?? name}
    </Badge>
  )
}
