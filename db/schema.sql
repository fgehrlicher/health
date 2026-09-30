-- Mutable baseline until the first deployment; changes need `make db-reset`.
-- Content validation belongs in the importers and the API.
-- Two schemas: catalog (foods and their nutrition) and log (what was eaten).

-- Foods, their nutrition sources, portions, and search. BLS rows can be
-- rebuilt by the importer; registered products cannot.
CREATE SCHEMA catalog;

CREATE TABLE catalog.foods (
    -- Stable identity within this catalog.
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug text NOT NULL UNIQUE,

    -- Display and search names.
    name text NOT NULL,
    aliases text[] NOT NULL DEFAULT '{}',

    -- Generic foods from BLS and, later, branded products from your labels.
    kind text NOT NULL DEFAULT 'generic',
    preparation_state text,
    brand text,
    barcode text,

    -- When this catalog entry was added.
    created_at timestamptz NOT NULL DEFAULT now()
);

-- One piece of nutrition evidence for exactly one catalog food.
CREATE TABLE catalog.food_sources (
    -- Catalog food this source actually describes.
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    food_id bigint NOT NULL REFERENCES catalog.foods(id) ON DELETE CASCADE,

    -- Origin and identity supplied by the source, e.g. BLS 4.0 / BLS code.
    source_name text NOT NULL,
    external_id text,
    food_name text NOT NULL,
    -- Source-specific grouping, e.g. the first letter of a BLS code.
    group_code text,

    -- Basis for every nutrition amount below, usually 100 g for BLS.
    reference_quantity numeric NOT NULL,
    reference_unit text NOT NULL,

    -- Nutrition per reference quantity, following the EU label (LMIV) layout.
    -- Units are in the names; NULL means no usable number. "davon" rows are
    -- subsets of the row above them. carbs_g is available carbohydrate, as on
    -- EU labels and in BLS; fiber is separate.
    energy_kj numeric,
    energy_kcal numeric,
    fat_g numeric,
    saturated_fat_g numeric,
    monounsaturated_fat_g numeric,
    polyunsaturated_fat_g numeric,
    carbs_g numeric,
    sugars_g numeric,
    polyols_g numeric,
    starch_g numeric,
    fiber_g numeric,
    protein_g numeric,
    salt_g numeric,
    alcohol_g numeric,

    -- Ingredient list exactly as printed on a label, unparsed. Recipes change,
    -- so it belongs to the source, not the food. NULL for datasets like BLS.
    ingredients_text text,

    -- Nutrition columns whose value is a declared maximum, e.g. a label's
    -- "<0,5 g" stored as fat_g = 0.5 with 'fat_g' listed here.
    upper_bounds text[] NOT NULL DEFAULT '{}'
);

CREATE INDEX food_sources_food_id_idx ON catalog.food_sources (food_id);

-- A barcode identifies one product.
CREATE UNIQUE INDEX foods_barcode_key ON catalog.foods (barcode) WHERE barcode IS NOT NULL;

-- Nutrients beyond the label columns of food_sources, e.g. vitamins and
-- minerals. Units follow EU label conventions; codes are INFOODS tagnames as
-- used by BLS.
CREATE TABLE catalog.nutrients (
    key text PRIMARY KEY,
    name text NOT NULL,
    unit text NOT NULL,
    category text NOT NULL,
    infoods_code text NOT NULL UNIQUE,
    sort_order integer NOT NULL
);

