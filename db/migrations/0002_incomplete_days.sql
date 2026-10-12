-- Days the person marked as incomplete: some meals of the day are missing, so its
-- totals are lower than what was eaten. Stats leave these days out; the day stays
-- visible. One row per local day.
CREATE TABLE log.incomplete_days (
    day date PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now()
);
