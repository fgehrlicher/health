# Web frontend

The app in [`web/`](../web/) is how I use the system in a browser, on the
desktop and the phone. It consumes the health API and holds no data or rules of
its own.

## Pages

- **Today** (`/`, `/?date=2026-09-28`): the day's totals and meals. Calories
  and macros show measured values, with estimated ones listed separately, and
  unknown meals as a badge. Arrows move between days. **Log meal** opens a
  form: meal kind, time, a note for raw thoughts, and foods found by catalog
  search, each with an amount
  or a label portion (e.g. "Becher") and a "guessed" switch. The form shows the
  calculated calories and protein before saving, using the API's dry run. A
  meal without foods is logged as unknown. Every meal can be edited or deleted.
- **Foods** (`/foods`): the catalog as cards. Each card shows calories and a
  bar of where the energy comes from. The 20 BLS food groups, each with an
  icon and count, form a sidebar on wide screens and a **Categories** menu on
  phones. Type, preparation, and sort ("Most protein per kcal", "Fewest
  calories", …) are menus. Categories and menus list only values that match
  the other filters, with counts: with "Branded" chosen, only categories
  holding branded foods remain, and a **Brand** menu lists the brands. **Clear filters** appears while search,
  category, type, or preparation is set, also in an empty result, and keeps
  the sort; **Load more** adds the next 40. Category, search,
  filters, and sort are in the URL (`/foods?group=F`), so back and new tabs
  work.
- **Food** (`/foods/{slug}`): key figures, a donut of where the energy comes
  from, a bar of what 100 g contain (macros, water, rest), the full nutrition
  label with ingredients, and vitamins and minerals as a share of the EU daily
  reference intake, plus **Log this food**. A generic food's group links to
  its category; a product has a category menu to set it, and its brand links
  to all products of that brand.

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

- `make check-web`: API types up to date, lint, formatting, type check, and a
  production build.
- `make check-e2e`: browser tests with Playwright, on a desktop and a phone
  screen. They start their own API on port 8010 against the throwaway
  `health_test` database and their own app on port 3010, so the real log is
  never touched. The tests wait until the page is interactive
  (`html[data-hydrated]`) before clicking.

The app has no login. Like the API, it is meant for this machine or a private
network only.
