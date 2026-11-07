-- CCI global schema migration 009
-- Scope: dataset lineage/validation, transformation runs and experiment execution artifacts.
-- Requires migrations 001 through 008. No artifact bytes or OHLCV payloads are stored here.

BEGIN;

CREATE TABLE cci.transformation_runs (
    id UUID PRIMARY KEY,
    transformation_id UUID NOT NULL,
    ingestion_run_id UUID,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL
        CHECK (status IN ('queued', 'running', 'succeeded', 'partial', 'failed', 'cancelled')),
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(parameters) = 'object'),
    code_commit TEXT,
    error_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT transformation_runs_fk_transformation
        FOREIGN KEY (transformation_id)
        REFERENCES cci.transformations(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT transformation_runs_fk_ingestion_run
        FOREIGN KEY (ingestion_run_id)
        REFERENCES cci.ingestion_runs(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT transformation_runs_ck_finished_after_started
        CHECK (finished_at IS NULL OR finished_at >= started_at),
    CONSTRAINT transformation_runs_ck_terminal_finish
        CHECK (
            (status IN ('succeeded', 'partial', 'failed', 'cancelled') AND finished_at IS NOT NULL)
            OR (status IN ('queued', 'running') AND finished_at IS NULL)
        )
);

CREATE INDEX transformation_runs_ix_transformation_started
    ON cci.transformation_runs (transformation_id, started_at DESC);

CREATE INDEX transformation_runs_ix_ingestion_run
    ON cci.transformation_runs (ingestion_run_id)
    WHERE ingestion_run_id IS NOT NULL;

CREATE TABLE cci.dataset_lineage (
    input_dataset_id UUID NOT NULL,
    output_dataset_id UUID NOT NULL,
    transformation_run_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT dataset_lineage_pk
        PRIMARY KEY (input_dataset_id, output_dataset_id, transformation_run_id),
    CONSTRAINT dataset_lineage_fk_input_dataset
        FOREIGN KEY (input_dataset_id)
        REFERENCES cci.datasets(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT dataset_lineage_fk_output_dataset
        FOREIGN KEY (output_dataset_id)
        REFERENCES cci.datasets(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT dataset_lineage_fk_transformation_run
        FOREIGN KEY (transformation_run_id)
        REFERENCES cci.transformation_runs(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT dataset_lineage_ck_distinct_datasets
        CHECK (input_dataset_id <> output_dataset_id)
);

CREATE INDEX dataset_lineage_ix_input
    ON cci.dataset_lineage (input_dataset_id);

CREATE INDEX dataset_lineage_ix_output
    ON cci.dataset_lineage (output_dataset_id);

CREATE FUNCTION cci.guard_dataset_lineage_acyclic()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = cci, pg_temp
AS $$
DECLARE
    v_would_cycle BOOLEAN;
BEGIN
    -- Serialize graph-edge publication so two concurrent opposite edges cannot form a cycle.
    PERFORM pg_advisory_xact_lock(73628, 1);

    WITH RECURSIVE reachable(dataset_id) AS (
        SELECT NEW.output_dataset_id
        UNION
        SELECT edge.output_dataset_id
        FROM cci.dataset_lineage AS edge
        JOIN reachable AS r ON edge.input_dataset_id = r.dataset_id
    )
    SELECT EXISTS (
        SELECT 1 FROM reachable WHERE dataset_id = NEW.input_dataset_id
    )
    INTO v_would_cycle;

    IF v_would_cycle THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'dataset lineage edge would create a directed cycle';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_dataset_lineage_acyclic
BEFORE INSERT ON cci.dataset_lineage
FOR EACH ROW EXECUTE FUNCTION cci.guard_dataset_lineage_acyclic();

CREATE TRIGGER trg_dataset_lineage_immutable
BEFORE UPDATE OR DELETE ON cci.dataset_lineage
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

CREATE TABLE cci.data_validations (
    id UUID PRIMARY KEY,
    dataset_id UUID NOT NULL,
    ingestion_run_id UUID,
    validation_suite TEXT NOT NULL
        CHECK (btrim(validation_suite) <> ''),
    validation_version TEXT NOT NULL
        CHECK (btrim(validation_version) <> ''),
    status TEXT NOT NULL
        CHECK (status IN ('passed', 'failed', 'warning', 'skipped')),
    checked_at TIMESTAMPTZ NOT NULL,
    checks_total INTEGER NOT NULL,
    checks_passed INTEGER NOT NULL,
    checks_failed INTEGER NOT NULL,
    report_uri TEXT,
    report_hash TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(details) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT data_validations_fk_dataset
        FOREIGN KEY (dataset_id)
        REFERENCES cci.datasets(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT data_validations_fk_ingestion_run
        FOREIGN KEY (ingestion_run_id)
        REFERENCES cci.ingestion_runs(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT data_validations_ck_nonnegative_counts
        CHECK (checks_total >= 0 AND checks_passed >= 0 AND checks_failed >= 0),
    CONSTRAINT data_validations_ck_counts_within_total
        CHECK (checks_passed + checks_failed <= checks_total)
);

CREATE INDEX data_validations_ix_dataset_checked
    ON cci.data_validations (dataset_id, checked_at DESC);

CREATE TRIGGER trg_data_validations_immutable
BEFORE UPDATE OR DELETE ON cci.data_validations
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

CREATE TABLE cci.research_experiment_runs (
    id UUID PRIMARY KEY,
    experiment_id UUID NOT NULL,
    run_key TEXT NOT NULL
        CHECK (btrim(run_key) <> ''),
    status TEXT NOT NULL
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    code_commit TEXT NOT NULL
        CHECK (btrim(code_commit) <> ''),
    protocol_version TEXT NOT NULL
        CHECK (btrim(protocol_version) <> ''),
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(parameters) = 'object'),
    input_manifest JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(input_manifest) = 'object'),
    metrics JSONB
        CHECK (metrics IS NULL OR jsonb_typeof(metrics) = 'object'),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_code TEXT,
    error_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT research_experiment_runs_fk_experiment
        FOREIGN KEY (experiment_id)
        REFERENCES cci.research_experiments(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT research_experiment_runs_uq_experiment_run_key
        UNIQUE (experiment_id, run_key),
    CONSTRAINT research_experiment_runs_ck_finished_after_started
        CHECK (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at),
    CONSTRAINT research_experiment_runs_ck_terminal_finish
        CHECK (
            (status IN ('succeeded', 'failed', 'cancelled') AND finished_at IS NOT NULL)
            OR (status IN ('queued', 'running') AND finished_at IS NULL)
        ),
    CONSTRAINT research_experiment_runs_ck_running_started
        CHECK (status <> 'running' OR started_at IS NOT NULL),
    CONSTRAINT research_experiment_runs_ck_failed_summary
        CHECK (status <> 'failed' OR (error_summary IS NOT NULL AND btrim(error_summary) <> ''))
);

CREATE FUNCTION cci.guard_research_experiment_run_transition()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = cci, pg_temp
AS $$
BEGIN
    IF OLD.status IN ('succeeded', 'failed', 'cancelled') THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'terminal research experiment runs are immutable';
    END IF;

    IF NEW.experiment_id IS DISTINCT FROM OLD.experiment_id
       OR NEW.run_key IS DISTINCT FROM OLD.run_key
       OR NEW.code_commit IS DISTINCT FROM OLD.code_commit
       OR NEW.protocol_version IS DISTINCT FROM OLD.protocol_version
       OR NEW.parameters IS DISTINCT FROM OLD.parameters
       OR NEW.input_manifest IS DISTINCT FROM OLD.input_manifest THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'research experiment run identity and input manifest are immutable';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'queued' AND NEW.status NOT IN ('running', 'cancelled') THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'invalid research run transition from queued';
        END IF;
        IF OLD.status = 'running' AND NEW.status NOT IN ('succeeded', 'failed', 'cancelled') THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'invalid research run transition from running';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_research_experiment_run_transition
BEFORE UPDATE ON cci.research_experiment_runs
FOR EACH ROW EXECUTE FUNCTION cci.guard_research_experiment_run_transition();

CREATE TABLE cci.research_run_artifacts (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL,
    artifact_role TEXT NOT NULL
        CHECK (artifact_role IN (
            'input_manifest', 'summary', 'metrics', 'report',
            'dataset', 'log', 'other'
        )),
    logical_uri TEXT NOT NULL
        CHECK (btrim(logical_uri) <> ''),
    media_type TEXT NOT NULL
        CHECK (btrim(media_type) <> ''),
    format TEXT NOT NULL
        CHECK (format IN ('json', 'csv', 'parquet', 'text', 'other')),
    sha256 TEXT NOT NULL
        CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    byte_size BIGINT NOT NULL
        CHECK (byte_size >= 0),
    schema_version TEXT,
    retention_class TEXT NOT NULL
        CHECK (retention_class IN ('ephemeral', 'research', 'restricted', 'do_not_retain')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT research_run_artifacts_fk_run
        FOREIGN KEY (run_id)
        REFERENCES cci.research_experiment_runs(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT research_run_artifacts_uq_artifact
        UNIQUE (run_id, artifact_role, logical_uri, sha256)
);

CREATE INDEX research_run_artifacts_ix_run
    ON cci.research_run_artifacts (run_id);

CREATE TRIGGER trg_research_run_artifacts_immutable
BEFORE UPDATE OR DELETE ON cci.research_run_artifacts
FOR EACH ROW EXECUTE FUNCTION cci.reject_immutable_row_change();

CREATE TABLE cci.research_hypotheses (
    id UUID PRIMARY KEY,
    experiment_id UUID NOT NULL,
    hypothesis_key TEXT NOT NULL
        CHECK (btrim(hypothesis_key) <> ''),
    statement TEXT NOT NULL
        CHECK (btrim(statement) <> ''),
    alternative_explanations JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(alternative_explanations) = 'array'),
    falsification_criteria TEXT,
    status TEXT NOT NULL
        CHECK (status IN ('proposed', 'testing', 'supported', 'not_supported', 'inconclusive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT research_hypotheses_fk_experiment
        FOREIGN KEY (experiment_id)
        REFERENCES cci.research_experiments(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT research_hypotheses_uq_experiment_key
        UNIQUE (experiment_id, hypothesis_key)
);

CREATE TABLE cci.experiment_datasets (
    experiment_id UUID NOT NULL,
    dataset_id UUID NOT NULL,
    dataset_role TEXT NOT NULL
        CHECK (dataset_role IN ('input', 'benchmark', 'validation', 'output')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT experiment_datasets_pk
        PRIMARY KEY (experiment_id, dataset_id, dataset_role),
    CONSTRAINT experiment_datasets_fk_experiment
        FOREIGN KEY (experiment_id)
        REFERENCES cci.research_experiments(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT experiment_datasets_fk_dataset
        FOREIGN KEY (dataset_id)
        REFERENCES cci.datasets(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE INDEX experiment_datasets_ix_dataset
    ON cci.experiment_datasets (dataset_id);

INSERT INTO cci.schema_migrations (version, description)
VALUES ('009_lineage_validation_research_runs', 'Create dataset lineage, validations and research execution records');

COMMIT;
