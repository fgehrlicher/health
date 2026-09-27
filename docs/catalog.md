# Food catalog browser and API

This is a read-only first view of the food catalog. It searches foods, aliases,
brands, barcodes, source food names, and external IDs. Filters cover food type,
preparation state, source, minimum protein and fiber, and maximum energy.
Sorting and pagination work on the same API. A food detail shows every
nutrition source, its reference quantity, and any unknown values.

## Run locally

From the repository root:

```sh
make db-up
make db-fixture                         # optional starter data
uv run --locked health-catalog
```

Open <http://127.0.0.1:8000>. To browse the reviewed BLS starter set, run
`uv run --locked bls4-import` first. The catalog uses `DATABASE_URL` if set;
otherwise it connects to the local Compose database.

The server binds to `127.0.0.1` by default. It has no login yet. Do not expose
it to a public network. An explicit `--host` and `--port` are available for a
private deployment once access control and networking are decided.

## API

- `GET /api/foods` — paginated food list; parameters: `q`, `kind`,
  `preparation_state`, `source_name`, `min_protein`, `min_fiber`, `max_energy`,
  `sort`, `limit`, `offset`.
- `GET /api/foods/facets` — available filter values and catalog counts.
- `GET /api/foods/{slug}` — food details and all nutrition sources.
- `GET /docs` — interactive API documentation.

List results show one source per food: the requested source when filtered,
otherwise BLS 4.0 if present, then the first source record. The source is
always named; it is not a universal or merged nutrition value. Filters and
nutrition sorting compare values on each displayed source's stated reference
basis, usually 100 g for BLS. Unknown nutrient values are `null` and do not
match numeric filters. API decimal amounts are strings to avoid losing source
precision. The browser shows a dash for unknown values, never a fabricated zero.

The UI and API are served from one process and origin. The manifest makes the
site home-screen friendly; offline behavior is not implemented yet. Logging,
editing, recipes, and the daily dashboard remain separate future work.
