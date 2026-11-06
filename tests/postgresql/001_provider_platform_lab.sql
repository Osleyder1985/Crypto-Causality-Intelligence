-- CCI PostgreSQL laboratory DDL
-- Scope: provider-platform identity, temporal reviews and published network identifiers.
-- Disposable test schema only. This is NOT a production migration.
BEGIN;

CREATE SCHEMA IF NOT EXISTS cci_lab;
SET LOCAL search_path TO cci_lab, public;

CREATE TABLE data_sources (
    id UUID PRIMARY KEY,
    source_key TEXT NOT NULL UNIQUE
);

CREATE TABLE networks (
    id UUID PRIMARY KEY,
    network_key TEXT NOT NULL UNIQUE
);

CREATE TABLE provider_platforms (
    id UUID PRIMARY KEY,
    data_source_id UUID NOT NULL REFERENCES data_sources(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    provider_platform_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT provider_platforms_uq_source_key
        UNIQUE (data_source_id, provider_platform_key),
    CONSTRAINT provider_platforms_uq_id_source
        UNIQUE (id, data_source_id),
    CONSTRAINT provider_platforms_uq_id_source_key
        UNIQUE (id, data_source_id, provider_platform_key)
);

CREATE TABLE provider_platform_observations (
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
    evidence_reference TEXT NOT NULL,
    evidence_sha256 TEXT,
    CONSTRAINT provider_platform_observations_fk_platform_source
        FOREIGN KEY (provider_platform_id, data_source_id)
        REFERENCES provider_platforms(id, data_source_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT provider_platform_observations_ck_chain_identifier_json
        CHECK (jsonb_typeof(reported_chain_identifier_json) IN ('number', 'null')),
    CONSTRAINT provider_platform_observations_uq_capture
        UNIQUE (provider_platform_id, capture_id),
    CONSTRAINT provider_platform_observations_uq_id_platform_source
        UNIQUE (id, provider_platform_id, data_source_id)
);

CREATE TABLE provider_platform_resolution_reviews (
    id UUID PRIMARY KEY,
    provider_platform_id UUID NOT NULL,
    data_source_id UUID NOT NULL,
    based_on_observation_id UUID,
    candidate_network_id UUID REFERENCES networks(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    resolution_status TEXT NOT NULL,
    evidence_reference TEXT,
    decision_reference TEXT,
    reviewed_at TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ,
    supersedes_review_id UUID,
    CONSTRAINT provider_platform_resolution_reviews_fk_platform_source
        FOREIGN KEY (provider_platform_id, data_source_id)
        REFERENCES provider_platforms(id, data_source_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT provider_platform_resolution_reviews_fk_observation
        FOREIGN KEY (based_on_observation_id, provider_platform_id, data_source_id)
        REFERENCES provider_platform_observations(id, provider_platform_id, data_source_id)
        MATCH SIMPLE ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT provider_platform_resolution_reviews_fk_successor_chain
        FOREIGN KEY (supersedes_review_id, provider_platform_id)
        REFERENCES provider_platform_resolution_reviews(id, provider_platform_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT provider_platform_resolution_reviews_ck_status
        CHECK (resolution_status IN ('pending_review', 'accepted', 'rejected', 'ambiguous')),
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

CREATE UNIQUE INDEX provider_platform_reviews_uq_root
    ON provider_platform_resolution_reviews (provider_platform_id)
    WHERE supersedes_review_id IS NULL;

CREATE UNIQUE INDEX provider_platform_reviews_uq_successor
    ON provider_platform_resolution_reviews (supersedes_review_id)
    WHERE supersedes_review_id IS NOT NULL;

CREATE INDEX provider_platform_reviews_ix_platform_recorded
    ON provider_platform_resolution_reviews (provider_platform_id, recorded_at DESC);

CREATE TABLE network_identifiers (
    id UUID PRIMARY KEY,
    network_id UUID NOT NULL REFERENCES networks(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    namespace TEXT NOT NULL,
    identifier_type TEXT NOT NULL,
    identifier_value TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    evidence_reference TEXT NOT NULL,
    provider_platform_id UUID,
    provider_data_source_id UUID,
    provider_platform_resolution_review_id UUID,
    provider_platform_resolution_status TEXT,
    CONSTRAINT network_identifiers_fk_platform_source
        FOREIGN KEY (provider_platform_id, provider_data_source_id)
        REFERENCES provider_platforms(id, data_source_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT network_identifiers_fk_accepted_review
        FOREIGN KEY (
            provider_platform_resolution_review_id,
            provider_platform_id,
            network_id,
            provider_platform_resolution_status
        )
        REFERENCES provider_platform_resolution_reviews (
            id, provider_platform_id, candidate_network_id, resolution_status
        )
        MATCH SIMPLE ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT network_identifiers_ck_provenance
        CHECK (
            (
                provider_platform_id IS NULL
                AND provider_data_source_id IS NULL
                AND provider_platform_resolution_review_id IS NULL
                AND provider_platform_resolution_status IS NULL
            )
            OR
            (
                provider_platform_id IS NOT NULL
                AND provider_data_source_id IS NOT NULL
                AND provider_platform_resolution_review_id IS NOT NULL
                AND provider_platform_resolution_status IS NOT NULL
                AND provider_platform_resolution_status = 'accepted'
                AND identifier_type = 'asset_platform_id'
            )
        ),
    CONSTRAINT network_identifiers_uq_review
        UNIQUE (provider_platform_resolution_review_id)
);

CREATE INDEX network_identifiers_ix_network
    ON network_identifiers (network_id);

CREATE FUNCTION reject_immutable_row_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION USING
        ERRCODE = '55000',
        MESSAGE = format('%I is append-only; %s is not permitted', TG_TABLE_NAME, TG_OP);
END;
$$;

CREATE TRIGGER trg_provider_platform_observations_immutable
BEFORE UPDATE OR DELETE ON provider_platform_observations
FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_change();

CREATE TRIGGER trg_provider_platform_reviews_immutable
BEFORE UPDATE OR DELETE ON provider_platform_resolution_reviews
FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_change();

CREATE FUNCTION guard_provider_platform_review_chain()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = cci_lab, pg_temp
AS $$
DECLARE
    v_locked_id UUID;
    v_head_id UUID;
    v_previous_valid_from TIMESTAMPTZ;
BEGIN
    SELECT id INTO v_locked_id
    FROM provider_platforms
    WHERE id = NEW.provider_platform_id
      AND data_source_id = NEW.data_source_id
    FOR UPDATE;

    IF v_locked_id IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = '23503',
            MESSAGE = 'provider platform/source pair does not exist';
    END IF;

    SELECT r.id, r.valid_from
      INTO v_head_id, v_previous_valid_from
    FROM provider_platform_resolution_reviews AS r
    WHERE r.provider_platform_id = NEW.provider_platform_id
      AND NOT EXISTS (
          SELECT 1
          FROM provider_platform_resolution_reviews AS successor
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
BEFORE INSERT ON provider_platform_resolution_reviews
FOR EACH ROW EXECUTE FUNCTION guard_provider_platform_review_chain();

CREATE FUNCTION guard_network_identifier_platform_mapping()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = cci_lab, pg_temp
AS $$
DECLARE
    v_platform_key TEXT;
    v_source_key TEXT;
BEGIN
    IF NEW.provider_platform_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT p.provider_platform_key, ds.source_key
      INTO v_platform_key, v_source_key
    FROM provider_platforms AS p
    JOIN data_sources AS ds ON ds.id = p.data_source_id
    WHERE p.id = NEW.provider_platform_id
      AND p.data_source_id = NEW.provider_data_source_id
    FOR UPDATE OF p;

    IF v_platform_key IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = '23503',
            MESSAGE = 'provider platform/source pair does not exist';
    END IF;

    IF NEW.identifier_value IS DISTINCT FROM v_platform_key THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'mapping identifier_value must equal provider_platform_key';
    END IF;

    IF NEW.namespace IS DISTINCT FROM v_source_key || ':asset_platform_id' THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'mapping namespace must be source_key:asset_platform_id';
    END IF;

    IF NEW.identifier_type <> 'asset_platform_id'
       OR NEW.provider_platform_resolution_status <> 'accepted' THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'provider platform mapping must use accepted asset_platform_id';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM provider_platform_resolution_reviews AS successor
        WHERE successor.supersedes_review_id = NEW.provider_platform_resolution_review_id
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'mapping review is not the current chain head';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_network_identifier_platform_guard
BEFORE INSERT ON network_identifiers
FOR EACH ROW EXECUTE FUNCTION guard_network_identifier_platform_mapping();

CREATE VIEW provider_platform_resolution_current AS
SELECT
    r.provider_platform_id,
    r.data_source_id,
    r.id AS resolution_review_id,
    r.candidate_network_id AS network_id,
    r.resolution_status,
    r.valid_from,
    r.valid_until,
    LEAST(
        COALESCE(r.valid_until, 'infinity'::timestamptz),
        COALESCE(s.valid_from, 'infinity'::timestamptz)
    ) AS effective_valid_until
FROM provider_platform_resolution_reviews AS r
LEFT JOIN provider_platform_resolution_reviews AS s
  ON s.supersedes_review_id = r.id
WHERE r.valid_from <= statement_timestamp()
  AND statement_timestamp() < LEAST(
        COALESCE(r.valid_until, 'infinity'::timestamptz),
        COALESCE(s.valid_from, 'infinity'::timestamptz)
      );

CREATE VIEW provider_platform_mappings_current AS
SELECT
    m.id AS network_identifier_id,
    m.network_id,
    m.namespace,
    m.identifier_type,
    m.identifier_value,
    m.provider_platform_id,
    m.provider_data_source_id,
    m.provider_platform_resolution_review_id AS resolution_review_id
FROM network_identifiers AS m
JOIN provider_platform_resolution_current AS r
  ON r.resolution_review_id = m.provider_platform_resolution_review_id
 AND r.provider_platform_id = m.provider_platform_id
 AND r.data_source_id = m.provider_data_source_id
 AND r.network_id = m.network_id
WHERE r.resolution_status = 'accepted'
  AND m.provider_platform_resolution_status = 'accepted';


CREATE FUNCTION provider_platform_resolution_as_known(
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
SET search_path = cci_lab, pg_temp
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
    FROM provider_platform_resolution_reviews AS r
    LEFT JOIN provider_platform_resolution_reviews AS s
      ON s.supersedes_review_id = r.id
     AND s.recorded_at <= p_known_at
    WHERE r.recorded_at <= p_known_at
      AND r.valid_from <= p_valid_at
      AND p_valid_at < LEAST(
            COALESCE(r.valid_until, 'infinity'::timestamptz),
            COALESCE(s.valid_from, 'infinity'::timestamptz)
          );
$cci_resolution$;

COMMIT;
