BEGIN;

CREATE SCHEMA IF NOT EXISTS cci;

CREATE TABLE IF NOT EXISTS cci.schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS cci.source_permissions (
    provider TEXT NOT NULL,
    market_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    storage_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    retention_until TIMESTAMPTZ,
    evidence_ref TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (provider, market_type, symbol),
    CHECK (length(btrim(provider)) > 0),
    CHECK (length(btrim(symbol)) > 0),
    CHECK (length(btrim(evidence_ref)) > 0),
    CHECK (NOT storage_allowed OR retention_until IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS cci.ingestion_runs (
    run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    market_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    row_count INTEGER NOT NULL CHECK (row_count > 0),
    payload_sha256 CHAR(64) NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    actor TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (run_id, provider, market_type, symbol, interval)
);

CREATE TABLE IF NOT EXISTS cci.market_candles (
    provider TEXT NOT NULL,
    market_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    open_time_ms BIGINT NOT NULL CHECK (open_time_ms >= 0),
    open_time_utc TIMESTAMPTZ NOT NULL,
    open NUMERIC(38,18) NOT NULL CHECK (open > 0),
    high NUMERIC(38,18) NOT NULL CHECK (high > 0),
    low NUMERIC(38,18) NOT NULL CHECK (low > 0),
    close NUMERIC(38,18) NOT NULL CHECK (close > 0),
    volume_base NUMERIC(38,18) NOT NULL CHECK (volume_base >= 0),
    quote_volume NUMERIC(38,18) NOT NULL CHECK (quote_volume >= 0),
    close_time_ms BIGINT NOT NULL CHECK (close_time_ms >= open_time_ms),
    trade_count BIGINT NOT NULL CHECK (trade_count >= 0),
    taker_buy_base_volume NUMERIC(38,18) NOT NULL CHECK (taker_buy_base_volume >= 0),
    taker_buy_quote_volume NUMERIC(38,18) NOT NULL CHECK (taker_buy_quote_volume >= 0),
    source_ignore_field TEXT NOT NULL,
    ingestion_run_id BIGINT NOT NULL REFERENCES cci.ingestion_runs(run_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (provider, market_type, symbol, interval, open_time_ms),
    CHECK (low <= open AND open <= high AND low <= close AND close <= high),
    CHECK (taker_buy_base_volume <= volume_base),
    CHECK (taker_buy_quote_volume <= quote_volume),
    CHECK (open_time_utc = to_timestamp(open_time_ms / 1000.0))
);

CREATE TABLE IF NOT EXISTS cci.audit_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    actor TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    payload JSONB NOT NULL,
    payload_sha256 CHAR(64) NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    correlation_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS market_candles_time_idx
    ON cci.market_candles (symbol, interval, open_time_ms);
CREATE INDEX IF NOT EXISTS audit_events_entity_idx
    ON cci.audit_events (entity_type, entity_key, occurred_at);
CREATE INDEX IF NOT EXISTS ingestion_runs_created_idx
    ON cci.ingestion_runs (created_at);

CREATE OR REPLACE FUNCTION cci.reject_audit_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'cci.audit_events is append-only';
END;
$$;

DROP TRIGGER IF EXISTS audit_events_no_update ON cci.audit_events;
CREATE TRIGGER audit_events_no_update
BEFORE UPDATE OR DELETE ON cci.audit_events
FOR EACH ROW EXECUTE FUNCTION cci.reject_audit_mutation();

INSERT INTO cci.schema_migrations(version)
VALUES ('001_transactional_market_storage')
ON CONFLICT (version) DO NOTHING;

COMMIT;
