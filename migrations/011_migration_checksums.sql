-- CCI global schema migration 011
-- Scope: migration ledger checksum and applying-role metadata.
-- The migration runner backfills SHA-256 values from the pinned manifest after this DDL commits.

BEGIN;

ALTER TABLE cci.schema_migrations
    ADD COLUMN checksum_sha256 TEXT
        CHECK (checksum_sha256 IS NULL OR checksum_sha256 ~ '^[0-9a-f]{64}$');

ALTER TABLE cci.schema_migrations
    ADD COLUMN applied_by TEXT NOT NULL DEFAULT session_user
        CHECK (btrim(applied_by) <> '');

INSERT INTO cci.schema_migrations (version, description)
VALUES ('011_migration_checksums', 'Add migration checksum and applying-role metadata to the schema ledger');

COMMIT;
