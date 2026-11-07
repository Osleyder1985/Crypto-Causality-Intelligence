-- CCI global schema migration 006
-- Scope: append-only asset identity reviews and accepted asset/representation identifiers.
-- Requires migrations 001 through 005. Synthetic fixtures only.

BEGIN;

CREATE TABLE cci.asset_identity_resolution_reviews (
    id UUID PRIMARY KEY,
    namespace TEXT NOT NULL,
    network_id UUID,
    external_identifier TEXT NOT NULL
        CHECK (btrim(external_identifier) <> ''),
    candidate_asset_id UUID,
    candidate_asset_representation_id UUID,
    resolution_status TEXT NOT NULL
        CHECK (resolution_status IN ('pending_review', 'accepted', 'rejected', 'ambiguous')),
    evidence_reference TEXT,
    decision_reference TEXT,
    observed_at TIMESTAMPTZ NOT NULL,
    reviewed_at TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    supersedes_review_id UUID,
    CONSTRAINT asset_identity_resolution_reviews_fk_namespace
        FOREIGN KEY (namespace)
        REFERENCES cci.identity_namespaces(namespace_key)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT asset_identity_resolution_reviews_fk_network
        FOREIGN KEY (network_id)
        REFERENCES cci.networks(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT asset_identity_resolution_reviews_fk_candidate_asset
        FOREIGN KEY (candidate_asset_id)
        REFERENCES cci.assets(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT asset_identity_resolution_reviews_fk_candidate_representation
        FOREIGN KEY (candidate_asset_representation_id)
        REFERENCES cci.asset_representations(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT asset_identity_resolution_reviews_fk_successor
        FOREIGN KEY (supersedes_review_id)
        REFERENCES cci.asset_identity_resolution_reviews(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT asset_identity_resolution_reviews_ck_single_candidate
        CHECK (
            candidate_asset_id IS NULL
            OR candidate_asset_representation_id IS NULL
        ),
    CONSTRAINT asset_identity_resolution_reviews_ck_accepted
        CHECK (
            resolution_status <> 'accepted'
            OR (
                (candidate_asset_id IS NOT NULL)
                <> (candidate_asset_representation_id IS NOT NULL)
                AND evidence_reference IS NOT NULL
                AND btrim(evidence_reference) <> ''
                AND reviewed_at IS NOT NULL
                AND valid_from IS NOT NULL
            )
        ),
    CONSTRAINT asset_identity_resolution_reviews_ck_validity
        CHECK (
            valid_until IS NULL
            OR (valid_from IS NOT NULL AND valid_until > valid_from)
        ),
    CONSTRAINT asset_identity_resolution_reviews_uq_asset_target
        UNIQUE (
            id, candidate_asset_id, resolution_status, namespace, external_identifier
        ),
    CONSTRAINT asset_identity_resolution_reviews_uq_representation_target
        UNIQUE (
            id, candidate_asset_representation_id, resolution_status,
            namespace, external_identifier, network_id
        )
);

CREATE INDEX asset_identity_resolution_reviews_ix_identity_recorded
    ON cci.asset_identity_resolution_reviews
        (namespace, network_id, external_identifier, recorded_at DESC);

CREATE INDEX asset_identity_resolution_reviews_ix_candidate_asset
    ON cci.asset_identity_resolution_reviews (candidate_asset_id)
    WHERE candidate_asset_id IS NOT NULL;

CREATE INDEX asset_identity_resolution_reviews_ix_candidate_representation
    ON cci.asset_identity_resolution_reviews (candidate_asset_representation_id)
    WHERE candidate_asset_representation_id IS NOT NULL;

CREATE UNIQUE INDEX asset_identity_resolution_reviews_uq_root
    ON cci.asset_identity_resolution_reviews
        (namespace, network_id, external_identifier) NULLS NOT DISTINCT
    WHERE supersedes_review_id IS NULL;

CREATE UNIQUE INDEX asset_identity_resolution_reviews_uq_successor
    ON cci.asset_identity_resolution_reviews (supersedes_review_id)
    WHERE supersedes_review_id IS NOT NULL;

CREATE FUNCTION cci.guard_asset_identity_resolution_review()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = cci, pg_temp
AS $$
DECLARE
    v_scope_mode TEXT;
    v_target_level TEXT;
    v_locked_namespace TEXT;
    v_head_id UUID;
    v_head_valid_from TIMESTAMPTZ;
    v_representation_network_id UUID;
BEGIN
    SELECT scope_mode, target_level, namespace_key
      INTO v_scope_mode, v_target_level, v_locked_namespace
    FROM cci.identity_namespaces
    WHERE namespace_key = NEW.namespace
    FOR UPDATE;

    IF v_locked_namespace IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = '23503',
            MESSAGE = 'identity namespace does not exist';
    END IF;

    IF (v_scope_mode = 'global' AND NEW.network_id IS NOT NULL)
       OR (v_scope_mode = 'network' AND NEW.network_id IS NULL) THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'identity review network scope does not match namespace scope_mode';
    END IF;

    IF (v_target_level = 'asset' AND NEW.candidate_asset_representation_id IS NOT NULL)
       OR (v_target_level = 'representation' AND NEW.candidate_asset_id IS NOT NULL) THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'identity review candidate does not match namespace target_level';
    END IF;

    IF NEW.candidate_asset_representation_id IS NOT NULL THEN
        SELECT network_id INTO v_representation_network_id
        FROM cci.asset_representations
        WHERE id = NEW.candidate_asset_representation_id;

        IF v_representation_network_id IS NULL
           OR NEW.network_id IS DISTINCT FROM v_representation_network_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'representation candidate network must equal identity review network';
        END IF;
    END IF;

    SELECT r.id, r.valid_from
      INTO v_head_id, v_head_valid_from
    FROM cci.asset_identity_resolution_reviews AS r
    WHERE r.namespace = NEW.namespace
      AND r.network_id IS NOT DISTINCT FROM NEW.network_id
      AND r.external_identifier = NEW.external_identifier
      AND NOT EXISTS (
          SELECT 1
          FROM cci.asset_identity_resolution_reviews AS successor
          WHERE successor.supersedes_review_id = r.id
      )
    FOR UPDATE;

    IF v_head_id IS NULL THEN
        IF NEW.supersedes_review_id IS NOT NULL THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'first identity review must be the root of its key chain';
        END IF;
    ELSE
        IF NEW.supersedes_review_id IS DISTINCT FROM v_head_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'identity review must supersede the current chain head';
        END IF;
        IF NEW.valid_from IS NOT NULL
           AND v_head_valid_from IS NOT NULL
           AND NEW.valid_from < v_head_valid_from THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'identity review valid_from cannot precede its predecessor';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_asset_identity_resolution_review_guard
BEFORE INSERT ON cci.asset_identity_resolution_reviews
FOR EACH ROW EXECUTE FUNCTION cci.guard_asset_identity_resolution_review();

CREATE TRIGGER trg_asset_identity_resolution_reviews_immutable
BEFORE UPDATE OR DELETE ON cci.asset_identity_resolution_reviews
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

CREATE TABLE cci.asset_identifiers (
    id UUID PRIMARY KEY,
    asset_id UUID NOT NULL,
    namespace TEXT NOT NULL,
    external_identifier TEXT NOT NULL
        CHECK (btrim(external_identifier) <> ''),
    network_id UUID,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    evidence_reference TEXT NOT NULL
        CHECK (btrim(evidence_reference) <> ''),
    resolution_review_id UUID NOT NULL,
    resolution_status TEXT NOT NULL DEFAULT 'accepted'
        CHECK (resolution_status = 'accepted'),
    CONSTRAINT asset_identifiers_fk_asset
        FOREIGN KEY (asset_id)
        REFERENCES cci.assets(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT asset_identifiers_fk_network
        FOREIGN KEY (network_id)
        REFERENCES cci.networks(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT asset_identifiers_fk_accepted_review
        FOREIGN KEY (
            resolution_review_id, asset_id, resolution_status, namespace, external_identifier
        )
        REFERENCES cci.asset_identity_resolution_reviews (
            id, candidate_asset_id, resolution_status, namespace, external_identifier
        )
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT asset_identifiers_ck_validity
        CHECK (valid_until IS NULL OR valid_until > valid_from)
);

CREATE INDEX asset_identifiers_ix_namespace_identifier
    ON cci.asset_identifiers (namespace, external_identifier);

CREATE FUNCTION cci.validate_asset_identifier_review_scope()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = cci, pg_temp
AS $$
DECLARE
    v_review_network_id UUID;
BEGIN
    SELECT network_id INTO v_review_network_id
    FROM cci.asset_identity_resolution_reviews
    WHERE id = NEW.resolution_review_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '23503',
            MESSAGE = 'asset identifier resolution review does not exist';
    END IF;

    IF NEW.network_id IS DISTINCT FROM v_review_network_id THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'asset identifier network scope must equal resolution review scope';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_asset_identifier_review_scope
BEFORE INSERT ON cci.asset_identifiers
FOR EACH ROW EXECUTE FUNCTION cci.validate_asset_identifier_review_scope();

CREATE TRIGGER trg_asset_identifiers_immutable
BEFORE UPDATE OR DELETE ON cci.asset_identifiers
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

CREATE TABLE cci.asset_representation_identifiers (
    id UUID PRIMARY KEY,
    asset_representation_id UUID NOT NULL,
    network_id UUID NOT NULL,
    namespace TEXT NOT NULL,
    external_identifier TEXT NOT NULL
        CHECK (btrim(external_identifier) <> ''),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    evidence_reference TEXT NOT NULL
        CHECK (btrim(evidence_reference) <> ''),
    resolution_review_id UUID NOT NULL,
    resolution_status TEXT NOT NULL DEFAULT 'accepted'
        CHECK (resolution_status = 'accepted'),
    CONSTRAINT asset_representation_identifiers_fk_representation_network
        FOREIGN KEY (asset_representation_id, network_id)
        REFERENCES cci.asset_representations(id, network_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT asset_representation_identifiers_fk_accepted_review
        FOREIGN KEY (
            resolution_review_id, asset_representation_id, resolution_status,
            namespace, external_identifier, network_id
        )
        REFERENCES cci.asset_identity_resolution_reviews (
            id, candidate_asset_representation_id, resolution_status,
            namespace, external_identifier, network_id
        )
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT asset_representation_identifiers_ck_validity
        CHECK (valid_until IS NULL OR valid_until > valid_from)
);

CREATE INDEX asset_representation_identifiers_ix_namespace_identifier
    ON cci.asset_representation_identifiers (namespace, external_identifier);

CREATE TRIGGER trg_asset_representation_identifiers_immutable
BEFORE UPDATE OR DELETE ON cci.asset_representation_identifiers
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

INSERT INTO cci.schema_migrations (version, description)
VALUES ('006_asset_identity_resolution', 'Create append-only asset identity reviews and accepted identifier mappings');

COMMIT;
