-- Consumption log: what was eaten, when, and how much.
--
-- Nutrition is never entered: every value is a catalog source's value times an
-- amount. An entry without items is logged but has unknown nutrition.

CREATE SCHEMA log;

CREATE TABLE log.entries (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    eaten_at timestamptz NOT NULL,
    -- The original words, e.g. "the big Döner from the place near work".
    observation text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    -- Deleted entries stay for history but no longer count.
    deleted_at timestamptz
);

CREATE INDEX entries_eaten_at_idx ON log.entries (eaten_at) WHERE deleted_at IS NULL;

-- One component of an entry: a catalog source and the amount eaten. A range
-- (amount_min < amount_max) marks an estimate; equal values an exact amount.
CREATE TABLE log.entry_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entry_id bigint NOT NULL REFERENCES log.entries(id),
    -- A food that was eaten cannot be deleted from the catalog.
    source_id bigint NOT NULL REFERENCES food_sources(id) ON DELETE RESTRICT,
    -- What the component stands for, e.g. "Fladenbrot", as described.
    label text,
    -- In the source's reference unit (g or ml).
    amount_min numeric NOT NULL CHECK (amount_min > 0),
    amount_max numeric NOT NULL CHECK (amount_max >= amount_min),
    unit text NOT NULL,
    -- Set when the amount came from a portion, e.g. 1 × "Becher".
    portion_name text,
    portion_count numeric,
    -- The source's reference quantity and nutrition when logged, so later
    -- catalog changes do not rewrite history.
    reference_quantity numeric NOT NULL,
    nutrition jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    -- Corrections replace items; the old ones stay, marked superseded.
    superseded_at timestamptz
);

CREATE INDEX entry_items_entry_id_idx ON log.entry_items (entry_id) WHERE superseded_at IS NULL;
CREATE INDEX entry_items_source_id_idx ON log.entry_items (source_id);
