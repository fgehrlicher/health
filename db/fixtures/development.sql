BEGIN;

INSERT INTO foods (slug, name, aliases, preparation_state)
VALUES
    ('apple-raw', 'Apple', ARRAY['Apfel roh', 'Apple raw'], 'raw'),
    ('white-rice-raw', 'White rice', ARRAY['Reis poliert, roh', 'White rice raw'], 'raw'),
    ('lentil-mature-dry', 'Lentils', ARRAY['Linse reif', 'Lentil mature'], 'dried')
ON CONFLICT (slug) DO NOTHING;

-- Energy is kcal; protein, fat, available carbohydrate, and fiber are grams.
-- All amounts refer to 100 g of edible food from BLS 4.0.
INSERT INTO food_sources (
    food_id,
    source_name,
    external_id,
    food_name,
    reference_quantity,
    reference_unit,
    energy_kcal,
    protein_g,
    fat_g,
    carbs_g,
    fiber_g,
    source_url
)
SELECT
    food.id,
    'BLS 4.0',
    sample.external_id,
    sample.food_name,
    100,
    'g',
    sample.energy_kcal,
    sample.protein_g,
    sample.fat_g,
    sample.carbs_g,
    sample.fiber_g,
    'https://blsdb.de/download'
FROM (VALUES
    ('apple-raw', 'F110100', 'Apfel roh', 58::numeric, 0.424, 0.5, 11.7, 2.275),
    ('white-rice-raw', 'C352000', 'Reis poliert, roh', 351::numeric, 7.931, 0.62, 77.1, 2.5),
    ('lentil-mature-dry', 'H725100', 'Linse reif', 323::numeric, 23.357, 1.7, 44.8, 17.6)
) AS sample(
    food_slug, external_id, food_name,
    energy_kcal, protein_g, fat_g, carbs_g, fiber_g
)
JOIN foods AS food ON food.slug = sample.food_slug
WHERE NOT EXISTS (
    SELECT 1 FROM food_sources AS existing
    WHERE existing.source_name = 'BLS 4.0'
        AND existing.external_id = sample.external_id
);

COMMIT;