INSERT INTO catalog.nutrients (key, name, unit, category, infoods_code, sort_order) VALUES
    ('vitamin_a', 'Vitamin A (retinol equivalents)', 'µg', 'vitamin', 'VITA', 10),
    ('vitamin_d', 'Vitamin D', 'µg', 'vitamin', 'VITD', 11),
    ('vitamin_e', 'Vitamin E (alpha-tocopherol)', 'mg', 'vitamin', 'VITE', 12),
    ('vitamin_k', 'Vitamin K', 'µg', 'vitamin', 'VITK', 13),
    ('vitamin_c', 'Vitamin C', 'mg', 'vitamin', 'VITC', 14),
    ('thiamin', 'Thiamin (B1)', 'mg', 'vitamin', 'THIA', 15),
    ('riboflavin', 'Riboflavin (B2)', 'mg', 'vitamin', 'RIBF', 16),
    ('niacin', 'Niacin (niacin equivalents)', 'mg', 'vitamin', 'NIAEQ', 17),
    ('vitamin_b6', 'Vitamin B6', 'mg', 'vitamin', 'VITB6', 18),
    ('folate', 'Folate (folate equivalents)', 'µg', 'vitamin', 'FOL', 19),
    ('vitamin_b12', 'Vitamin B12', 'µg', 'vitamin', 'VITB12', 20),
    ('sodium', 'Sodium', 'mg', 'mineral', 'NA', 30),
    ('potassium', 'Potassium', 'mg', 'mineral', 'K', 31),
    ('calcium', 'Calcium', 'mg', 'mineral', 'CA', 32),
    ('magnesium', 'Magnesium', 'mg', 'mineral', 'MG', 33),
    ('phosphorus', 'Phosphorus', 'mg', 'mineral', 'P', 34),
    ('iron', 'Iron', 'mg', 'mineral', 'FE', 35),
    ('zinc', 'Zinc', 'mg', 'mineral', 'ZN', 36),
    ('iodine', 'Iodine', 'µg', 'mineral', 'ID', 37),
    ('omega_3', 'Omega-3 fatty acids', 'g', 'fat', 'FAPUN3', 50),
    ('epa', 'EPA (C20:5 n-3)', 'g', 'fat', 'F20:5CN3', 51),
    ('dha', 'DHA (C22:6 n-3)', 'g', 'fat', 'F22:6CN3', 52),
    ('omega_6', 'Omega-6 fatty acids', 'g', 'fat', 'FAPUN6', 53),
    ('cholesterol', 'Cholesterol', 'mg', 'fat', 'CHORL', 54),
    ('water', 'Water', 'g', 'other', 'WATER', 70),
    ('lactose', 'Lactose', 'g', 'other', 'LACS', 71);

-- One nutrient amount of a source, per the source's reference quantity. No row
-- means unknown; a stored 0 is a reported zero.
CREATE TABLE catalog.food_source_nutrients (
    source_id bigint NOT NULL REFERENCES catalog.food_sources(id) ON DELETE CASCADE,
    nutrient_key text NOT NULL REFERENCES catalog.nutrients(key),
    amount numeric NOT NULL,
    -- A declared maximum, e.g. a label's "<0,1 µg".
    upper_bound boolean NOT NULL DEFAULT false,
    PRIMARY KEY (source_id, nutrient_key)
);

-- Named amounts of a food, e.g. "Portion" 200 g and "Becher" 400 g from a
-- label, used to turn "I ate one cup" into grams.
CREATE TABLE catalog.food_portions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    food_id bigint NOT NULL REFERENCES catalog.foods(id) ON DELETE CASCADE,
    name text NOT NULL,
    -- package: the whole sold unit; serving: the label's portion; piece or
    -- household: other everyday measures such as "1 slice" or "1 tbsp".
    kind text NOT NULL,
    quantity numeric NOT NULL,
    unit text NOT NULL,
    UNIQUE (food_id, name)
);

