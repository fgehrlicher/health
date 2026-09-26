-- Mutable baseline until the first deployment. Content validation belongs in the importer.

CREATE TABLE foods (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug text NOT NULL UNIQUE,
    name text NOT NULL,
    aliases text[] NOT NULL DEFAULT '{}',
    kind text NOT NULL DEFAULT 'ingredient',
    preparation_state text,
    brand text,
    barcode text,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- One record from BLS, a manual entry, a photographed label, or an estimate.
-- source_name can include a fixed dataset version, e.g. "BLS 4.0".
CREATE TABLE food_sources (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    food_id bigint NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    source_kind text NOT NULL,
    source_name text NOT NULL,
    external_id text,
    food_name text NOT NULL,
    reference_quantity numeric NOT NULL,
    reference_unit text NOT NULL,
    energy_kcal numeric,
    protein_g numeric,
    fat_g numeric,
    carbs_g numeric,
    fiber_g numeric,
    vitamin_b12_ug numeric,
    vitamin_c_mg numeric,
    beta_carotene_ug numeric,
    capture_method text,
    source_url text,
    raw_input text,
    raw_data jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
