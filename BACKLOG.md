# Backlog

The one place for planned work. Whenever something is decided, built or dropped,
this file changes first. What exists today is in
[Current state](docs/current-state.md).

How it works:

- **IDs stay.** An item keeps its ID for good, so "B3" means the same thing next
  month. New items get the next free ID: **B13**.
- **Order is priority.** Items under Next are in the order they will be built.
  Move an item to change the plan.
- **Finished items go to Done**, with the date and the doc that describes them.
  Dropped ideas go to Decided, not planned, with the reason.

## Now

- **B1 · Dates in Telegram.** Built and deployed on 2026-10-17. Each of his
  messages reaches the food agent with the time he sent it (Hermes's
  `gateway.message_timestamps`, Europe/Berlin), and `health day today|yesterday`
  resolves the day in the CLI ([Agents](docs/agents.md#safety-of-agent-access)).
  Waiting for a live check from Telegram: "Wie spät ist es?" and "Was habe ich
  gestern gegessen?" Then it moves to Done.

## Next

### B2 · Branded food lookup on demand

Open Food Facts is the first candidate (EAN lookup, free API, good German
coverage). It fits the scan's `not_in_catalog` result. The lookup is read-only
and returns candidates. Registration still needs the user's confirmation. Open
Food Facts data is ODbL, so attribution is required, and the same plausibility
checks apply as to label values.

### B3 · Health evaluation

A module inside the existing API, not a second service (one database). A profile
table (sex, age, height, activity, goal). Protein targets per kg of body weight:
the DGE reference is about 0.8 g/kg for the general population, and the ISSN
position stand is roughly 1.4 to 2.0 g/kg per day for people who train (verify
before relying on it). A guidelines table where every benchmark has a source,
year and quote. The agent may say "sodium was above the reference on 9 of 14
days", but never diagnose. Deficiencies need blood work, not a food log.

### B4 · Agent memory

Health facts (goals, profile, preferences about logging) belong in the database,
not in agent memory. Agent memory keeps conversation style and open threads.
Choose a Hermes memory add-on only after deciding what must be remembered. The
calorie limit already moved to the app; the protein target, weight and goal still
live only in the food agent's memory.

### B5 · The general agent changing the health app

The riskiest item, so last. Guardrails: work on a branch and open a pull request,
never push to `main`; `make check` and `make check-e2e` must pass; deploy only
after the user approves in Telegram; back up before every deploy
(`scripts/backup-db.sh` exists); migrations always need explicit approval; its
credentials can run only the deploy script, with no general sudo. Start
read-only: it reads the code and proposes a diff, and the user applies it.

### B6 · Architecture

Keep one API and one database, the `health` CLI as the agent's only door, and the
web app. Split features into domain modules inside the API. Move rules that can
be validations out of the skill text and into the API. Hermes once overwrote the
stated-item rules on the box, so rules that live only in prose are fragile.

## Small follow-ups

- **B7 · Document the stats work.** [Web](docs/web.md) and
  [Consumption log](docs/log.md) predate it: they do not describe the Stats page,
  incomplete days, the daily limit and tolerance, stated items, or the calorie
  bar on Today, and Today's description is out of date.
- **B9 · Stated items from the web meal sheet.** Today the agent can log them,
  and the web app shows and keeps them, but it cannot create them.
- **B12 · Hermes photo cache (waiting on upstream).** A multiplexed gateway never
  prunes a served profile's media cache, so the food bot's photos stay on the box
  (77 photos, 12 MB on 2026-10-16). Reported as
  [hermes-agent#130413](https://github.com/NousResearch/hermes-agent/issues/130413),
  fixed by [#130414](https://github.com/NousResearch/hermes-agent/pull/130414).
  Once that is merged, run `hermes update` on the box and check that photos older
  than 24 hours go.

## Done

Newest first, from the October 2026 feedback round on.

| Date | What | Details |
| --- | --- | --- |
| 2026-10-17 | B8 · `health product label` stores an ingredient list or legal name read from a later photo; the skill maps each label gap to its command | [Agents](docs/agents.md), [SKILL.md](agents/food/skills/health/food-logging/SKILL.md) |
| 2026-10-17 | B11 · The e2e tests get their own database (`health_e2e`), and the USDA tests put back what they change, so the API tests pass on a reused test database | [Web](docs/web.md) |
| 2026-10-17 | B10 · `pnpm test` runs unit tests only, with tests for the day verdict and the stats; part of `make check-web` | [Web](docs/web.md) |
| 2026-10-17 | Food agent memory cleaned: raw-API notes and the `date` rule removed, the calorie target pointed at the app | on the box only (`memories/` in the food profile) |
| 2026-10-16 | Food skill takes the calorie limit, tolerance and incomplete days from `health day` | [SKILL.md](agents/food/skills/health/food-logging/SKILL.md) |
| 2026-10-16 | Scan tool: barcodes and QR codes in photos, decoded before the agent sees them | [Scan tool](docs/scan-tool.md) |
| 2026-10-15 | Calorie bar on Today against the daily limit | not documented yet (B7) |
| 2026-10-15 | Stated items without a product, the 300 kcal tolerance, daily charts, Today trimmed to four macros | not documented yet (B7) |
| 2026-10-13 | Add a registered product's barcode later (`health product barcode`) | [Catalog](docs/catalog.md#api) |
| 2026-10-12 | Stats page: a calendar of calories per day, incomplete days in gray, charts | not documented yet (B7) |
| 2026-10-12 | The web app works on a phone first | [Web](docs/web.md) |

## Decided, not planned

- **Voice memos:** dropped on 2026-10-16. Neither the Claude nor the Codex
  subscription can transcribe audio for our own tools, and the speech setup
  (local model or API key) was judged too complicated for what it would add.
- **Weight tracking:** left out. Apple Health already covers weight.
- **Stated items:** values come from the user only. A rough figure is flagged as
  estimated. The agent never adds numbers from its own knowledge of a food.
