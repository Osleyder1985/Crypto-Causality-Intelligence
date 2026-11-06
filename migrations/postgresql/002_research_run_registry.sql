-- CCI research run registry. Apply 001_research_experiments.sql first for a clean installation.
BEGIN;

CREATE TABLE IF NOT EXISTS cci.research_experiment_runs (
    id UUID PRIMARY KEY,
    experiment_id UUID NOT NULL REFERENCES cci.research_experiments(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    run_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued','running','succeeded','failed','cancelled')),
    code_commit TEXT NOT NULL CHECK (length(code_commit) BETWEEN 7 AND 128),
    protocol_version TEXT NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(parameters) = 'object'),
    input_manifest JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(input_manifest) = 'object'),
    metrics JSONB NULL CHECK (metrics IS NULL OR jsonb_typeof(metrics) = 'object'),
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    error_code TEXT NULL,
    error_summary TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (experiment_id, run_key),
    CHECK (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at),
    CHECK ((status IN ('succeeded','failed','cancelled')) = (finished_at IS NOT NULL)),
    CHECK (status <> 'running' OR started_at IS NOT NULL),
    CHECK (status <> 'failed' OR error_summary IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS research_experiment_runs_experiment_created_idx
    ON cci.research_experiment_runs (experiment_id, created_at DESC);
CREATE INDEX IF NOT EXISTS research_experiment_runs_status_created_idx
    ON cci.research_experiment_runs (status, created_at DESC);

CREATE TABLE IF NOT EXISTS cci.research_run_artifacts (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES cci.research_experiment_runs(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    artifact_role TEXT NOT NULL CHECK (artifact_role IN ('input_manifest','summary','metrics','report','dataset','log','other')),
    logical_uri TEXT NOT NULL CHECK (length(logical_uri) > 0),
    media_type TEXT NOT NULL,
    format TEXT NOT NULL CHECK (format IN ('json','csv','parquet','text','other')),
    sha256 TEXT NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    byte_size BIGINT NOT NULL CHECK (byte_size >= 0),
    schema_version TEXT NULL,
    retention_class TEXT NOT NULL CHECK (retention_class IN ('ephemeral','research','restricted','do_not_retain')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, artifact_role, logical_uri, sha256)
);
CREATE INDEX IF NOT EXISTS research_run_artifacts_run_idx
    ON cci.research_run_artifacts (run_id, created_at);

CREATE OR REPLACE FUNCTION cci.enforce_research_run_transition()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status NOT IN ('queued','running') THEN
            RAISE EXCEPTION 'new research run must start queued or running';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status IN ('succeeded','failed','cancelled') THEN
        RAISE EXCEPTION 'terminal research run is immutable';
    END IF;
    IF NEW.id <> OLD.id OR NEW.experiment_id <> OLD.experiment_id OR
       NEW.run_key <> OLD.run_key OR NEW.code_commit <> OLD.code_commit OR
       NEW.protocol_version <> OLD.protocol_version OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'research run identity fields are immutable';
    END IF;
    IF NOT (
        (OLD.status = 'queued' AND NEW.status IN ('queued','running','cancelled')) OR
        (OLD.status = 'running' AND NEW.status IN ('running','succeeded','failed','cancelled'))
    ) THEN
        RAISE EXCEPTION 'invalid research run transition: % -> %', OLD.status, NEW.status;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS research_run_transition_guard ON cci.research_experiment_runs;
CREATE TRIGGER research_run_transition_guard
BEFORE INSERT OR UPDATE ON cci.research_experiment_runs
FOR EACH ROW EXECUTE FUNCTION cci.enforce_research_run_transition();

COMMIT;
