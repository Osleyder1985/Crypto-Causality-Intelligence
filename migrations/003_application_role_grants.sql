BEGIN;

GRANT USAGE ON SCHEMA cci TO cci_app;
GRANT SELECT ON cci.source_permissions TO cci_app;
GRANT UPDATE (updated_at) ON cci.source_permissions TO cci_app;
GRANT SELECT, INSERT ON cci.ingestion_runs, cci.market_candles, cci.audit_events TO cci_app;
GRANT USAGE, SELECT ON SEQUENCE cci.ingestion_runs_run_id_seq TO cci_app;
GRANT USAGE, SELECT ON SEQUENCE cci.audit_events_event_id_seq TO cci_app;
REVOKE UPDATE, DELETE, TRUNCATE ON cci.audit_events FROM cci_app;

GRANT USAGE ON SCHEMA cci TO cci_retention;
GRANT SELECT ON cci.source_permissions TO cci_retention;
GRANT UPDATE (updated_at) ON cci.source_permissions TO cci_retention;
GRANT DELETE ON cci.market_candles TO cci_retention;
GRANT INSERT ON cci.audit_events TO cci_retention;
GRANT USAGE, SELECT ON SEQUENCE cci.audit_events_event_id_seq TO cci_retention;
REVOKE UPDATE, DELETE, TRUNCATE ON cci.audit_events FROM cci_retention;

INSERT INTO cci.schema_migrations(version)
VALUES ('003_application_role_grants')
ON CONFLICT (version) DO NOTHING;

COMMIT;
