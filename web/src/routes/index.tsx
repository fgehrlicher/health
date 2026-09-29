import { useSuspenseQuery } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { ChevronLeftIcon, ChevronRightIcon, PlusIcon } from "lucide-react"
import { useState } from "react"
import { z } from "zod"
import { DayTotals } from "@/components/log/day-totals"
import { MealCard } from "@/components/log/meal-card"
import { MealSheet } from "@/components/log/meal-sheet"
import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import { addDays, dayLabel, today } from "@/lib/format"
import { dayQuery } from "@/lib/queries"
import type { Meal } from "@/lib/api/types"

export const Route = createFileRoute("/")({
  validateSearch: z.object({ date: z.iso.date().optional() }),
  loaderDeps: ({ search }) => ({ date: search.date ?? today() }),
  loader: ({ context, deps }) =>
    context.queryClient.ensureQueryData(dayQuery(deps.date)),
  component: TodayPage,
})

function TodayPage() {
  const { date } = Route.useLoaderDeps()
  const { data: day } = useSuspenseQuery(dayQuery(date))
  // null: closed; "new": logging a meal; otherwise the meal being edited.
  const [editing, setEditing] = useState<Meal | "new" | null>(null)
  const isToday = date === today()

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Previous day"
          nativeButton={false}
          render={<Link to="/" search={{ date: addDays(date, -1) }} />}
        >
          <ChevronLeftIcon />
        </Button>
        <h1 className="min-w-0 flex-1 text-center font-heading text-xl font-semibold sm:flex-none">
          {dayLabel(date)}
        </h1>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Next day"
          disabled={isToday}
          nativeButton={false}
          render={<Link to="/" search={{ date: addDays(date, 1) }} />}
        >
          <ChevronRightIcon />
        </Button>
        {!isToday && (
          <Button
            variant="outline"
            size="sm"
            nativeButton={false}
            render={<Link to="/" search={{}} />}
          >
            Today
          </Button>
        )}
        <Button
          className="ml-auto hidden sm:inline-flex"
          onClick={() => setEditing("new")}
        >
          <PlusIcon /> Log meal
        </Button>
      </div>

      <DayTotals day={day} />

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-muted-foreground">Meals</h2>
        {day.meals.length === 0 ? (
          <Empty className="border border-dashed">
            <EmptyHeader>
              <EmptyTitle>
                Nothing logged {isToday ? "yet" : "this day"}
              </EmptyTitle>
              <EmptyDescription>
                Log a meal from catalog foods, or log it as unknown and fill it
                in later.
              </EmptyDescription>
            </EmptyHeader>
            <Button onClick={() => setEditing("new")}>
              <PlusIcon /> Log meal
            </Button>
          </Empty>
        ) : (
          day.meals.map((meal) => (
            <MealCard
              key={meal.id}
              meal={meal}
              onEdit={() => setEditing(meal)}
            />
          ))
        )}
      </section>

      {/* Thumb-reachable button on phones. */}
      <Button
        size="lg"
        className="fixed right-4 bottom-4 z-30 rounded-full shadow-lg sm:hidden"
        onClick={() => setEditing("new")}
      >
        <PlusIcon /> Log meal
      </Button>

      <MealSheet
        date={date}
        meal={editing === "new" ? null : editing}
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
      />
    </div>
  )
}
