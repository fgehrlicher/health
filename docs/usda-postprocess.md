# USDA post-processing: food groups and German names

The USDA foods come in English, and without a food group. This one-off step
gives each of them a catalog food group, the same groups the BLS foods use, and
a German name. It also gives the 20 food groups German names. It runs after the
import, on the foods in `catalog.foods` that have a USDA source.

The decisions are made by an LLM, batch by batch, following
[`importers/usda/postprocess/PROMPT.md`](../importers/usda/postprocess/PROMPT.md).
The code does the rest and checks the decisions. The decisions are committed in
[`importers/usda/postprocess/decisions/`](../importers/usda/postprocess/decisions/),
so the result can be reproduced without asking an LLM again.

## Steps

1. **Export the batches.** This only reads. The batches go to `data/usda/batches`,
   which is git-ignored.

   ```sh
   DATABASE_URL=… uv run --locked usda-postprocess export --out data/usda/batches --batch-size 250
   ```

   Each batch file is a JSON array of foods: `slug`, English `name`, USDA's own
   `usda_category` (a hint only) and `preparation_state`.

2. **Decide, batch by batch.** For each batch, an LLM reads PROMPT.md and the batch
   file, and writes `decisions/batch-NN.json`: one item per food, with `slug`,
   `food_group` (one of the catalog's codes) and `name_de`. The decisions were
   made by sub-agents, one batch each, in parallel. Each agent checked its own file
   against its batch before it reported.

3. **Check.** A dry run of `apply` checks every decision. It refuses unless every
   USDA food has exactly one decision with a catalog group and a German name, and
   the group names cover all catalog groups.

   ```sh
   uv run --locked usda-postprocess apply
   ```

4. **Apply.** `--commit` writes the group, the German name and, for search, the
   German name as an alias. Group names are written from `groups.json`. The
   search index is rebuilt. Applying twice changes nothing.

   ```sh
   DATABASE_URL=… uv run --locked usda-postprocess apply --commit
   ```

## What is stored

- `catalog.foods.food_group`: one of the BLS group codes (B, C, D, E, F, G, H,
  K, M, N, P, Q, R, S, T, U, V, W, X, Y).
- `catalog.foods.name_de`: the German name. The API shows it first, as it does
  for BLS foods. The English name stays in `name`.
- `catalog.food_groups.name_de`: the German name of each group, from
  [`groups.json`](../importers/usda/postprocess/groups.json).

The schema change is `db/migrations/0001_german_names.sql`. The migration runs
on deploy.

## Limits

- The LLM decisions are judgement. The checks catch missing, repeated and
  invalid decisions, not wrong ones. Spot-check a sample of the decision files
  before you apply.
- Foods with a BLS name keep it. For BLS foods, the German name is the BLS
  name, and `name_de` is not used.
- The groups are fixed. A food that fits no group needs a decision on whether to
  add one to `groups.json` and the database.
