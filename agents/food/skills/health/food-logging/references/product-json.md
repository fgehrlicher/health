# Product JSON for `health product check` and `register`

Write the file with the fields below. The check rejects any other top-level key.

## Fields

- `name`: the product name as printed (required).
- `brand`: the brand as printed.
- `barcode`: the EAN as a string, digits only (copy it from the package). If it
  cannot be read, leave it out; add it later with `health product barcode <slug> <code>`.
- `food_group`: one letter from the catalog's groups. Do not guess it. Copy the letter from a similar catalog food, found with `health foods search`. Group `P` is not protein; it reads "Alcoholic drinks" in the catalog, so a protein bar set to `P` is wrong.
- `portions`: a list of `{"name", "kind": "package", "quantity", "unit"}`, for example the bar's wrapper weight as `Riegel`, 45 g.
- `nutrition`: a single object per 100 g or 100 ml, with `reference_quantity`, `reference_unit`, and the values (`energy_kj`, `energy_kcal`, `fat_g`, `saturated_fat_g`, `carbs_g`, `sugars_g`, `polyols_g`, `fiber_g`, `protein_g`, `salt_g`). Convert a per-serving label to per 100 g before you enter it.

Do not send `kind`, `sources`, `label_gaps`, or `slug`. The check rejects them with "Extra inputs are not permitted" (exit code 2).

## Ingredients and legal name

The check warns when `ingredients_text` is missing; it is mandatory on most EU labels. Only send the full list once it is complete (see the Photos section in SKILL.md). A missing list leaves a label gap, not a rejection.

## Checking a product

1. Run `health product check --file p.json`. The output lists `warnings` and a `food` slug on a dry run.
2. Report the warnings to him in one line each.
3. Register with `--commit` only after he confirms.
4. Log a meal with the returned slug, and the portion name you gave the package (for example `Riegel`).
