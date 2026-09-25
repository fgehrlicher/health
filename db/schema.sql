CREATE TABLE data_sources (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug text NOT NULL CONSTRAINT data_sources_slug_unique UNIQUE,
    name text NOT NULL,
    kind text NOT NULL,
    homepage_url text,
    license text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT data_sources_slug_format
        CHECK (slug ~ '^[a-z0-9]+([._-][a-z0-9]+)*$'),
    CONSTRAINT data_sources_name_present CHECK (btrim(name) <> ''),
    CONSTRAINT data_sources_kind_valid
        CHECK (kind IN (
            'dataset',
            'package_label',
            'publication',
            'laboratory',
            'user_entry',
            'agent_estimate'
        ))
);

CREATE TABLE source_releases (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data_source_id bigint NOT NULL REFERENCES data_sources(id) ON DELETE RESTRICT,
    version text NOT NULL,
    published_on date,
    retrieved_at timestamptz NOT NULL,
    source_url text,
    citation text,
    sha256 text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT source_releases_source_version_unique
        UNIQUE (data_source_id, version),
    CONSTRAINT source_releases_id_source_unique
        UNIQUE (id, data_source_id),
    CONSTRAINT source_releases_version_present CHECK (btrim(version) <> ''),
    CONSTRAINT source_releases_sha256_valid
        CHECK (sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT source_releases_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE TABLE source_foods (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data_source_id bigint NOT NULL REFERENCES data_sources(id) ON DELETE RESTRICT,
    source_release_id bigint,
    external_id text,
    name text NOT NULL,
    name_en text,
    source_url text,
    observed_at timestamptz,
    raw_input text,
    raw_data jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT source_foods_release_matches_source
        FOREIGN KEY (source_release_id, data_source_id)
        REFERENCES source_releases(id, data_source_id)
        ON DELETE RESTRICT,
    CONSTRAINT source_foods_release_has_external_id
        CHECK (source_release_id IS NULL OR external_id IS NOT NULL),
    CONSTRAINT source_foods_external_id_present
        CHECK (external_id IS NULL OR btrim(external_id) <> ''),
    CONSTRAINT source_foods_name_present CHECK (btrim(name) <> ''),
    CONSTRAINT source_foods_raw_input_present
        CHECK (raw_input IS NULL OR btrim(raw_input) <> ''),
    CONSTRAINT source_foods_raw_data_object CHECK (jsonb_typeof(raw_data) = 'object')
);

CREATE UNIQUE INDEX source_foods_release_external_id_unique
    ON source_foods (source_release_id, external_id)
    WHERE source_release_id IS NOT NULL AND external_id IS NOT NULL;

CREATE UNIQUE INDEX source_foods_unreleased_external_id_unique
    ON source_foods (data_source_id, external_id)
    WHERE source_release_id IS NULL AND external_id IS NOT NULL;

CREATE TABLE foods (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug text NOT NULL CONSTRAINT foods_slug_unique UNIQUE,
    name text NOT NULL,
    kind text NOT NULL DEFAULT 'ingredient',
    preparation_state text,
    brand text,
    barcode text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT foods_slug_format
        CHECK (slug ~ '^[a-z0-9]+([._-][a-z0-9]+)*$'),
    CONSTRAINT foods_name_present CHECK (btrim(name) <> ''),
    CONSTRAINT foods_kind_valid
        CHECK (kind IN ('ingredient', 'branded_product', 'prepared_food')),
    CONSTRAINT foods_preparation_state_present
        CHECK (preparation_state IS NULL OR btrim(preparation_state) <> ''),
    CONSTRAINT foods_barcode_present
        CHECK (barcode IS NULL OR btrim(barcode) <> '')
);

CREATE UNIQUE INDEX foods_barcode_unique
    ON foods (barcode)
    WHERE barcode IS NOT NULL;

CREATE TABLE food_source_mappings (
    food_id bigint NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    source_food_id bigint NOT NULL REFERENCES source_foods(id) ON DELETE RESTRICT,
    relationship text NOT NULL,
    rationale text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (food_id, source_food_id),
    CONSTRAINT food_source_mappings_relationship_valid
        CHECK (relationship IN ('exact', 'equivalent', 'proxy')),
    CONSTRAINT food_source_mappings_proxy_rationale
        CHECK (relationship <> 'proxy' OR nullif(btrim(rationale), '') IS NOT NULL)
);

CREATE TABLE food_aliases (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    food_id bigint NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    name text NOT NULL,
    locale text NOT NULL DEFAULT 'und',
    source_food_id bigint REFERENCES source_foods(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT food_aliases_name_present CHECK (btrim(name) <> ''),
    CONSTRAINT food_aliases_locale_format
        CHECK (locale ~ '^[a-z]{2,3}(-[A-Z]{2})?$')
);

CREATE UNIQUE INDEX food_aliases_identity_unique
    ON food_aliases (food_id, locale, lower(name));

CREATE TABLE measurement_units (
    code text PRIMARY KEY,
    name text NOT NULL,
    symbol text NOT NULL,
    dimension text NOT NULL,
    CONSTRAINT measurement_units_code_format CHECK (code ~ '^[a-z][a-z0-9_]*$'),
    CONSTRAINT measurement_units_name_present CHECK (btrim(name) <> ''),
    CONSTRAINT measurement_units_symbol_present CHECK (btrim(symbol) <> ''),
    CONSTRAINT measurement_units_dimension_valid
        CHECK (dimension IN ('mass', 'energy', 'volume', 'count'))
);

CREATE TABLE nutrients (
    code text PRIMARY KEY,
    name text NOT NULL,
    default_unit_code text NOT NULL REFERENCES measurement_units(code) ON DELETE RESTRICT,
    description text,
    CONSTRAINT nutrients_code_format CHECK (code ~ '^[a-z][a-z0-9_]*$'),
    CONSTRAINT nutrients_name_present CHECK (btrim(name) <> '')
);

CREATE TABLE nutrient_profiles (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_food_id bigint NOT NULL REFERENCES source_foods(id) ON DELETE RESTRICT,
    reference_quantity numeric NOT NULL,
    reference_unit_code text NOT NULL REFERENCES measurement_units(code) ON DELETE RESTRICT,
    acquisition_method text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT nutrient_profiles_source_basis_unique
        UNIQUE (source_food_id, reference_quantity, reference_unit_code),
    CONSTRAINT nutrient_profiles_reference_quantity_positive
        CHECK (reference_quantity > 0),
    CONSTRAINT nutrient_profiles_acquisition_method_valid
        CHECK (acquisition_method IN (
            'bulk_import',
            'api_import',
            'llm_label_extraction',
            'llm_estimation',
            'manual_entry',
            'calculated'
        ))
);

CREATE TABLE nutrient_values (
    nutrient_profile_id bigint NOT NULL REFERENCES nutrient_profiles(id) ON DELETE CASCADE,
    nutrient_code text NOT NULL REFERENCES nutrients(code) ON DELETE RESTRICT,
    source_nutrient_id text,
    source_unit_code text NOT NULL REFERENCES measurement_units(code) ON DELETE RESTRICT,
    source_value text NOT NULL,
    source_provenance text,
    normalized_amount numeric,
    normalized_amount_lower_bound numeric,
    normalized_amount_upper_bound numeric,
    confidence text,
    value_state text NOT NULL,
    derivation_method text NOT NULL,
    normalization_method text NOT NULL DEFAULT 'identity',
    normalization_note text,
    source_reference text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (nutrient_profile_id, nutrient_code),
    CONSTRAINT nutrient_values_amounts_nonnegative
        CHECK (
            (normalized_amount IS NULL OR normalized_amount >= 0)
            AND (
                normalized_amount_lower_bound IS NULL
                OR normalized_amount_lower_bound >= 0
            )
            AND (
                normalized_amount_upper_bound IS NULL
                OR normalized_amount_upper_bound >= 0
            )
        ),
    CONSTRAINT nutrient_values_bounds_complete
        CHECK (
            (normalized_amount_lower_bound IS NULL)
            = (normalized_amount_upper_bound IS NULL)
        ),
    CONSTRAINT nutrient_values_bounds_ordered
        CHECK (
            normalized_amount_lower_bound IS NULL
            OR normalized_amount_lower_bound <= normalized_amount_upper_bound
        ),
    CONSTRAINT nutrient_values_amount_within_bounds
        CHECK (
            normalized_amount_lower_bound IS NULL
            OR normalized_amount IS NULL
            OR normalized_amount BETWEEN
                normalized_amount_lower_bound AND normalized_amount_upper_bound
        ),
    CONSTRAINT nutrient_values_state_valid
        CHECK (value_state IN (
            'reported',
            'trace',
            'below_detection_limit',
            'below_quantification_limit',
            'below_detection_or_quantification_limit',
            'missing'
        )),
    CONSTRAINT nutrient_values_amount_matches_state
        CHECK (
            (value_state = 'reported' AND normalized_amount IS NOT NULL)
            OR (
                value_state <> 'reported'
                AND normalized_amount IS NULL
                AND normalized_amount_lower_bound IS NULL
                AND normalized_amount_upper_bound IS NULL
            )
        ),
    CONSTRAINT nutrient_values_derivation_method_valid
        CHECK (derivation_method IN (
            'analysis',
            'aggregation',
            'formula_calculation',
            'nutrient_database',
            'literature',
            'label',
            'recipe_calculation',
            'pattern_calculation',
            'transferred',
            'rescaled',
            'logical_zero',
            'logical_assumption',
            'trace',
            'estimated',
            'unknown'
        )),
    CONSTRAINT nutrient_values_logical_zero_is_zero
        CHECK (
            derivation_method <> 'logical_zero'
            OR (value_state = 'reported' AND normalized_amount = 0)
        ),
    CONSTRAINT nutrient_values_source_value_present CHECK (btrim(source_value) <> ''),
    CONSTRAINT nutrient_values_source_provenance_present
        CHECK (source_provenance IS NULL OR btrim(source_provenance) <> ''),
    CONSTRAINT nutrient_values_confidence_present
        CHECK (confidence IS NULL OR btrim(confidence) <> ''),
    CONSTRAINT nutrient_values_normalization_method_present
        CHECK (btrim(normalization_method) <> ''),
    CONSTRAINT nutrient_values_normalization_note_present
        CHECK (normalization_note IS NULL OR btrim(normalization_note) <> ''),
    CONSTRAINT nutrient_values_metadata_object CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE VIEW food_nutrient_observations AS
SELECT
    food.id AS food_id,
    food.slug AS food_slug,
    food.name AS food_name,
    food.preparation_state,
    mapping.relationship AS source_relationship,
    mapping.rationale AS source_mapping_rationale,
    source.slug AS source_slug,
    source.kind AS source_kind,
    release.version AS source_version,
    source_food.id AS source_food_record_id,
    source_food.external_id AS source_food_external_id,
    source_food.observed_at,
    profile.reference_quantity,
    profile.reference_unit_code,
    profile.acquisition_method,
    value.nutrient_code,
    value.source_nutrient_id,
    nutrient.name AS nutrient_name,
    value.source_value,
    value.source_unit_code,
    value.source_provenance,
    value.normalized_amount,
    value.normalized_amount_lower_bound,
    value.normalized_amount_upper_bound,
    value.confidence,
    nutrient.default_unit_code AS normalized_unit_code,
    value.value_state,
    value.derivation_method,
    value.normalization_method,
    value.normalization_note,
    value.source_reference
FROM foods AS food
JOIN food_source_mappings AS mapping
    ON mapping.food_id = food.id
JOIN source_foods AS source_food
    ON source_food.id = mapping.source_food_id
JOIN data_sources AS source
    ON source.id = source_food.data_source_id
LEFT JOIN source_releases AS release
    ON release.id = source_food.source_release_id
JOIN nutrient_profiles AS profile
    ON profile.source_food_id = source_food.id
JOIN nutrient_values AS value
    ON value.nutrient_profile_id = profile.id
JOIN nutrients AS nutrient
    ON nutrient.code = value.nutrient_code;

COMMENT ON TABLE source_foods IS
    'Food observations from a dataset, package label, user, publication, laboratory, or agent estimate.';
COMMENT ON TABLE foods IS
    'Canonical food identities used by the application.';
COMMENT ON TABLE food_source_mappings IS
    'Exact, equivalent, or explicit proxy mappings from canonical foods to source records.';
COMMENT ON TABLE nutrient_values IS
    'Nutrient observations preserving source evidence separately from normalized values.';
