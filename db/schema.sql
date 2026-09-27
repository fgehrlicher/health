-- Mutable baseline until the first deployment. Content validation belongs in the importer.

CREATE TABLE foods (
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
CREATE TABLE food_sources (
    -- Catalog food this source actually describes.
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    food_id bigint NOT NULL REFERENCES foods(id) ON DELETE CASCADE,

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

    -- Nutrition columns whose value is a declared maximum, e.g. a label's
    -- "<0,5 g" stored as fat_g = 0.5 with 'fat_g' listed here.
    upper_bounds text[] NOT NULL DEFAULT '{}'
);

CREATE INDEX food_sources_food_id_idx ON food_sources (food_id);

-- Named amounts of a food, e.g. "Portion" 200 g and "Becher" 400 g from a
-- label, used to turn "I ate one cup" into grams.
CREATE TABLE food_portions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    food_id bigint NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
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
-- Anything that writes foods or sources must refresh both views afterwards.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE MATERIALIZED VIEW food_search_terms AS
WITH titles AS (
    SELECT id AS food_id, lower(name) AS title FROM foods
    UNION SELECT id, lower(unnest(aliases)) FROM foods
    UNION SELECT id, lower(brand) FROM foods WHERE brand IS NOT NULL
    UNION SELECT id, lower(barcode) FROM foods WHERE barcode IS NOT NULL
    UNION SELECT food_id, lower(food_name) FROM food_sources
    UNION SELECT food_id, lower(external_id) FROM food_sources WHERE external_id IS NOT NULL
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

CREATE INDEX food_search_terms_word_idx ON food_search_terms (word);
CREATE INDEX food_search_terms_food_id_idx ON food_search_terms (food_id);

CREATE MATERIALIZED VIEW food_search_vocabulary AS
SELECT DISTINCT word FROM food_search_terms;

CREATE UNIQUE INDEX food_search_vocabulary_word_idx ON food_search_vocabulary (word);
CREATE INDEX food_search_vocabulary_trgm_idx ON food_search_vocabulary USING gin (word gin_trgm_ops);
