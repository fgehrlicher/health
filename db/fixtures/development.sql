BEGIN;

INSERT INTO foods (slug, name, aliases, preparation_state)
VALUES
    ('apple-raw', 'Apple', ARRAY['Apfel roh', 'Apple raw'], 'raw'),
    ('white-rice-raw', 'White rice', ARRAY['Reis poliert, roh', 'White rice raw'], 'raw'),
    ('lentil-mature-dry', 'Lentils', ARRAY['Linse reif', 'Lentil mature'], 'dried')
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    aliases = EXCLUDED.aliases,
    preparation_state = EXCLUDED.preparation_state;

INSERT INTO food_sources (
    food_id,
    source_name,
    external_id,
    food_name,
    reference_quantity,
    reference_unit,
    capture_method,
    source_url
)
SELECT
    food.id,
    'BLS 4.0', fixture.external_id, fixture.food_name,
    100, 'g', 'bulk_import', 'https://blsdb.de/download'
FROM (VALUES
    ('apple-raw', 'F110100', 'Apfel roh'),
    ('white-rice-raw', 'C352000', 'Reis poliert, roh'),
    ('lentil-mature-dry', 'H725100', 'Linse reif')
) AS fixture(food_slug, external_id, food_name)
JOIN foods AS food ON food.slug = fixture.food_slug
WHERE NOT EXISTS (
    SELECT 1 FROM food_sources AS existing
    WHERE existing.source_name = 'BLS 4.0'
        AND existing.external_id = fixture.external_id
);

