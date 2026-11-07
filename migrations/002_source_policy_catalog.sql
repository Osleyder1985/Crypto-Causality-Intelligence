-- CCI global schema migration 002
-- Scope: source endpoints, usage policies and concrete policy evaluations.
-- Requires 001_cci_root_entities.sql. Synthetic fixtures only.

BEGIN;

CREATE TABLE cci.data_endpoints (
    id UUID PRIMARY KEY,
    data_source_id UUID NOT NULL,
    endpoint_key TEXT NOT NULL
        CHECK (btrim(endpoint_key) <> ''),
    base_url TEXT,
    resource_path TEXT,
    data_type TEXT NOT NULL
        CHECK (btrim(data_type) <> ''),
    documentation_url TEXT,
    status TEXT NOT NULL
        CHECK (status IN ('active', 'paused', 'deprecated')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT data_endpoints_fk_data_source
        FOREIGN KEY (data_source_id)
        REFERENCES cci.data_sources(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT data_endpoints_uq_source_endpoint
        UNIQUE (data_source_id, endpoint_key),
    CONSTRAINT data_endpoints_uq_id_source
        UNIQUE (id, data_source_id)
);

CREATE TABLE cci.source_usage_policies (
    id UUID PRIMARY KEY,
    data_source_id UUID NOT NULL,
    data_endpoint_id UUID,
    policy_scope TEXT NOT NULL
        CHECK (policy_scope IN ('provider', 'product', 'endpoint', 'data_type')),
    scope_reference TEXT,
    intended_use TEXT NOT NULL
        CHECK (intended_use IN (
            'private_research', 'public_display', 'redistribution',
            'commercial_use', 'internal_testing', 'other'
        )),
    permission_status TEXT NOT NULL
        CHECK (permission_status IN (
            'allowed', 'restricted', 'denied', 'unknown', 'pending_confirmation'
        )),
    evidence_url TEXT,
    evidence_reference TEXT,
    evidence_sha256 TEXT
        CHECK (evidence_sha256 IS NULL OR evidence_sha256 ~ '^[0-9a-f]{64}$'),
    reviewed_at TIMESTAMPTZ,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ,
    retention_rule TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT source_usage_policies_fk_source
        FOREIGN KEY (data_source_id)
        REFERENCES cci.data_sources(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT source_usage_policies_fk_endpoint_source
        FOREIGN KEY (data_endpoint_id, data_source_id)
        REFERENCES cci.data_endpoints(id, data_source_id)
        MATCH SIMPLE ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT source_usage_policies_uq_id_source
        UNIQUE (id, data_source_id),
    CONSTRAINT source_usage_policies_ck_validity
        CHECK (valid_until IS NULL OR valid_until > valid_from),
    CONSTRAINT source_usage_policies_ck_scope
        CHECK (
            (
                policy_scope = 'endpoint'
                AND data_endpoint_id IS NOT NULL
                AND scope_reference IS NULL
            )
            OR
            (
                policy_scope IN ('product', 'data_type')
                AND scope_reference IS NOT NULL
                AND btrim(scope_reference) <> ''
            )
            OR
            (
                policy_scope = 'provider'
                AND data_endpoint_id IS NULL
                AND scope_reference IS NULL
            )
        )
);

CREATE TABLE cci.policy_evaluations (
    id UUID PRIMARY KEY,
    source_usage_policy_id UUID NOT NULL,
    data_source_id UUID NOT NULL,
    data_endpoint_id UUID NOT NULL,
    data_type TEXT NOT NULL
        CHECK (btrim(data_type) <> ''),
    intended_use TEXT NOT NULL
        CHECK (intended_use IN (
            'private_research', 'public_display', 'redistribution',
            'commercial_use', 'internal_testing', 'other'
        )),
    permission_status TEXT NOT NULL
        CHECK (permission_status IN (
            'allowed', 'restricted', 'denied', 'unknown', 'pending_confirmation'
        )),
    evaluated_at TIMESTAMPTZ NOT NULL,
    policy_valid_from_snapshot TIMESTAMPTZ NOT NULL,
    policy_valid_until_snapshot TIMESTAMPTZ,
    evidence_sha256 TEXT
        CHECK (evidence_sha256 IS NULL OR evidence_sha256 ~ '^[0-9a-f]{64}$'),
    decision_reference TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT policy_evaluations_fk_policy_source
        FOREIGN KEY (source_usage_policy_id, data_source_id)
        REFERENCES cci.source_usage_policies(id, data_source_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT policy_evaluations_fk_endpoint_source
        FOREIGN KEY (data_endpoint_id, data_source_id)
        REFERENCES cci.data_endpoints(id, data_source_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT policy_evaluations_uq_provenance
        UNIQUE (id, data_source_id, data_endpoint_id, data_type, intended_use),
    CONSTRAINT policy_evaluations_ck_snapshot_validity
        CHECK (
            policy_valid_until_snapshot IS NULL
            OR policy_valid_until_snapshot > policy_valid_from_snapshot
        )
);

CREATE INDEX source_usage_policies_ix_source_valid_from
    ON cci.source_usage_policies (data_source_id, valid_from DESC);

CREATE INDEX source_usage_policies_ix_endpoint_valid_from
    ON cci.source_usage_policies (data_endpoint_id, valid_from DESC)
    WHERE data_endpoint_id IS NOT NULL;

CREATE INDEX policy_evaluations_ix_scope_time
    ON cci.policy_evaluations (
        data_source_id, data_endpoint_id, data_type, intended_use, evaluated_at DESC
    );

CREATE INDEX policy_evaluations_ix_policy_source
    ON cci.policy_evaluations (source_usage_policy_id, data_source_id);

CREATE INDEX policy_evaluations_ix_endpoint_source
    ON cci.policy_evaluations (data_endpoint_id, data_source_id);

INSERT INTO cci.schema_migrations (version, description)
VALUES ('002_source_policy_catalog', 'Create endpoints, source usage policies and policy evaluations');

COMMIT;
