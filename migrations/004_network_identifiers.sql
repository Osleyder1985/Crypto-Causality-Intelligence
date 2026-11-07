-- CCI global schema migration 004
-- Scope: network identifiers and atomic guard for accepted provider-platform mappings.
-- Requires migrations 001, 002 and 003. Synthetic fixtures only.

BEGIN;

CREATE TABLE cci.network_identifiers (
    id UUID PRIMARY KEY,
    network_id UUID NOT NULL,
    namespace TEXT NOT NULL
        CHECK (btrim(namespace) <> ''),
    identifier_type TEXT NOT NULL
        CHECK (btrim(identifier_type) <> ''),
    identifier_value TEXT NOT NULL
        CHECK (btrim(identifier_value) <> ''),
    observed_at TIMESTAMPTZ NOT NULL,
    evidence_reference TEXT NOT NULL
        CHECK (btrim(evidence_reference) <> ''),
    provider_platform_id UUID,
    provider_data_source_id UUID,
    provider_platform_resolution_review_id UUID,
    provider_platform_resolution_status TEXT,
    CONSTRAINT network_identifiers_fk_network
        FOREIGN KEY (network_id)
        REFERENCES cci.networks(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT network_identifiers_fk_platform_source
        FOREIGN KEY (provider_platform_id, provider_data_source_id)
        REFERENCES cci.provider_platforms(id, data_source_id)
        MATCH SIMPLE ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT network_identifiers_fk_accepted_review
        FOREIGN KEY (
            provider_platform_resolution_review_id,
            provider_platform_id,
            network_id,
            provider_platform_resolution_status
        )
        REFERENCES cci.provider_platform_resolution_reviews (
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
                AND provider_platform_resolution_status = 'accepted'
                AND identifier_type = 'asset_platform_id'
            )
        )
);

CREATE UNIQUE INDEX network_identifiers_uq_review
    ON cci.network_identifiers (provider_platform_resolution_review_id)
    WHERE provider_platform_resolution_review_id IS NOT NULL;

CREATE INDEX network_identifiers_ix_network_type
    ON cci.network_identifiers (network_id, identifier_type);

CREATE FUNCTION cci.guard_network_identifier_platform_mapping()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = cci, pg_temp
AS $$
DECLARE
    v_platform_key TEXT;
    v_source_key TEXT;
BEGIN
    IF NEW.provider_platform_id IS NULL
       AND NEW.provider_data_source_id IS NULL
       AND NEW.provider_platform_resolution_review_id IS NULL
       AND NEW.provider_platform_resolution_status IS NULL THEN
        RETURN NEW;
    END IF;

    IF NEW.provider_platform_id IS NULL
       OR NEW.provider_data_source_id IS NULL
       OR NEW.provider_platform_resolution_review_id IS NULL
       OR NEW.provider_platform_resolution_status IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'provider platform provenance must be all NULL or all complete';
    END IF;

    SELECT p.provider_platform_key, ds.source_key
      INTO v_platform_key, v_source_key
    FROM cci.provider_platforms AS p
    JOIN cci.data_sources AS ds ON ds.id = p.data_source_id
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
        FROM cci.provider_platform_resolution_reviews AS successor
        WHERE successor.supersedes_review_id = NEW.provider_platform_resolution_review_id
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'mapping review is not the current chain head';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_network_identifier_platform_guard
BEFORE INSERT ON cci.network_identifiers
FOR EACH ROW EXECUTE FUNCTION cci.guard_network_identifier_platform_mapping();

CREATE TRIGGER trg_network_identifiers_immutable
BEFORE UPDATE OR DELETE ON cci.network_identifiers
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

CREATE VIEW cci.provider_platform_mappings_current AS
SELECT
    m.provider_platform_id,
    m.provider_data_source_id AS data_source_id,
    m.network_id,
    m.namespace,
    m.identifier_type,
    m.identifier_value,
    m.provider_platform_resolution_review_id AS resolution_review_id
FROM cci.network_identifiers AS m
JOIN cci.provider_platform_resolution_current AS r
  ON r.resolution_review_id = m.provider_platform_resolution_review_id
 AND r.provider_platform_id = m.provider_platform_id
 AND r.data_source_id = m.provider_data_source_id
 AND r.network_id = m.network_id
WHERE r.resolution_status = 'accepted'
  AND m.provider_platform_resolution_status = 'accepted';

INSERT INTO cci.schema_migrations (version, description)
VALUES ('004_network_identifiers', 'Create network identifiers and accepted provider-platform mapping guard');

COMMIT;
