-- CCI global schema migration 005
-- Scope: canonical asset representations and evidenced directed asset relationships.
-- Requires migrations 001 through 004. Synthetic fixtures only.

BEGIN;

CREATE TABLE cci.asset_representations (
    id UUID PRIMARY KEY,
    asset_id UUID NOT NULL,
    network_id UUID NOT NULL,
    representation_kind TEXT NOT NULL
        CHECK (representation_kind IN ('native', 'token_contract', 'other')),
    native_asset_key TEXT,
    contract_address TEXT,
    address_normalization TEXT,
    token_standard TEXT,
    decimals INTEGER,
    issuer_key TEXT,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    observed_at TIMESTAMPTZ NOT NULL,
    evidence_reference TEXT NOT NULL
        CHECK (btrim(evidence_reference) <> ''),
    CONSTRAINT asset_representations_fk_asset
        FOREIGN KEY (asset_id)
        REFERENCES cci.assets(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT asset_representations_fk_network
        FOREIGN KEY (network_id)
        REFERENCES cci.networks(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT asset_representations_uq_id_network
        UNIQUE (id, network_id),
    CONSTRAINT asset_representations_ck_kind_fields
        CHECK (
            (
                representation_kind = 'native'
                AND native_asset_key IS NOT NULL
                AND btrim(native_asset_key) <> ''
                AND contract_address IS NULL
            )
            OR
            (
                representation_kind = 'token_contract'
                AND contract_address IS NOT NULL
                AND btrim(contract_address) <> ''
                AND native_asset_key IS NULL
            )
            OR representation_kind = 'other'
        ),
    CONSTRAINT asset_representations_ck_validity
        CHECK (
            valid_until IS NULL
            OR (valid_from IS NOT NULL AND valid_until > valid_from)
        )
);

CREATE INDEX asset_representations_ix_network_kind_contract
    ON cci.asset_representations (network_id, representation_kind, contract_address);

CREATE INDEX asset_representations_ix_asset
    ON cci.asset_representations (asset_id);

CREATE TABLE cci.asset_relationships (
    id UUID PRIMARY KEY,
    subject_asset_id UUID NOT NULL,
    object_asset_id UUID NOT NULL,
    relationship_type TEXT NOT NULL
        CHECK (relationship_type IN (
            'wrapped_representation_of',
            'bridged_representation_of',
            'redeemable_for',
            'backed_by',
            'tracks_price_of',
            'migrated_to'
        )),
    directionality TEXT NOT NULL DEFAULT 'directed'
        CHECK (directionality = 'directed'),
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    evidence_reference TEXT NOT NULL
        CHECK (btrim(evidence_reference) <> ''),
    observed_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT asset_relationships_fk_subject_asset
        FOREIGN KEY (subject_asset_id)
        REFERENCES cci.assets(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT asset_relationships_fk_object_asset
        FOREIGN KEY (object_asset_id)
        REFERENCES cci.assets(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT asset_relationships_ck_distinct_assets
        CHECK (subject_asset_id <> object_asset_id),
    CONSTRAINT asset_relationships_ck_validity
        CHECK (
            valid_until IS NULL
            OR (valid_from IS NOT NULL AND valid_until > valid_from)
        )
);

CREATE INDEX asset_relationships_ix_subject_type
    ON cci.asset_relationships (subject_asset_id, relationship_type);

CREATE INDEX asset_relationships_ix_object
    ON cci.asset_relationships (object_asset_id);

CREATE TRIGGER trg_asset_representations_immutable
BEFORE UPDATE OR DELETE ON cci.asset_representations
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

CREATE TRIGGER trg_asset_relationships_immutable
BEFORE UPDATE OR DELETE ON cci.asset_relationships
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

INSERT INTO cci.schema_migrations (version, description)
VALUES ('005_asset_representations_relationships', 'Create canonical asset representations and evidenced directed relationships');

COMMIT;
