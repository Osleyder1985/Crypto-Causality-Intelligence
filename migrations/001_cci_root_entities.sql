-- CCI global schema migration 001
-- Scope: eight independent root entities plus migration ledger.
-- This is the first versioned migration for schema cci; it is not the full 34-table model.
-- No market OHLCV facts, provider credentials, or real provider data are stored here.

BEGIN;

CREATE SCHEMA cci;

CREATE TABLE cci.schema_migrations (
    version TEXT PRIMARY KEY
        CHECK (version ~ '^[0-9]{3}_[a-z0-9_]+$'),
    description TEXT NOT NULL
        CHECK (btrim(description) <> ''),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE cci.data_sources (
    id UUID PRIMARY KEY,
    source_key TEXT NOT NULL UNIQUE
        CHECK (btrim(source_key) <> ''),
    display_name TEXT NOT NULL
        CHECK (btrim(display_name) <> ''),
    source_type TEXT NOT NULL
        CHECK (source_type IN (
            'exchange', 'aggregator', 'on_chain', 'news',
            'calendar', 'synthetic', 'internal', 'other'
        )),
    documentation_url TEXT,
    status TEXT NOT NULL
        CHECK (status IN ('active', 'paused', 'deprecated')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cci.assets (
    id UUID PRIMARY KEY,
    canonical_code TEXT NOT NULL UNIQUE
        CHECK (btrim(canonical_code) <> ''),
    display_name TEXT NOT NULL
        CHECK (btrim(display_name) <> ''),
    asset_type TEXT NOT NULL
        CHECK (asset_type IN (
            'crypto', 'fiat', 'stablecoin', 'tokenized_asset', 'other'
        )),
    issuer_key TEXT,
    issuer_name TEXT,
    external_identifiers JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(external_identifiers) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cci.identity_namespaces (
    namespace_key TEXT PRIMARY KEY
        CHECK (btrim(namespace_key) <> ''),
    scope_mode TEXT NOT NULL
        CHECK (scope_mode IN ('global', 'network')),
    target_level TEXT NOT NULL
        CHECK (target_level IN ('asset', 'representation', 'both')),
    description TEXT NOT NULL
        CHECK (btrim(description) <> ''),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cci.networks (
    id UUID PRIMARY KEY,
    network_key TEXT NOT NULL UNIQUE
        CHECK (btrim(network_key) <> ''),
    display_name TEXT NOT NULL
        CHECK (btrim(display_name) <> ''),
    network_family TEXT NOT NULL
        CHECK (network_family IN ('bitcoin', 'evm', 'solana', 'other')),
    environment TEXT NOT NULL
        CHECK (environment IN ('mainnet', 'testnet', 'devnet', 'other')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cci.ingestion_runs (
    id UUID PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE
        CHECK (btrim(run_key) <> ''),
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL
        CHECK (status IN ('queued', 'running', 'succeeded', 'partial', 'failed', 'cancelled')),
    code_version TEXT,
    protocol_version TEXT,
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(configuration) = 'object'),
    trigger_type TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ingestion_runs_ck_finished_after_started
        CHECK (finished_at IS NULL OR finished_at >= started_at),
    CONSTRAINT ingestion_runs_ck_terminal_finish
        CHECK (
            (status IN ('succeeded', 'partial', 'failed', 'cancelled') AND finished_at IS NOT NULL)
            OR
            (status IN ('queued', 'running') AND finished_at IS NULL)
        )
);

CREATE TABLE cci.datasets (
    id UUID PRIMARY KEY,
    dataset_key TEXT NOT NULL
        CHECK (btrim(dataset_key) <> ''),
    version INTEGER NOT NULL
        CHECK (version > 0),
    stage TEXT NOT NULL
        CHECK (stage IN (
            'source_capture', 'normalized', 'derived',
            'analytical_result', 'validation_report'
        )),
    data_format TEXT NOT NULL
        CHECK (data_format IN ('parquet', 'json', 'csv', 'other')),
    schema_name TEXT NOT NULL
        CHECK (btrim(schema_name) <> ''),
    schema_version TEXT NOT NULL
        CHECK (btrim(schema_version) <> ''),
    storage_uri TEXT NOT NULL
        CHECK (btrim(storage_uri) <> ''),
    checksum_sha256 TEXT NOT NULL
        CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    file_size_bytes BIGINT,
    record_count BIGINT,
    time_start TIMESTAMPTZ,
    time_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retention_status TEXT NOT NULL
        CHECK (retention_status IN (
            'active', 'pending_review', 'expired', 'deletion_pending', 'deleted'
        )),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT datasets_uq_key_version UNIQUE (dataset_key, version),
    CONSTRAINT datasets_ck_nonnegative_size
        CHECK (file_size_bytes IS NULL OR file_size_bytes >= 0),
    CONSTRAINT datasets_ck_nonnegative_record_count
        CHECK (record_count IS NULL OR record_count >= 0),
    CONSTRAINT datasets_ck_time_range
        CHECK (time_end IS NULL OR time_start IS NULL OR time_end >= time_start)
);

CREATE TABLE cci.transformations (
    id UUID PRIMARY KEY,
    transformation_key TEXT NOT NULL
        CHECK (btrim(transformation_key) <> ''),
    version TEXT NOT NULL
        CHECK (btrim(version) <> ''),
    description TEXT NOT NULL
        CHECK (btrim(description) <> ''),
    code_reference TEXT,
    parameters_schema JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(parameters_schema) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT transformations_uq_key_version
        UNIQUE (transformation_key, version)
);

CREATE TABLE cci.research_experiments (
    id UUID PRIMARY KEY,
    experiment_key TEXT NOT NULL UNIQUE
        CHECK (btrim(experiment_key) <> ''),
    title TEXT NOT NULL
        CHECK (btrim(title) <> ''),
    objective TEXT NOT NULL
        CHECK (btrim(objective) <> ''),
    methodology_version TEXT,
    status TEXT NOT NULL
        CHECK (status IN ('planned', 'running', 'completed', 'inconclusive', 'rejected')),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    code_version TEXT,
    protocol JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(protocol) = 'object'),
    conclusion_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT research_experiments_ck_finished_after_started
        CHECK (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at)
);

INSERT INTO cci.schema_migrations (version, description)
VALUES ('001_cci_root_entities', 'Create CCI schema and eight independent root entities');

COMMIT;
