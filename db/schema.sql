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

    -- Core nutrition. Units are in the names; NULL means no usable number.
    energy_kcal numeric,
    protein_g numeric,
    fat_g numeric,
    carbs_g numeric,
    fiber_g numeric
);

CREATE INDEX food_sources_food_id_idx ON food_sources (food_id);
