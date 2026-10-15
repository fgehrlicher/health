-- Items with no catalog product: nutrition the person states, e.g. a label read before the
-- package was thrown away. Only the values they give are stored; nothing is inferred.
-- Such an item has no source and no cook, so the one-of check now counts the stated name too.
DO $$
DECLARE
    one_kind text;
BEGIN
    SELECT conname INTO one_kind
    FROM pg_constraint
    WHERE conrelid = 'log.meal_items'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%num_nonnulls%';
    EXECUTE format('ALTER TABLE log.meal_items DROP CONSTRAINT %I', one_kind);
END
$$;

ALTER TABLE log.meal_items
    ADD COLUMN stated_name text CHECK (btrim(stated_name) <> ''),
    ADD COLUMN stated_energy_kcal numeric(8, 1) CHECK (stated_energy_kcal >= 0),
    ADD COLUMN stated_protein_g numeric(8, 2) CHECK (stated_protein_g >= 0),
    ADD COLUMN stated_fat_g numeric(8, 2) CHECK (stated_fat_g >= 0),
    ADD COLUMN stated_carbs_g numeric(8, 2) CHECK (stated_carbs_g >= 0),
    ADD COLUMN stated_fiber_g numeric(8, 2) CHECK (stated_fiber_g >= 0),
    ADD CONSTRAINT meal_items_one_kind CHECK (num_nonnulls(source_id, cook_id, stated_name) = 1),
    ADD CONSTRAINT meal_items_stated_has_kcal
        CHECK (stated_name IS NULL OR stated_energy_kcal IS NOT NULL);

-- The kcal the person accepts above the daily limit before a day turns red.
ALTER TABLE log.goals
    ADD COLUMN kcal_tolerance integer NOT NULL DEFAULT 300
        CHECK (kcal_tolerance BETWEEN 0 AND 5000);
