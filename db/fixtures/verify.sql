DO $$
DECLARE
    food_count integer;
    source_count integer;
    representative_count integer;
BEGIN
    SELECT count(*) INTO food_count FROM foods;
    SELECT count(*) INTO source_count FROM food_sources WHERE source_name = 'BLS 4.0';
    SELECT count(*) INTO representative_count
    FROM food_sources AS source
    JOIN foods AS food ON food.id = source.food_id
    WHERE source.source_name = 'BLS 4.0'
      AND source.reference_quantity = 100 AND source.reference_unit = 'g'
      AND (
          (food.slug = 'apple-raw' AND source.external_id = 'F110100'
              AND source.energy_kcal = 58 AND source.protein_g = 0.424
              AND source.fat_g = 0.5 AND source.carbs_g = 11.7 AND source.fiber_g = 2.275)
          OR (food.slug = 'white-rice-raw' AND source.external_id = 'C352000'
              AND source.energy_kcal = 351 AND source.protein_g = 7.931
              AND source.fat_g = 0.62 AND source.carbs_g = 77.1 AND source.fiber_g = 2.5)
          OR (food.slug = 'lentil-mature-dry' AND source.external_id = 'H725100'
              AND source.energy_kcal = 323 AND source.protein_g = 23.357
              AND source.fat_g = 1.7 AND source.carbs_g = 44.8 AND source.fiber_g = 17.6)
      );
    IF food_count < 3 OR source_count < 3 OR representative_count <> 3 THEN
        RAISE EXCEPTION 'fixture incomplete: foods=%, sources=%, representative=%',
            food_count, source_count, representative_count;
    END IF;
    RAISE NOTICE 'schema verified: foods=% sources=% energy_and_macros=ok',
        food_count, source_count;
END $$;
