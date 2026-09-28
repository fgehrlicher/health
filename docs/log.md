# Consumption log

Records what was eaten, when, and how much. It is part of the catalog API
(`make catalog`, <http://127.0.0.1:8000/docs>) and stores its tables in the
`log` database schema.

## Ground rule: no invented numbers

Callers never send nutrition values. An entry holds the original observation, a
time, and zero or more **items**: a catalog food and the amount eaten. The API
calculates every value as the catalog source's value times the amount. The
request format has no nutrition fields, so an agent cannot add its own guesses.

Each entry has a status derived from its items:

| Status | Items | Example |
| --- | --- | --- |
| `measured` | all with an exact amount | the whole 400 g cup, 30 g weighed nuts |
| `estimated` | at least one amount range | "a big Döner": bread 100–130 g, meat 120–180 g, … |
| `unknown` | none | "dinner at the Italian place" with no details |

An estimate must still name catalog foods; BLS includes many prepared dishes
such as pizza, lasagne, and curries. If no catalog food fits, the entry stays
unknown rather than getting an invented number.

## Items

Each item names a food by `food` (its slug) and exactly one amount:

- `amount`: exact, in the source's unit (g or ml);
- `amount_min` and `amount_max`: an estimated range;
- `portion` and optional `count`: a named portion of that food, e.g.
  `{"portion": "Becher"}` for a 400 g cup. Unknown portion names are rejected
  with the list of known ones.

`source_id` chooses a specific source; by default the food's BLS 4.0 source is
used, otherwise its newest one. `label` describes what the item stands for,
e.g. "Fladenbrot" within a Döner.

When logged, the item stores a **snapshot** of the source's values. Later
catalog changes, such as a corrected BLS value or a new label version, do not
change past entries.

## Time and days

`eaten_at` defaults to now. A time without an offset is local time in
`HEALTH_TIMEZONE` (default `Europe/Berlin`). Times more than ten minutes in the
future are rejected. A day runs from local midnight to local midnight, including
23- and 25-hour days at daylight-saving changes.

## Endpoints

- `POST /api/log/entries`: log an entry; `?dry_run=true` returns the calculated
  entry without storing it.
- `GET /api/log/entries/{id}`: one entry with items and totals.
- `PUT /api/log/entries/{id}/items`: replace the items, e.g. to fill in an
  unknown meal or correct an amount. Previous items stay stored as superseded.
- `PATCH /api/log/entries/{id}`: correct `eaten_at`.
- `DELETE /api/log/entries/{id}`: remove from totals; the entry stays stored as
  deleted.
- `GET /api/log/days/{YYYY-MM-DD}`: a day's entries and totals.

Invalid requests return `422` with `field`/`message` issues and write nothing.

```json
POST /api/log/entries
{
  "observation": "had the whole peach quark cup",
  "eaten_at": "2026-09-28T16:50:00",
  "items": [{"food": "milbona-high-protein-quark-creme-pfirsich-maracuja", "portion": "Becher"}]
}
```

```json
POST /api/log/entries
{
  "observation": "big Döner from the place near work",
  "items": [
    {"food": "…bread slug…", "label": "Fladenbrot", "amount_min": 100, "amount_max": 130},
    {"food": "…meat slug…", "label": "Dönerfleisch", "amount_min": 120, "amount_max": 180}
  ]
}
```

## Day totals

`GET /api/log/days/{date}` returns, per nutrient column (the 14 label fields):

- `measured`: the sum over measured entries;
- `estimated_min` and `estimated_max`: the range over estimated entries;
- `items_without_value`: how many items' sources lack that nutrient, so a total
  is a lower bound when this is not 0.

`counts` gives the number of measured, estimated, and unknown entries. Together
they read as "1,840 kcal measured, 450–700 kcal estimated, 1 meal unknown"
instead of one falsely precise number.

## Not included

Totals cover the 14 label fields, not vitamins and minerals. There are no
recipes, meal-prep batches, or reusable meal templates, and no agent tooling
beyond this HTTP API.
