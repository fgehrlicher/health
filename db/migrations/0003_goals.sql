-- The person's goals. One row: a daily kcal limit that colors the days on the stats
-- calendar. Days within the limit (or below it) and days above it look different.
CREATE TABLE log.goals (
    id smallint PRIMARY KEY CHECK (id = 1),
    daily_kcal_limit integer NOT NULL CHECK (daily_kcal_limit BETWEEN 1 AND 10000),
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO log.goals (id, daily_kcal_limit) VALUES (1, 2000);
