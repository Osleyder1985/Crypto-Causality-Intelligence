-- Research experiment foundation for the run registry.
-- This is intentionally scoped to research_experiments, not the full CCI schema.
BEGIN;

CREATE SCHEMA IF NOT EXISTS cci;

CREATE TABLE IF NOT EXISTS cci.research_experiments (
    id UUID PRIMARY KEY,
    experiment_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    methodology_version TEXT NULL,
    status TEXT NOT NULL CHECK (status IN ('planned','running','completed','inconclusive','rejected')),
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    code_version TEXT NULL,
    protocol JSONB NOT NULL DEFAULT '{}'::jsonb,
    conclusion_summary TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at)
);

COMMIT;
