-- CCI global schema migration 010
-- Scope: NOLOGIN role groups, object ownership, deny-by-default runtime grants.
-- Requires migrations 001 through 009. No service LOGIN identities or credentials are created.
-- Runtime writes remain denied until domain SECURITY DEFINER functions are implemented and audited.

BEGIN;

DO $cci_roles$
DECLARE
    r RECORD;
    v_can_login BOOLEAN;
    v_inherit BOOLEAN;
    v_superuser BOOLEAN;
    v_createdb BOOLEAN;
    v_createrole BOOLEAN;
    v_replication BOOLEAN;
    v_bypass_rls BOOLEAN;
BEGIN
    FOR r IN
        SELECT role_name, inherit_privileges
        FROM (VALUES
            ('cci_owner', false),
            ('cci_migrator', true),
            ('cci_catalog_writer', true),
            ('cci_policy_admin', true),
            ('cci_policy_evaluator', true),
            ('cci_ingest_writer', true),
            ('cci_identity_resolver', true),
            ('cci_transform_writer', true),
            ('cci_research_writer', true),
            ('cci_reader', true)
        ) AS role_specs(role_name, inherit_privileges)
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r.role_name) THEN
            EXECUTE format(
                'CREATE ROLE %I NOLOGIN %s',
                r.role_name,
                CASE WHEN r.inherit_privileges THEN 'INHERIT' ELSE 'NOINHERIT' END
            );
        ELSE
            SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb,
                   rolcreaterole, rolreplication, rolbypassrls
              INTO v_can_login, v_inherit, v_superuser, v_createdb,
                   v_createrole, v_replication, v_bypass_rls
            FROM pg_roles
            WHERE rolname = r.role_name;

            IF v_can_login
               OR v_inherit IS DISTINCT FROM r.inherit_privileges
               OR v_superuser OR v_createdb OR v_createrole
               OR v_replication OR v_bypass_rls THEN
                RAISE EXCEPTION 'Existing role % has unsafe attributes; refusing to adopt it', r.role_name;
            END IF;
        END IF;
    END LOOP;
END;
$cci_roles$;

GRANT cci_owner TO cci_migrator;

ALTER SCHEMA cci OWNER TO cci_owner;

DO $cci_ownership$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT c.relname, c.relkind
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'cci'
          AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
        ORDER BY c.relkind, c.relname
    LOOP
        IF r.relkind IN ('r', 'p', 'f') THEN
            EXECUTE format('ALTER TABLE cci.%I OWNER TO cci_owner', r.relname);
        ELSIF r.relkind = 'v' THEN
            EXECUTE format('ALTER VIEW cci.%I OWNER TO cci_owner', r.relname);
        ELSIF r.relkind = 'm' THEN
            EXECUTE format('ALTER MATERIALIZED VIEW cci.%I OWNER TO cci_owner', r.relname);
        ELSIF r.relkind = 'S' THEN
            EXECUTE format('ALTER SEQUENCE cci.%I OWNER TO cci_owner', r.relname);
        END IF;
    END LOOP;

    FOR r IN
        SELECT p.proname, pg_get_function_identity_arguments(p.oid) AS identity_args
        FROM pg_proc AS p
        JOIN pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'cci'
        ORDER BY p.proname, identity_args
    LOOP
        EXECUTE format(
            'ALTER FUNCTION cci.%I(%s) OWNER TO cci_owner',
            r.proname,
            r.identity_args
        );
    END LOOP;
END;
$cci_ownership$;

REVOKE ALL ON SCHEMA cci FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA cci FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA cci FROM PUBLIC;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA cci FROM PUBLIC;

ALTER DEFAULT PRIVILEGES FOR ROLE cci_owner IN SCHEMA cci
    REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE cci_owner IN SCHEMA cci
    REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE cci_owner IN SCHEMA cci
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

GRANT USAGE ON SCHEMA cci TO
    cci_catalog_writer,
    cci_policy_admin,
    cci_policy_evaluator,
    cci_ingest_writer,
    cci_identity_resolver,
    cci_transform_writer,
    cci_research_writer,
    cci_reader;

-- Catalog services receive read access only; all writes wait for audited domain functions.
GRANT SELECT ON
    cci.data_sources,
    cci.data_endpoints,
    cci.assets,
    cci.identity_namespaces,
    cci.networks,
    cci.network_identifiers,
    cci.provider_platforms,
    cci.provider_platform_observations,
    cci.provider_platform_resolution_reviews,
    cci.asset_representations,
    cci.asset_relationships,
    cci.asset_identity_resolution_reviews,
    cci.asset_identifiers,
    cci.asset_representation_identifiers,
    cci.market_instruments,
    cci.instrument_identifiers,
    cci.instrument_metadata_versions,
    cci.instrument_trading_rules
TO cci_catalog_writer, cci_identity_resolver;

GRANT SELECT ON
    cci.data_sources,
    cci.data_endpoints,
    cci.source_usage_policies,
    cci.policy_evaluations
TO cci_policy_admin, cci_policy_evaluator;

GRANT SELECT ON
    cci.data_sources,
    cci.data_endpoints,
    cci.source_usage_policies,
    cci.policy_evaluations,
    cci.market_instruments,
    cci.instrument_identifiers,
    cci.instrument_metadata_versions,
    cci.instrument_trading_rules,
    cci.ingestion_runs,
    cci.ingestion_requests,
    cci.datasets,
    cci.run_datasets,
    cci.dataset_sources
TO cci_ingest_writer;

GRANT SELECT ON
    cci.datasets,
    cci.run_datasets,
    cci.dataset_sources,
    cci.dataset_lineage,
    cci.data_validations,
    cci.transformations,
    cci.transformation_runs
TO cci_transform_writer;

GRANT SELECT ON
    cci.research_experiments,
    cci.research_experiment_runs,
    cci.research_run_artifacts,
    cci.research_hypotheses,
    cci.experiment_datasets,
    cci.datasets,
    cci.data_validations,
    cci.transformations,
    cci.transformation_runs,
    cci.dataset_lineage
TO cci_research_writer;

-- General readers see only the two reviewed provider-resolution views.
GRANT SELECT ON
    cci.provider_platform_resolution_current,
    cci.provider_platform_mappings_current
TO cci_reader;

GRANT EXECUTE ON FUNCTION
    cci.provider_platform_resolution_as_known(TIMESTAMPTZ, TIMESTAMPTZ)
TO cci_identity_resolver;

INSERT INTO cci.schema_migrations (version, description)
VALUES ('010_runtime_role_bootstrap', 'Create NOLOGIN role groups and deny-by-default runtime privileges');

COMMIT;
