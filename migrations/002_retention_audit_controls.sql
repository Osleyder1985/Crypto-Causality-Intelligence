BEGIN;

-- Keep audit records immutable for ordinary application roles.
REVOKE UPDATE, DELETE, TRUNCATE ON cci.audit_events FROM PUBLIC;

INSERT INTO cci.schema_migrations(version)
VALUES ('002_retention_audit_controls')
ON CONFLICT (version) DO NOTHING;

COMMIT;
