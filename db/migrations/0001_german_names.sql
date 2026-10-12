-- German names for foods without a BLS name (set by the USDA post-processing)
-- and for every food group. Foods keep their English name in `name`.
ALTER TABLE catalog.foods ADD COLUMN name_de text;
ALTER TABLE catalog.food_groups ADD COLUMN name_de text;
