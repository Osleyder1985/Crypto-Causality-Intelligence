-- CCI global schema migration 007
-- Scope: source-specific market instruments, aliases, metadata versions and trading rules.
-- Requires migrations 001 through 006. Symbols are not canonical asset identities.

BEGIN;

CREATE TABLE cci.market_instruments (
    id UUID PRIMARY KEY,
    data_source_id UUID NOT NULL,
    source_instrument_id TEXT,
    native_symbol TEXT NOT NULL
        CHECK (btrim(native_symbol) <> ''),
    native_base_asset_code TEXT NOT NULL
        CHECK (btrim(native_base_asset_code) <> ''),
    native_quote_asset_code TEXT NOT NULL
        CHECK (btrim(native_quote_asset_code) <> ''),
    base_asset_id UUID,
    quote_asset_id UUID,
    canonical_symbol TEXT,
    market_type TEXT NOT NULL
        CHECK (market_type IN ('spot', 'perpetual', 'future', 'option', 'other')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT market_instruments_fk_source
        FOREIGN KEY (data_source_id)
        REFERENCES cci.data_sources(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT market_instruments_fk_base_asset
        FOREIGN KEY (base_asset_id)
        REFERENCES cci.assets(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT market_instruments_fk_quote_asset
        FOREIGN KEY (quote_asset_id)
        REFERENCES cci.assets(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT market_instruments_uq_id_source
        UNIQUE (id, data_source_id),
    CONSTRAINT market_instruments_ck_asset_pair
        CHECK (
            (base_asset_id IS NULL AND quote_asset_id IS NULL)
            OR
            (
                base_asset_id IS NOT NULL
                AND quote_asset_id IS NOT NULL
                AND base_asset_id <> quote_asset_id
            )
        )
);

CREATE INDEX market_instruments_ix_source
    ON cci.market_instruments (data_source_id);

CREATE INDEX market_instruments_ix_native_symbol
    ON cci.market_instruments (native_symbol);

CREATE TABLE cci.instrument_identifiers (
    id UUID PRIMARY KEY,
    market_instrument_id UUID NOT NULL,
    identifier_namespace TEXT NOT NULL
        CHECK (btrim(identifier_namespace) <> ''),
    identifier_value TEXT NOT NULL
        CHECK (btrim(identifier_value) <> ''),
    is_primary BOOLEAN NOT NULL DEFAULT false,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT instrument_identifiers_fk_market_instrument
        FOREIGN KEY (market_instrument_id)
        REFERENCES cci.market_instruments(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT instrument_identifiers_ck_validity
        CHECK (
            valid_until IS NULL
            OR valid_from IS NULL
            OR valid_until > valid_from
        )
);

CREATE INDEX instrument_identifiers_ix_namespace_value
    ON cci.instrument_identifiers (identifier_namespace, identifier_value);

CREATE INDEX instrument_identifiers_ix_instrument_observed
    ON cci.instrument_identifiers (market_instrument_id, observed_at DESC);

CREATE TABLE cci.instrument_metadata_versions (
    id UUID PRIMARY KEY,
    market_instrument_id UUID NOT NULL,
    source_dataset_id UUID,
    observed_at TIMESTAMPTZ NOT NULL,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    source_status TEXT NOT NULL
        CHECK (btrim(source_status) <> ''),
    normalized_status TEXT,
    price_precision INTEGER,
    quantity_precision INTEGER,
    pair_decimals INTEGER,
    lot_decimals INTEGER,
    provider_metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(provider_metadata) = 'object'),
    mapping_version TEXT NOT NULL
        CHECK (btrim(mapping_version) <> ''),
    schema_version TEXT NOT NULL
        CHECK (btrim(schema_version) <> ''),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT instrument_metadata_versions_fk_market_instrument
        FOREIGN KEY (market_instrument_id)
        REFERENCES cci.market_instruments(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT instrument_metadata_versions_fk_source_dataset
        FOREIGN KEY (source_dataset_id)
        REFERENCES cci.datasets(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT instrument_metadata_versions_ck_validity
        CHECK (
            valid_until IS NULL
            OR valid_from IS NULL
            OR valid_until > valid_from
        ),
    CONSTRAINT instrument_metadata_versions_ck_nonnegative_precision
        CHECK (
            (price_precision IS NULL OR price_precision >= 0)
            AND (quantity_precision IS NULL OR quantity_precision >= 0)
            AND (pair_decimals IS NULL OR pair_decimals >= 0)
            AND (lot_decimals IS NULL OR lot_decimals >= 0)
        )
);

CREATE INDEX instrument_metadata_versions_ix_instrument_observed
    ON cci.instrument_metadata_versions (market_instrument_id, observed_at DESC);

CREATE TABLE cci.instrument_trading_rules (
    id UUID PRIMARY KEY,
    metadata_version_id UUID NOT NULL,
    rule_namespace TEXT NOT NULL
        CHECK (btrim(rule_namespace) <> ''),
    rule_scope TEXT NOT NULL
        CHECK (rule_scope IN (
            'price', 'limit_quantity', 'market_quantity', 'notional',
            'order', 'asset', 'exchange', 'other'
        )),
    parameters JSONB NOT NULL
        CHECK (jsonb_typeof(parameters) = 'object'),
    applicability JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(applicability) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT instrument_trading_rules_fk_metadata_version
        FOREIGN KEY (metadata_version_id)
        REFERENCES cci.instrument_metadata_versions(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT instrument_trading_rules_uq_version_namespace_scope
        UNIQUE (metadata_version_id, rule_namespace, rule_scope)
);

CREATE INDEX instrument_trading_rules_ix_metadata_version
    ON cci.instrument_trading_rules (metadata_version_id);

CREATE TRIGGER trg_instrument_identifiers_immutable
BEFORE UPDATE OR DELETE ON cci.instrument_identifiers
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

CREATE TRIGGER trg_instrument_metadata_versions_immutable
BEFORE UPDATE OR DELETE ON cci.instrument_metadata_versions
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

CREATE TRIGGER trg_instrument_trading_rules_immutable
BEFORE UPDATE OR DELETE ON cci.instrument_trading_rules
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

INSERT INTO cci.schema_migrations (version, description)
VALUES ('007_market_instrument_catalog', 'Create source-specific market instruments, aliases, metadata versions and trading rules');

COMMIT;
