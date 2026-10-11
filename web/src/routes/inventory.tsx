import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { CookRow } from "@/components/recipes/cook-row"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import { cooksQuery } from "@/lib/queries"

// Cooks with portions still to eat: what is left over from batch cooking.
const inventory = { left: true, limit: 200 } as const

export const Route = createFileRoute("/inventory")({
  loader: ({ context }) =>
    context.queryClient.ensureQueryData(cooksQuery(inventory)),
  head: () => ({ meta: [{ title: "Inventory · Health" }] }),
  component: InventoryPage,
})

function InventoryPage() {
  const { data: cooks } = useSuspenseQuery(cooksQuery(inventory))

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-heading text-2xl font-semibold sm:text-3xl">
          Inventory
        </h1>
        <p className="text-sm text-muted-foreground">
          Cooked dishes you can still eat, newest first.
        </p>
      </div>
      {cooks.length === 0 ? (
        <Empty>
          <EmptyHeader>
            <EmptyTitle>Nothing left over</EmptyTitle>
            <EmptyDescription>
              Cook a recipe in batches and the portions you have not eaten will
              show here.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <div className="flex flex-col gap-2">
          {cooks.map((cook) => (
            <CookRow key={cook.id} cook={cook} />
          ))}
        </div>
      )}
    </div>
  )
}
