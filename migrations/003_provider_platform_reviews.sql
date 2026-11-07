-- CCI global schema migration 003
-- Scope: provider platform identities, immutable observations and append-only resolution reviews.
-- Requires migrations 001 and 002. Provider mappings are added in a later migration.

BEGIN;

CREATE TABLE cci.provider_platforms (
    id UUID PRIMARY KEY,
    data_source_id UUID NOT NULL,
    provider_platform_key TEXT NOT NULL
        CHECK (btrim(provider_platform_key) <> ''),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT provider_platforms_fk_source
        FOREIGN KEY (data_source_id)
        REFERENCES cci.data_sources(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT provider_platforms_uq_source_key
        UNIQUE (data_source_id, provider_platform_key),
    CONSTRAINT provider_platforms_uq_id_source
        UNIQUE (id, data_source_id),
    CONSTRAINT provider_platforms_uq_id_source_key
        UNIQUE (id, data_source_id, provider_platform_key)
);

CREATE TABLE cci.provider_platform_observations (
    id UUID PRIMARY KEY,
    provider_platform_id UUID NOT NULL,
    data_source_id UUID NOT NULL,
    capture_id UUID NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    provider_name TEXT,
    provider_shortname TEXT,
    provider_native_coin_id TEXT,
    reported_chain_identifier_json JSONB NOT NULL,
    evidence_reference TEXT NOT NULL
        CHECK (btrim(evidence_reference) <> ''),
    evidence_sha256 TEXT
        CHECK (evidence_sha256 IS NULL OR evidence_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT provider_platform_observations_fk_platform_source
        FOREIGN KEY (provider_platform_id, data_source_id)
        REFERENCES cci.provider_platforms(id, data_source_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT provider_platform_observations_ck_chain_identifier_json
        CHECK (jsonb_typeof(reported_chain_identifier_json) IN ('number', 'null')),
    CONSTRAINT provider_platform_observations_uq_capture
        UNIQUE (provider_platform_id, capture_id),
    CONSTRAINT provider_platform_observations_uq_id_platform
        UNIQUE (id, provider_platform_id),
    CONSTRAINT provider_platform_observations_uq_id_platform_source
        UNIQUE (id, provider_platform_id, data_source_id)
);

CREATE INDEX provider_platform_observations_ix_platform_observed_at
    ON cci.provider_platform_observations (provider_platform_id, observed_at DESC);

CREATE TABLE cci.provider_platform_resolution_reviews (
    id UUID PRIMARY KEY,
    provider_platform_id UUID NOT NULL,
    data_source_id UUID NOT NULL,
    based_on_observation_id UUID,
    candidate_network_id UUID,
    resolution_status TEXT NOT NULL
        CHECK (resolution_status IN ('pending_review', 'accepted', 'rejected', 'ambiguous')),
    evidence_reference TEXT,
    decision_reference TEXT,
    reviewed_at TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ,
    supersedes_review_id UUID,
    CONSTRAINT provider_platform_resolution_reviews_fk_platform_source
        FOREIGN KEY (provider_platform_id, data_source_id)
        REFERENCES cci.provider_platforms(id, data_source_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT provider_platform_resolution_reviews_fk_observation
        FOREIGN KEY (based_on_observation_id, provider_platform_id, data_source_id)
        REFERENCES cci.provider_platform_observations(id, provider_platform_id, data_source_id)
        MATCH SIMPLE ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT provider_platform_resolution_reviews_fk_candidate_network
        FOREIGN KEY (candidate_network_id)
        REFERENCES cci.networks(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT provider_platform_resolution_reviews_fk_successor_chain
        FOREIGN KEY (supersedes_review_id, provider_platform_id)
        REFERENCES cci.provider_platform_resolution_reviews(id, provider_platform_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT provider_platform_resolution_reviews_ck_validity
        CHECK (valid_until IS NULL OR valid_until > valid_from),
    CONSTRAINT provider_platform_resolution_reviews_ck_accepted
        CHECK (
            resolution_status <> 'accepted'
            OR (
                candidate_network_id IS NOT NULL
                AND evidence_reference IS NOT NULL
                AND btrim(evidence_reference) <> ''
                AND reviewed_at IS NOT NULL
            )
        ),
    CONSTRAINT provider_platform_resolution_reviews_uq_id_platform
        UNIQUE (id, provider_platform_id),
    CONSTRAINT provider_platform_resolution_reviews_uq_mapping
        UNIQUE (id, provider_platform_id, candidate_network_id, resolution_status)
);

CREATE INDEX provider_platform_resolution_reviews_ix_platform_recorded_at
    ON cci.provider_platform_resolution_reviews (provider_platform_id, recorded_at DESC);

CREATE UNIQUE INDEX provider_platform_reviews_uq_root
    ON cci.provider_platform_resolution_reviews (provider_platform_id)
    WHERE supersedes_review_id IS NULL;

CREATE UNIQUE INDEX provider_platform_reviews_uq_successor
    ON cci.provider_platform_resolution_reviews (supersedes_review_id)
    WHERE supersedes_review_id IS NOT NULL;

CREATE FUNCTION cci.reject_immutable_row_change()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = cci, pg_temp
AS $$
BEGIN
    RAISE EXCEPTION USING
        ERRCODE = '55000',
        MESSAGE = format('%I is append-only; %s is not permitted', TG_TABLE_NAME, TG_OP);
END;
$$;

CREATE TRIGGER trg_provider_platform_observations_immutable
BEFORE UPDATE OR DELETE ON cci.provider_platform_observations
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

CREATE TRIGGER trg_provider_platform_reviews_immutable
BEFORE UPDATE OR DELETE ON cci.provider_platform_resolution_reviews
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

CREATE FUNCTION cci.guard_provider_platform_review_chain()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = cci, pg_temp
AS $$
DECLARE
    v_locked_id UUID;
    v_head_id UUID;
    v_previous_valid_from TIMESTAMPTZ;
BEGIN
    SELECT id INTO v_locked_id
    FROM cci.provider_platforms
    WHERE id = NEW.provider_platform_id
      AND data_source_id = NEW.data_source_id
    FOR UPDATE;

    IF v_locked_id IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = '23503',
            MESSAGE = 'provider platform/source pair does not exist';
    END IF;

    SELECT r.id, r.valid_from
      INTO v_head_id, v_previous_valid_from
    FROM cci.provider_platform_resolution_reviews AS r
    WHERE r.provider_platform_id = NEW.provider_platform_id
      AND NOT EXISTS (
          SELECT 1
          FROM cci.provider_platform_resolution_reviews AS successor
          WHERE successor.supersedes_review_id = r.id
      )
    FOR UPDATE;

    IF v_head_id IS NULL THEN
        IF NEW.supersedes_review_id IS NOT NULL THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'first review must be the root of the chain';
        END IF;
    ELSE
        IF NEW.supersedes_review_id IS DISTINCT FROM v_head_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'new review must supersede the current chain head';
        END IF;
        IF NEW.valid_from < v_previous_valid_from THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'successor valid_from cannot precede predecessor valid_from';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_provider_platform_review_chain_guard
BEFORE INSERT ON cci.provider_platform_resolution_reviews
FOR EACH ROW EXECUTE FUNCTION cci.guard_provider_platform_review_chain();

CREATE VIEW cci.provider_platform_resolution_current AS
SELECT
    r.provider_platform_id,
    r.data_source_id,
    r.id AS resolution_review_id,
    r.candidate_network_id AS network_id,
    r.resolution_status,
    r.valid_from,
    r.valid_until,
    r.recorded_at,
    LEAST(
        COALESCE(r.valid_until, 'infinity'::timestamptz),
        COALESCE(s.valid_from, 'infinity'::timestamptz)
    ) AS effective_valid_until
FROM cci.provider_platform_resolution_reviews AS r
LEFT JOIN cci.provider_platform_resolution_reviews AS s
  ON s.supersedes_review_id = r.id
WHERE r.valid_from <= statement_timestamp()
  AND statement_timestamp() < LEAST(
        COALESCE(r.valid_until, 'infinity'::timestamptz),
        COALESCE(s.valid_from, 'infinity'::timestamptz)
      );

CREATE FUNCTION cci.provider_platform_resolution_as_known(
    p_valid_at TIMESTAMPTZ,
    p_known_at TIMESTAMPTZ
)
RETURNS TABLE (
    provider_platform_id UUID,
    data_source_id UUID,
    resolution_review_id UUID,
    network_id UUID,
    resolution_status TEXT,
    valid_from TIMESTAMPTZ,
    effective_valid_until TIMESTAMPTZ
)
LANGUAGE sql
STABLE
SET search_path = cci, pg_temp
AS $cci_resolution$
    SELECT
        r.provider_platform_id,
        r.data_source_id,
        r.id,
        r.candidate_network_id,
        r.resolution_status,
        r.valid_from,
        LEAST(
            COALESCE(r.valid_until, 'infinity'::timestamptz),
            COALESCE(s.valid_from, 'infinity'::timestamptz)
        )
    FROM cci.provider_platform_resolution_reviews AS r
    LEFT JOIN cci.provider_platform_resolution_reviews AS s
      ON s.supersedes_review_id = r.id
     AND s.recorded_at <= p_known_at
    WHERE r.recorded_at <= p_known_at
      AND r.valid_from <= p_valid_at
      AND p_valid_at < LEAST(
            COALESCE(r.valid_until, 'infinity'::timestamptz),
            COALESCE(s.valid_from, 'infinity'::timestamptz)
          );
$cci_resolution$;

INSERT INTO cci.schema_migrations (version, description)
VALUES ('003_provider_platform_reviews', 'Create provider platform identities, observations and bitemporal resolution reviews');

COMMIT;