WITH fixture (
    external_id,
    nutrient_code,
    amount,
    value_state,
    derivation_method,
    raw_value,
    source_reference
) AS (VALUES
    ('F110100', 'energy_kcal', 58::numeric, 'reported', 'formula_calculation', '58', NULL),
    ('F110100', 'protein', 0.424, 'reported', 'aggregation', '0.424', 'Converted value from: Koivistoinen P; Mineral element composition of Finnish foods. N, K, Ca, Mg, P, S, Fe, Cu, Mn, Zn, Mo, Co, Ni, Cr, F, Se, Si, Rb, Al, B, Br, Hg, As, Cd, Pb and Ash; Almqvist & Wiksell; 1980#Converted value from: Health, D. o; Nutrient analysis of fruit and vegetables; 2013'),
    ('F110100', 'fat', 0.5, 'reported', 'literature', '0.5', 'Health, D. o; Nutrient analysis of fruit and vegetables; 2013'),
    ('F110100', 'available_carbohydrate', 11.7, 'reported', 'formula_calculation', '11.7', NULL),
    ('F110100', 'fiber', 2.275, 'reported', 'aggregation', '2.275', 'Converted value from: Feliciano, R. P., Antunes, C., Ramos, A., Serra, A. T., Figueira, M. E., Duarte, C. M. M., Carvalho, A. d, Bronze, M. R.; Characterization of traditional and exotic apple varieties from Portugal. Part 1 - Nutritional, phytochemical and sensory evaluation; Journal of Fuctional Foods; 2010; 2#Converted value from: Li, B. W. and Andrews, K. W.; Individual sugars, soluble, and insoluble dietary fiber contents of 70 high consumption foods.; Journal of Food Composition and Analysis; 2002; 15#Converted value from: Ramulu, P., Rao, P. U.; Total, insoluble and soluble dietary fiber contents of Indian fruits; Journal of Food Composition and Analysis; 2003; 16#Converted value from: Lee, Y., et al. ; Analytical dietary fiber database for the National Health and Nutrition Survey in Korea.; Journal of Food Composition and Analysis; 2008; 21'),
    ('F110100', 'vitamin_b12', 0, 'reported', 'logical_zero', '0', NULL),
    ('F110100', 'vitamin_c', 10.16, 'reported', 'analysis', '10.16', NULL),

    ('C352000', 'energy_kcal', 351, 'reported', 'formula_calculation', '351', NULL),
    ('C352000', 'protein', 7.931, 'reported', 'nutrient_database', '7.931', 'Converted value from: Kirchhoff, E; Souci - Fachmann - Kraut - Die Zusammensetzung der Lebensmittel - Nährwert-Tabellen; 2008; 7'),
    ('C352000', 'fat', 0.62, 'reported', 'nutrient_database', '0.62', 'Kirchhoff, E; Souci - Fachmann - Kraut - Die Zusammensetzung der Lebensmittel - Nährwert-Tabellen; 2008; 7'),
    ('C352000', 'available_carbohydrate', 77.1, 'reported', 'formula_calculation', '77.1', NULL),
    ('C352000', 'fiber', 2.5, 'reported', 'analysis', '2.5', NULL),
    ('C352000', 'vitamin_b12', 0, 'reported', 'logical_zero', '0', NULL),
    ('C352000', 'vitamin_c', NULL, 'below_detection_or_quantification_limit', 'nutrient_database', '<LOD or <LOQ', 'Kirchhoff, E; Souci - Fachmann - Kraut - Die Zusammensetzung der Lebensmittel - Nährwert-Tabellen; 2008; 7'),
    ('C352000', 'beta_carotene', NULL, 'missing', 'unknown', '-', NULL),

    ('H725100', 'energy_kcal', 323, 'reported', 'formula_calculation', '323', NULL),
    ('H725100', 'protein', 23.357, 'reported', 'nutrient_database', '23.357', 'Converted value from: Kirchhoff, E; Souci - Fachmann - Kraut - Die Zusammensetzung der Lebensmittel - Nährwert-Tabellen; 2008; 7'),
    ('H725100', 'fat', 1.7, 'reported', 'aggregation', '1.7', 'de Almeida Costa, G. E., et al.; Chemical composition, dietary fibre and resistant starch contents of raw and cooked pea, common bean, chickpea and lentil legumes.; Food Chemistry; 2006; 94; 3#Public Health England, Nutrient analysis of fruits and vegetables. 2017#Senser F., Scherz H.; Fleisch+ -prod., Fisch+ -prod., Gemüse+ -prod., Früchte+ -prod., Süßw., alkoholh; Brief vom 19.08.93 Deut. Forschungsanst. f. Lebensmittelchem; 1993#Kirchhoff, E; Souci - Fachmann - Kraut - Die Zusammensetzung der Lebensmittel - Nährwert-Tabellen; 2008; 7'),
    ('H725100', 'available_carbohydrate', 44.8, 'reported', 'formula_calculation', '44.8', NULL),
    ('H725100', 'fiber', 17.6, 'reported', 'aggregation', '17.6', 'Converted value from: de Almeida Costa, G. E., et al.; Chemical composition, dietary fibre and resistant starch contents of raw and cooked pea, common bean, chickpea and lentil legumes.; Food Chemistry; 2006; 94; 3#Public Health England, Nutrient analysis of fruits and vegetables. 2017#Converted value from: Perez-Hidalgo, M. A., Guerra-Hernández, E., García-Villanova, B.; Dietary fiber in three raw legumes and processing effect on chick peas by an enzymatic-gravimetric method; Journal of Food Composition and Analysis; 1997'),
    ('H725100', 'vitamin_b12', 0, 'reported', 'logical_zero', '0', NULL),
    ('H725100', 'vitamin_c', 7, 'reported', 'nutrient_database', '7', 'Kirchhoff, E; Souci - Fachmann - Kraut - Die Zusammensetzung der Lebensmittel - Nährwert-Tabellen; 2008; 7')
), source_nutrients AS (
    SELECT
        external_id,
        max(amount) FILTER (WHERE nutrient_code = 'energy_kcal') AS energy_kcal,
        max(amount) FILTER (WHERE nutrient_code = 'protein') AS protein_g,
        max(amount) FILTER (WHERE nutrient_code = 'fat') AS fat_g,
        max(amount) FILTER (WHERE nutrient_code = 'available_carbohydrate') AS carbs_g,
        max(amount) FILTER (WHERE nutrient_code = 'fiber') AS fiber_g,
        max(amount) FILTER (WHERE nutrient_code = 'vitamin_b12') AS vitamin_b12_ug,
        max(amount) FILTER (WHERE nutrient_code = 'vitamin_c') AS vitamin_c_mg,
        max(amount) FILTER (WHERE nutrient_code = 'beta_carotene') AS beta_carotene_ug,
        jsonb_build_object(
            'nutrients',
            jsonb_object_agg(
                CASE nutrient_code
                    WHEN 'energy_kcal' THEN 'ENERCC'
                    WHEN 'protein' THEN 'PROT625'
                    WHEN 'fat' THEN 'FAT'
                    WHEN 'available_carbohydrate' THEN 'CHO'
                    WHEN 'fiber' THEN 'FIBT'
                    WHEN 'vitamin_b12' THEN 'VITB12'
                    WHEN 'vitamin_c' THEN 'VITC'
                    WHEN 'beta_carotene' THEN 'CARTB'
                END,
                jsonb_strip_nulls(jsonb_build_object(
                    'value', raw_value,
                    'unit', CASE nutrient_code
                        WHEN 'energy_kcal' THEN 'kcal'
                        WHEN 'vitamin_b12' THEN 'ug'
                        WHEN 'vitamin_c' THEN 'mg'
                        WHEN 'beta_carotene' THEN 'ug'
                        ELSE 'g'
                    END,
                    'state', value_state,
                    'provenance', derivation_method,
                    'reference', source_reference
                ))
            )
        ) AS raw_data
    FROM fixture
    GROUP BY external_id
)
UPDATE food_sources AS source
SET energy_kcal = nutrients.energy_kcal,
    protein_g = nutrients.protein_g,
    fat_g = nutrients.fat_g,
    carbs_g = nutrients.carbs_g,
    fiber_g = nutrients.fiber_g,
    vitamin_b12_ug = nutrients.vitamin_b12_ug,
    vitamin_c_mg = nutrients.vitamin_c_mg,
    beta_carotene_ug = nutrients.beta_carotene_ug,
    raw_data = nutrients.raw_data
FROM source_nutrients AS nutrients
WHERE source.source_name = 'BLS 4.0'
    AND source.external_id = nutrients.external_id;

COMMIT;