-- Search terms derived from food names, aliases, source names, BLS codes,
-- brands, and barcodes. Each word is a term, and so is each adjacent pair
-- joined together ("hafer flocken" -> "haferflocken"); `parts` lists the words
-- a term covers. `head` marks words before the first comma, excluding numbers
-- and filler words: BLS names put the food first and qualifiers after commas.
-- Anything that writes foods or sources must call catalog.refresh_search().
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE MATERIALIZED VIEW catalog.food_search_terms AS
WITH titles AS (
    SELECT id AS food_id, lower(name) AS title FROM catalog.foods
    UNION SELECT id, lower(unnest(aliases)) FROM catalog.foods
    UNION SELECT id, lower(brand) FROM catalog.foods WHERE brand IS NOT NULL
    UNION SELECT id, lower(barcode) FROM catalog.foods WHERE barcode IS NOT NULL
    UNION SELECT food_id, lower(food_name) FROM catalog.food_sources
    UNION SELECT food_id, lower(external_id) FROM catalog.food_sources WHERE external_id IS NOT NULL
),
words AS (
    SELECT t.food_id, t.title, m.match[1] AS word, m.position,
           lead(m.match[1]) OVER (PARTITION BY t.food_id, t.title ORDER BY m.position) AS next_word,
           m.position <= (
               SELECT count(*) FROM regexp_matches(split_part(t.title, ',', 1), '[[:alnum:]]+', 'g')
           ) AS in_head
    FROM titles t
    CROSS JOIN LATERAL regexp_matches(t.title, '[[:alnum:]]+', 'g') WITH ORDINALITY AS m (match, position)
)
SELECT food_id, title, word, ARRAY[word] AS parts,
       bool_or(in_head) AND word !~ '^[0-9]+$'
           AND word <> ALL (ARRAY['raw', 'roh', 'and', 'und', 'with', 'mit', 'min', 'max',
                                  'i', 'tr', 'of', 'in']) AS head
FROM words
GROUP BY food_id, title, word
UNION
SELECT food_id, title, word || next_word, ARRAY[word, next_word], false
FROM words
WHERE next_word IS NOT NULL AND word !~ '^[0-9]+$' AND next_word !~ '^[0-9]+$';

CREATE INDEX food_search_terms_word_idx ON catalog.food_search_terms (word);
CREATE INDEX food_search_terms_food_id_idx ON catalog.food_search_terms (food_id);

CREATE MATERIALIZED VIEW catalog.food_search_vocabulary AS
SELECT DISTINCT word FROM catalog.food_search_terms;

-- Rebuild both search views. Call after every write to foods or sources.
CREATE FUNCTION catalog.refresh_search() RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    REFRESH MATERIALIZED VIEW catalog.food_search_terms;
    REFRESH MATERIALIZED VIEW catalog.food_search_vocabulary;
END;
$$;

CREATE UNIQUE INDEX food_search_vocabulary_word_idx ON catalog.food_search_vocabulary (word);
CREATE INDEX food_search_vocabulary_trgm_idx ON catalog.food_search_vocabulary USING gin (word gin_trgm_ops);

-- Consumption log: what was eaten, when, and how much. Nutrition is never
-- stored here; it is always the referenced source's value times the amount.
CREATE SCHEMA log;

-- One sitting. A meal without items was logged, but its nutrition is unknown.
CREATE TABLE log.meals (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    eaten_at timestamptz NOT NULL,
    -- breakfast, lunch, dinner, or snack; NULL when not said.
    kind text,
    -- Free thoughts about the meal, stored as written and never interpreted.
    note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX meals_eaten_at_idx ON log.meals (eaten_at);

-- "This much of this": a catalog source and the amount eaten.
CREATE TABLE log.meal_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    meal_id bigint NOT NULL REFERENCES log.meals(id) ON DELETE CASCADE,
    -- The exact source (e.g. one label version); an eaten food cannot be deleted.
    source_id bigint NOT NULL REFERENCES catalog.food_sources(id) ON DELETE RESTRICT,
    -- In the source's reference unit (g or ml).
    amount numeric NOT NULL,
    -- Guessed rather than weighed or read from a package.
    estimated boolean NOT NULL DEFAULT false
);

CREATE INDEX meal_items_meal_id_idx ON log.meal_items (meal_id);
CREATE INDEX meal_items_source_id_idx ON log.meal_items (source_id);
