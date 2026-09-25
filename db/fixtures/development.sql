BEGIN;

INSERT INTO measurement_units (code, name, symbol, dimension)
VALUES
    ('g', 'gram', 'g', 'mass'),
    ('mg', 'milligram', 'mg', 'mass'),
    ('ug', 'microgram', 'µg', 'mass'),
    ('kcal', 'kilocalorie', 'kcal', 'energy')
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    symbol = EXCLUDED.symbol,
    dimension = EXCLUDED.dimension;

INSERT INTO nutrients (code, name, default_unit_code)
VALUES
    ('energy_kcal', 'Energy', 'kcal'),
    ('protein', 'Protein', 'g'),
    ('fat', 'Fat', 'g'),
    ('available_carbohydrate', 'Available carbohydrate', 'g'),
    ('fiber', 'Total dietary fiber', 'g'),
    ('vitamin_b12', 'Vitamin B12', 'ug'),
    ('vitamin_c', 'Vitamin C', 'mg'),
    ('beta_carotene', 'Beta-carotene', 'ug')
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    default_unit_code = EXCLUDED.default_unit_code;

INSERT INTO data_sources (slug, name, kind, homepage_url, license)
VALUES (
    'bls',
    'Bundeslebensmittelschlüssel',
    'dataset',
    'https://blsdb.de/',
    'CC-BY-4.0'
)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    kind = EXCLUDED.kind,
    homepage_url = EXCLUDED.homepage_url,
    license = EXCLUDED.license;

INSERT INTO source_releases (
    data_source_id,
    version,
    published_on,
    retrieved_at,
    source_url,
    citation,
    sha256,
    metadata
)
SELECT
    id,
    '4.0',
    NULL,
    TIMESTAMPTZ '2026-09-25 00:00:00+02',
    'https://blsdb.de/download',
    'Max Rubner-Institut (2025): Bundeslebensmittelschlüssel (BLS), Version 4.0 — Deutsche Nährstoffdatenbank. Karlsruhe.',
    '524bbefe25b691f5cb3de7a9f3e27fa2967aebfeabf217d99414ba7806e78c60',
    '{"artifact":"BLS_4_0_Daten_2025_DE.xlsx","package_sha256":"12b7a6ba62807ec9b301eb276f897dc85f99b2292311618dec3749a12d984c91","retrieved_at_precision":"date"}'::jsonb
FROM data_sources
WHERE slug = 'bls'
ON CONFLICT (data_source_id, version) DO NOTHING;

INSERT INTO source_foods (
    data_source_id,
    source_release_id,
    external_id,
    name,
    name_en
)
SELECT source.id, release.id, fixture.external_id, fixture.name, fixture.name_en
FROM source_releases AS release
JOIN data_sources AS source ON source.id = release.data_source_id
CROSS JOIN (VALUES
    ('F110100', 'Apfel roh', 'Apple raw'),
    ('C352000', 'Reis poliert, roh', 'White rice raw'),
    ('H725100', 'Linse reif', 'Lentil mature')
) AS fixture(external_id, name, name_en)
WHERE source.slug = 'bls' AND release.version = '4.0'
ON CONFLICT (source_release_id, external_id)
    WHERE source_release_id IS NOT NULL AND external_id IS NOT NULL
DO NOTHING;

INSERT INTO foods (slug, name, kind, preparation_state)
VALUES
    ('apple-raw', 'Apple', 'ingredient', 'raw'),
    ('white-rice-raw', 'White rice', 'ingredient', 'raw'),
    ('lentil-mature-dry', 'Lentils', 'ingredient', 'dried')
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    kind = EXCLUDED.kind,
    preparation_state = EXCLUDED.preparation_state;

INSERT INTO food_source_mappings (
    food_id,
    source_food_id,
    relationship
)
SELECT food.id, source_food.id, 'exact'
FROM (VALUES
    ('apple-raw', 'F110100'),
    ('white-rice-raw', 'C352000'),
    ('lentil-mature-dry', 'H725100')
) AS fixture(food_slug, external_id)
JOIN foods AS food ON food.slug = fixture.food_slug
JOIN data_sources AS source ON source.slug = 'bls'
JOIN source_releases AS release
    ON release.data_source_id = source.id AND release.version = '4.0'
