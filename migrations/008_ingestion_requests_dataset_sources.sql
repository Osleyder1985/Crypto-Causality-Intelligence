-- CCI global schema migration 008
-- Scope: ingestion requests, run/dataset associations and policy-bound dataset provenance.
-- Requires migrations 001 through 007. No response bodies, secrets or provider OHLCV are stored.

BEGIN;

CREATE TABLE cci.ingestion_requests (
    id UUID PRIMARY KEY,
    ingestion_run_id UUID NOT NULL,
    data_source_id UUID NOT NULL,
    data_endpoint_id UUID NOT NULL,
    market_instrument_id UUID,
    attempt_number INTEGER NOT NULL
        CHECK (attempt_number > 0),
    requested_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    http_status SMALLINT,
    response_status TEXT NOT NULL
        CHECK (response_status IN (
            'succeeded', 'rate_limited', 'rejected',
            'timeout', 'network_error', 'invalid_response'
        )),
    request_parameters JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(request_parameters) = 'object'),
    response_headers_safe JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(response_headers_safe) = 'object'),
    response_hash TEXT,
    records_received BIGINT,
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ingestion_requests_fk_run
        FOREIGN KEY (ingestion_run_id)
        REFERENCES cci.ingestion_runs(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT ingestion_requests_fk_source
        FOREIGN KEY (data_source_id)
        REFERENCES cci.data_sources(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT ingestion_requests_fk_endpoint_source
        FOREIGN KEY (data_endpoint_id, data_source_id)
        REFERENCES cci.data_endpoints(id, data_source_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT ingestion_requests_fk_instrument_source
        FOREIGN KEY (market_instrument_id, data_source_id)
        REFERENCES cci.market_instruments(id, data_source_id)
        MATCH SIMPLE ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT ingestion_requests_uq_id_source_endpoint
        UNIQUE (id, data_source_id, data_endpoint_id),
    CONSTRAINT ingestion_requests_ck_completed_after_requested
        CHECK (completed_at IS NULL OR completed_at >= requested_at),
    CONSTRAINT ingestion_requests_ck_http_status
        CHECK (http_status IS NULL OR http_status BETWEEN 100 AND 599),
    CONSTRAINT ingestion_requests_ck_records_received
        CHECK (records_received IS NULL OR records_received >= 0)
);

CREATE INDEX ingestion_requests_ix_run_requested
    ON cci.ingestion_requests (ingestion_run_id, requested_at);

CREATE INDEX ingestion_requests_ix_endpoint_requested
    ON cci.ingestion_requests (data_endpoint_id, requested_at DESC);

CREATE INDEX ingestion_requests_ix_instrument
    ON cci.ingestion_requests (market_instrument_id)
    WHERE market_instrument_id IS NOT NULL;

CREATE TABLE cci.run_datasets (
    ingestion_run_id UUID NOT NULL,
    dataset_id UUID NOT NULL,
    dataset_role TEXT NOT NULL
        CHECK (dataset_role IN (
            'source_capture', 'normalized', 'validation_report',
            'derived', 'analytical_result'
        )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT run_datasets_pk
        PRIMARY KEY (ingestion_run_id, dataset_id, dataset_role),
    CONSTRAINT run_datasets_fk_run
        FOREIGN KEY (ingestion_run_id)
        REFERENCES cci.ingestion_runs(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT run_datasets_fk_dataset
        FOREIGN KEY (dataset_id)
        REFERENCES cci.datasets(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE INDEX run_datasets_ix_dataset
    ON cci.run_datasets (dataset_id);

CREATE TABLE cci.dataset_sources (
    id UUID PRIMARY KEY,
    dataset_id UUID NOT NULL,
    data_source_id UUID NOT NULL,
    data_endpoint_id UUID NOT NULL,
    data_type TEXT NOT NULL
        CHECK (btrim(data_type) <> ''),
    market_instrument_id UUID,
    ingestion_request_id UUID,
    policy_evaluation_id UUID NOT NULL,
    evaluated_intended_use TEXT NOT NULL
        CHECK (evaluated_intended_use IN (
            'private_research', 'public_display', 'redistribution',
            'commercial_use', 'internal_testing', 'other'
        )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT dataset_sources_fk_dataset
        FOREIGN KEY (dataset_id)
        REFERENCES cci.datasets(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT dataset_sources_fk_source
        FOREIGN KEY (data_source_id)
        REFERENCES cci.data_sources(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT dataset_sources_fk_endpoint_source
        FOREIGN KEY (data_endpoint_id, data_source_id)
        REFERENCES cci.data_endpoints(id, data_source_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT dataset_sources_fk_instrument_source
        FOREIGN KEY (market_instrument_id, data_source_id)
        REFERENCES cci.market_instruments(id, data_source_id)
        MATCH SIMPLE ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT dataset_sources_fk_ingestion_request_provenance
        FOREIGN KEY (ingestion_request_id, data_source_id, data_endpoint_id)
        REFERENCES cci.ingestion_requests(id, data_source_id, data_endpoint_id)
        MATCH SIMPLE ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT dataset_sources_fk_policy_evaluation_scope
        FOREIGN KEY (
            policy_evaluation_id, data_source_id, data_endpoint_id,
            data_type, evaluated_intended_use
        )
        REFERENCES cci.policy_evaluations (
            id, data_source_id, data_endpoint_id, data_type, intended_use
        )
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE INDEX dataset_sources_ix_dataset
    ON cci.dataset_sources (dataset_id);

CREATE INDEX dataset_sources_ix_source_created
    ON cci.dataset_sources (data_source_id, created_at DESC);

CREATE INDEX dataset_sources_ix_policy_evaluation
    ON cci.dataset_sources (policy_evaluation_id);

CREATE TRIGGER trg_dataset_sources_immutable
BEFORE UPDATE OR DELETE ON cci.dataset_sources
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

INSERT INTO cci.schema_migrations (version, description)
VALUES ('008_ingestion_requests_dataset_sources', 'Create ingestion requests, run dataset links and policy-bound dataset provenance');

COMMIT;
