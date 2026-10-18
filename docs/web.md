# Web frontend

The app in [`web/`](../web/) is how I use the system in a browser, on the
desktop and the phone. It consumes the health API and holds no data or rules of
its own.

## Pages

- **Today** (`/`, `/?date=2026-09-28`): the day's calories as a bar against
  the daily limit, then its protein, fat, carbs and fiber, and its meals.
  Estimated amounts count like measured ones in these totals; a meal card marks
  its estimated items with "~" and shows an unknown meal as a badge. The bar
  fills on a scale up to the limit plus the tolerance, with a mark at the limit,
  in the calendar's colors (green within the limit, yellow up to the tolerance
  above it, red beyond), and says how many kcal are left or how far over. The
  **Incomplete day** switch marks a day on which meals are missing: it stays
  visible but is left out of the stats, and its bar is gray and not judged.
  Arrows move between days. **Log meal** opens a form: meal kind, time, a note
  for raw thoughts, and the foods. A catalog food found by search takes an
  amount or a label portion (e.g. "Becher") and a "guessed" switch; **Cooked
  dish** takes portions from the cooking log; **Without product** takes a name,
  its kcal, and any of protein, fat, carbs and fiber the person knows (an empty
  value stays unknown). The form shows the calculated calories and protein
  before saving, using the API's dry run. A meal without foods is logged as
  unknown. Every meal can be edited or deleted, including a stated item's
  values.
- **Stats** (`/stats`): the last 53 weeks. The daily kcal limit and the
  tolerance above it are set at the top, and a line counts the days within the
  limit, up to the tolerance above it, and beyond. A calendar like GitHub's has
  one cell per day, Monday to Sunday, scrolled to the latest weeks: green
  within the limit, yellow up to the tolerance above, red beyond, gray without
  meals, and a dashed border on an incomplete day, which stays gray whatever was
  eaten. Tapping a day opens its card: kcal against the limit, its meals
  (unknown ones not counted), the incomplete switch, and **Open this day**.
  Below are charts: the energy split by week (26 weeks) and by day (30 days),
  calories per day for 90 days with the 7-day average and the limit, calories
  per day averaged by week and by weekday, and the energy split of the whole
  period. Incomplete days and days without known energy are left out of every
  number.
- **Recipes** (`/recipes`, `/recipes?tag=ice%20cream`): recipe cards with
  their tags and the latest version's calories, protein, and energy split per
  portion, a name filter, and the cooking log with portions left. Tags with
  their counts form a sidebar on wide screens and chips on phones; choosing one
  narrows the recipes and the cooking log, and a new recipe starts with it. **New recipe** and **Log improvised cook** open forms.
- **Recipe** (`/recipes/{slug}`): its tags, edited in place with suggestions
  from existing tags, and the history of versions, newest first. Each
  shows its note on what changed, the ingredients that differ from its parent
  (e.g. "Rice 600 → 400 g"), nutrition per portion, ingredients and steps, and
  the cooks made from it. Each version can be edited in place (**Edit this
  version**: ingredients, portions, steps and note, with no new version), cooked,
  developed into a new version, or forked into a new recipe; variations and the
  recipe it was forked from are linked.
- **Cook** (`/cooks/{id}`): when it was cooked, how it turned out, one
  portion's nutrition, what went in, and how that differs from its version.
  **Eat a portion** logs it as a meal; **Save as new version** (or **Save as
  recipe** for an improvised cook) turns it into the next version. A cook form
  starts with the version's ingredients to adjust freely and previews calories
  per portion. An ingredient that is a generic food with linked products (or
  one of those products) gets a **Product** menu to swap in what was actually
  used; the cook then shows "Alpro … instead of Soya drink unsweetened".
- **Foods** (`/foods`): the catalog as cards. Each card shows calories and a
  bar of where the energy comes from. The 20 BLS food groups, each with an
  icon and count, form a sidebar on wide screens and a **Categories** menu on
  phones. Type, preparation, and sort ("Most protein per kcal", "Fewest
  calories", …) are menus. Categories and menus list only values that match
  the other filters, with counts: with "Branded" chosen, only categories
  holding branded foods remain, and a **Brand** menu lists the brands. **Needs photos** (shown while any product
  has an incomplete label, with its count) lists only those products, marked
  "needs photos" on their cards. **Clear filters** appears while search,
  category, type, or preparation is set, also in an empty result, and keeps
  the sort; **Load more** adds the next 40. Category, search,
  filters, and sort are in the URL (`/foods?group=F`), so back and new tabs
  work.
- **Food** (`/foods/{slug}`): key figures, a donut of where the energy comes
  from, a bar of what 100 g contain (macros, water, rest), the full nutrition
  label with ingredients, and vitamins and minerals as a share of the EU daily
  reference intake, plus **Log this food**. A generic food's group links to
  its category; a product has a category menu to set it, and its brand links
  to all products of that brand. A product whose label still lacks something (ingredient list,
  legal name, barcode, or a mandatory nutrition row) shows **Label incomplete**
  with what to photograph next time. A product can be linked to the generic food
  it is a kind of (**Kind of**), and a generic food lists its linked
  **Products of this kind** with their calories and protein. **Delete product**
  removes a product: one that nothing uses goes at once; one used in meals,
  recipes or cooks first needs a food to take its place there, with the same
  amounts (its **Kind of** food is suggested), checked by a dry run before the
  button turns on. Generic foods have no delete.

The theme is warm: cream surfaces and green as the main color, in light and
dark variants that follow the system or the toggle in the header. Protein,
fat, carbs, fiber, and alcohol have fixed colors everywhere (`--macro-*` in
`src/styles.css`), checked for color-vision deficiency and contrast in both
modes; charts always label values, so color never carries meaning alone. A
dash always means unknown, never zero.

## Stack

- [TanStack Start](https://tanstack.com/start) with React 19: file routes in
  `src/routes/`, server rendering, and server functions.
- [TanStack Query](https://tanstack.com/query) for loading and caching,
  prefetched during server rendering.
- [shadcn/ui](https://ui.shadcn.com/) (style `base-nova` on Base UI) with
  Tailwind CSS 4. Components in `src/components/ui/` come from the shadcn CLI
  (`pnpm dlx shadcn@latest add …`); they are not edited or linted by hand.
- TypeScript, ESLint, Prettier, pnpm, and Vite 8.

## How it talks to the API

The browser never calls FastAPI. It calls server functions in `src/server/`,
which run in the web server and call the API at `HEALTH_API_URL` (default
`http://127.0.0.1:8000`). FastAPI can therefore stay reachable only on the
machine, and there is no cross-origin setup.

API types are generated from FastAPI's OpenAPI schema: `make web-types` writes
`web/openapi.json` and `web/src/lib/api/schema.gen.ts`. Run it after changing
an API model; `make check-web` fails while they are stale.

## Run and check

```sh
make db-up
make api        # FastAPI on 127.0.0.1:8000
make web        # the app on http://localhost:3000
```

- `make check-web`: API types up to date, lint, formatting, type check, unit
  tests (`pnpm test`: vitest, for the pure functions in `src/lib`), and a
  production build.
- `make check-e2e`: browser tests with Playwright, on a desktop and a phone
  screen. They start their own API on port 8010 against their own throwaway
  `health_e2e` database and their own app on port 3010, so neither the real log
  nor the API tests' `health_test` database is touched. The tests wait until the page is interactive
  (`html[data-hydrated]`) before clicking.

The app has no login. Like the API, it is meant for this machine or a private
network only.