JOIN source_foods AS source_food
    ON source_food.source_release_id = release.id
    AND source_food.external_id = fixture.external_id
ON CONFLICT (food_id, source_food_id) DO UPDATE SET
    relationship = EXCLUDED.relationship,
    rationale = NULL;

INSERT INTO food_aliases (food_id, name, locale, source_food_id)
SELECT food.id, fixture.alias, fixture.locale, source_food.id
FROM (VALUES
    ('apple-raw', 'Apfel roh', 'de', 'F110100'),
    ('apple-raw', 'Apple raw', 'en', 'F110100'),
    ('white-rice-raw', 'Reis poliert, roh', 'de', 'C352000'),
    ('white-rice-raw', 'White rice raw', 'en', 'C352000'),
    ('lentil-mature-dry', 'Linse reif', 'de', 'H725100'),
    ('lentil-mature-dry', 'Lentil mature', 'en', 'H725100')
) AS fixture(food_slug, alias, locale, external_id)
JOIN foods AS food ON food.slug = fixture.food_slug
JOIN data_sources AS source ON source.slug = 'bls'
JOIN source_releases AS release
    ON release.data_source_id = source.id AND release.version = '4.0'
JOIN source_foods AS source_food
    ON source_food.source_release_id = release.id
    AND source_food.external_id = fixture.external_id
ON CONFLICT DO NOTHING;

INSERT INTO nutrient_profiles (
    source_food_id,
    reference_quantity,
    reference_unit_code,
    acquisition_method
)
SELECT source_food.id, 100, 'g', 'bulk_import'
FROM source_foods AS source_food
JOIN source_releases AS release ON release.id = source_food.source_release_id
JOIN data_sources AS source ON source.id = release.data_source_id
WHERE source.slug = 'bls'
    AND release.version = '4.0'
    AND source_food.external_id IN ('F110100', 'C352000', 'H725100')
ON CONFLICT (source_food_id, reference_quantity, reference_unit_code) DO NOTHING;

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
)
INSERT INTO nutrient_values (
    nutrient_profile_id,
    nutrient_code,
    source_nutrient_id,
    source_unit_code,
    source_value,
    source_provenance,
    normalized_amount,
    value_state,
    derivation_method,
    normalization_method,
    source_reference
)
SELECT
    profile.id,
    fixture.nutrient_code,
    CASE fixture.nutrient_code
        WHEN 'energy_kcal' THEN 'ENERCC'
        WHEN 'protein' THEN 'PROT625'
        WHEN 'fat' THEN 'FAT'
        WHEN 'available_carbohydrate' THEN 'CHO'
        WHEN 'fiber' THEN 'FIBT'
        WHEN 'vitamin_b12' THEN 'VITB12'
        WHEN 'vitamin_c' THEN 'VITC'
        WHEN 'beta_carotene' THEN 'CARTB'
    END,
    CASE fixture.nutrient_code
        WHEN 'energy_kcal' THEN 'kcal'
        WHEN 'vitamin_b12' THEN 'ug'
        WHEN 'vitamin_c' THEN 'mg'
        WHEN 'beta_carotene' THEN 'ug'
        ELSE 'g'
    END,
    fixture.raw_value,
    fixture.derivation_method,
    fixture.amount,
    fixture.value_state,
    fixture.derivation_method,
    'identity',
    fixture.source_reference
FROM fixture
JOIN data_sources AS source ON source.slug = 'bls'
JOIN source_releases AS release
    ON release.data_source_id = source.id AND release.version = '4.0'
JOIN source_foods AS source_food
    ON source_food.source_release_id = release.id
    AND source_food.external_id = fixture.external_id
JOIN nutrient_profiles AS profile
    ON profile.source_food_id = source_food.id
    AND profile.reference_quantity = 100
    AND profile.reference_unit_code = 'g'
ON CONFLICT (nutrient_profile_id, nutrient_code) DO NOTHING;

COMMIT;
