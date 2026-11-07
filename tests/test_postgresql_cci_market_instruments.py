import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg import errors


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = [
    ROOT / "migrations" / "001_cci_root_entities.sql",
    ROOT / "migrations" / "002_source_policy_catalog.sql",
    ROOT / "migrations" / "003_provider_platform_reviews.sql",
    ROOT / "migrations" / "004_network_identifiers.sql",
    ROOT / "migrations" / "005_asset_representations_relationships.sql",
    ROOT / "migrations" / "006_asset_identity_resolution.sql",
    ROOT / "migrations" / "007_market_instrument_catalog.sql",
]


class CCIMarketInstrumentMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "CCI_TEST_DATABASE_URL" not in os.environ:
            raise unittest.SkipTest(
                "CCI market instrument tests require CCI_TEST_DATABASE_URL; "
                "run them through the dedicated PostgreSQL workflow."
            )
        cls.dsn = os.environ["CCI_TEST_DATABASE_URL"]
        with psycopg.connect(cls.dsn, autocommit=True) as conn:
            conn.execute("DROP SCHEMA IF EXISTS cci CASCADE")
            for migration_path in MIGRATIONS:
                conn.execute(migration_path.read_text(encoding="utf-8"), prepare=False)

    def setUp(self):
        self.conn = psycopg.connect(os.environ["CCI_TEST_DATABASE_URL"])
        self.source_a = uuid.uuid4()
        self.source_b = uuid.uuid4()
        self.asset_base = uuid.uuid4()
        self.asset_quote = uuid.uuid4()
        self.now = datetime.now(timezone.utc)
        self.conn.execute(
            """
            INSERT INTO cci.data_sources
                (id, source_key, display_name, source_type, status)
            VALUES
                (%s, 'synthetic-market-a', 'Synthetic market A', 'synthetic', 'active'),
                (%s, 'synthetic-market-b', 'Synthetic market B', 'synthetic', 'active')
            """,
            (self.source_a, self.source_b),
        )
        self.conn.execute(
            """
            INSERT INTO cci.assets (id, canonical_code, display_name, asset_type)
            VALUES
                (%s, 'SYNTHETIC:BASE', 'Synthetic base', 'crypto'),
                (%s, 'SYNTHETIC:QUOTE', 'Synthetic quote', 'stablecoin')
            """,
            (self.asset_base, self.asset_quote),
        )
        self.dataset_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.datasets (
                id, dataset_key, version, stage, data_format, schema_name,
                schema_version, storage_uri, checksum_sha256, retention_status
            ) VALUES (%s, 'synthetic-market-metadata', 1, 'source_capture',
                      'json', 'synthetic', '1', 'synthetic://metadata',
                      %s, 'active')
            """,
            (self.dataset_id, "c" * 64),
        )

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def insert_instrument(self, *, source_id=None, symbol="SYNTH/USDT",
                          base_id=None, quote_id=None, market_type="spot"):
        instrument_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.market_instruments (
                id, data_source_id, native_symbol, native_base_asset_code,
                native_quote_asset_code, base_asset_id, quote_asset_id, market_type
            ) VALUES (%s, %s, %s, 'SYNTH', 'USDT', %s, %s, %s)
            """,
            (
                instrument_id, source_id or self.source_a, symbol,
                base_id, quote_id, market_type,
            ),
        )
        return instrument_id

    def insert_metadata(self, instrument_id, *, source_dataset_id=None,
                        price_precision=8, quantity_precision=6,
                        valid_from=None, valid_until=None, provider_metadata='{"source":"synthetic"}'):
        metadata_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.instrument_metadata_versions (
                id, market_instrument_id, source_dataset_id, observed_at,
                valid_from, valid_until, source_status, price_precision,
                quantity_precision, provider_metadata, mapping_version, schema_version
            ) VALUES (%s, %s, %s, %s, %s, %s, 'TRADING', %s, %s,
                      %s::jsonb, 'synthetic-map-v1', 'synthetic-schema-v1')
            """,
            (
                metadata_id, instrument_id, source_dataset_id, self.now,
                valid_from, valid_until, price_precision, quantity_precision,
                provider_metadata,
            ),
        )
        return metadata_id

    def test_migration_installs_four_market_instrument_entities(self):
        names = {
            row[0] for row in self.conn.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'cci' AND table_type = 'BASE TABLE'
                """
            ).fetchall()
        }
        self.assertTrue({
            "market_instruments", "instrument_identifiers",
            "instrument_metadata_versions", "instrument_trading_rules",
        }.issubset(names))
        self.assertEqual(
            self.conn.execute(
                "SELECT version FROM cci.schema_migrations WHERE version = '007_market_instrument_catalog'"
            ).fetchone()[0],
            "007_market_instrument_catalog",
        )

    def test_instrument_can_remain_unresolved_without_canonical_asset_ids(self):
        instrument_id = self.insert_instrument()
        row = self.conn.execute(
            "SELECT base_asset_id, quote_asset_id FROM cci.market_instruments WHERE id = %s",
            (instrument_id,),
        ).fetchone()
        self.assertEqual(row, (None, None))

    def test_base_and_quote_asset_ids_must_be_both_null_or_distinct(self):
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_instrument(base_id=self.asset_base)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_instrument(base_id=self.asset_base, quote_id=self.asset_base)

    def test_same_native_symbol_is_allowed_across_distinct_sources(self):
        first = self.insert_instrument(source_id=self.source_a, symbol="SYNTH/USDT")
        second = self.insert_instrument(source_id=self.source_b, symbol="SYNTH/USDT")
        self.assertNotEqual(first, second)

    def test_instrument_identity_requires_existing_source_and_asset_references(self):
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.insert_instrument(source_id=uuid.uuid4())
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.insert_instrument(base_id=uuid.uuid4(), quote_id=self.asset_quote)

    def test_source_scoped_composite_candidate_key_is_installed(self):
        exists = self.conn.execute(
            """
            SELECT count(*) FROM pg_constraint
            WHERE conname = 'market_instruments_uq_id_source' AND contype = 'u'
            """
        ).fetchone()[0]
        self.assertEqual(exists, 1)

    def test_multiple_exchange_aliases_are_preserved_without_collapsing(self):
        instrument_id = self.insert_instrument()
        for namespace, value in (
            ("rest_pair_key", "SYNTHUSDT"),
            ("rest_altname", "SYNTH/USDT"),
            ("rest_wsname", "SYNTH/USDT"),
        ):
            self.conn.execute(
                """
                INSERT INTO cci.instrument_identifiers (
                    id, market_instrument_id, identifier_namespace,
                    identifier_value, is_primary, observed_at
                ) VALUES (%s, %s, %s, %s, false, %s)
                """,
                (uuid.uuid4(), instrument_id, namespace, value, self.now),
            )
        count = self.conn.execute(
            "SELECT count(*) FROM cci.instrument_identifiers WHERE market_instrument_id = %s",
            (instrument_id,),
        ).fetchone()[0]
        self.assertEqual(count, 3)

    def test_identifier_validity_interval_rejects_inversion(self):
        instrument_id = self.insert_instrument()
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.instrument_identifiers (
                        id, market_instrument_id, identifier_namespace,
                        identifier_value, valid_from, valid_until, observed_at
                    ) VALUES (%s, %s, 'synthetic', 'bad-range', %s, %s, %s)
                    """,
                    (
                        uuid.uuid4(), instrument_id,
                        self.now, self.now - timedelta(seconds=1), self.now,
                    ),
                )

    def test_metadata_version_accepts_optional_dataset_and_exact_json_metadata(self):
        instrument_id = self.insert_instrument()
        metadata_id = self.insert_metadata(
            instrument_id, source_dataset_id=self.dataset_id,
            provider_metadata='{"tickSize":"0.0001","source":"synthetic"}',
        )
        value = self.conn.execute(
            "SELECT provider_metadata ->> 'tickSize' FROM cci.instrument_metadata_versions WHERE id = %s",
            (metadata_id,),
        ).fetchone()[0]
        self.assertEqual(value, "0.0001")

    def test_metadata_version_rejects_negative_precision_and_inverted_validity(self):
        instrument_id = self.insert_instrument()
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_metadata(instrument_id, price_precision=-1)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_metadata(
                    instrument_id, valid_from=self.now,
                    valid_until=self.now - timedelta(seconds=1),
                )

    def test_metadata_version_rejects_non_object_provider_metadata(self):
        instrument_id = self.insert_instrument()
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_metadata(instrument_id, provider_metadata='[]')

    def test_trading_rules_preserve_decimal_parameters_as_json_strings(self):
        instrument_id = self.insert_instrument()
        metadata_id = self.insert_metadata(instrument_id)
        self.conn.execute(
            """
            INSERT INTO cci.instrument_trading_rules (
                id, metadata_version_id, rule_namespace, rule_scope, parameters
            ) VALUES (%s, %s, 'PRICE_FILTER', 'price',
                      '{"tickSize":"0.0001","minPrice":"0.01"}'::jsonb)
            """,
            (uuid.uuid4(), metadata_id),
        )
        self.assertEqual(
            self.conn.execute(
                """
                SELECT parameters ->> 'tickSize'
                FROM cci.instrument_trading_rules
                WHERE metadata_version_id = %s
                """,
                (metadata_id,),
            ).fetchone()[0],
            "0.0001",
        )

    def test_trading_rule_scope_and_per_version_uniqueness_are_enforced(self):
        instrument_id = self.insert_instrument()
        metadata_id = self.insert_metadata(instrument_id)
        self.conn.execute(
            """
            INSERT INTO cci.instrument_trading_rules (
                id, metadata_version_id, rule_namespace, rule_scope, parameters
            ) VALUES (%s, %s, 'LOT_SIZE', 'limit_quantity', '{"stepSize":"0.001"}')
            """,
            (uuid.uuid4(), metadata_id),
        )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.instrument_trading_rules (
                        id, metadata_version_id, rule_namespace, rule_scope, parameters
                    ) VALUES (%s, %s, 'UNKNOWN', 'universal_step', '{}')
                    """,
                    (uuid.uuid4(), metadata_id),
                )
        with self.assertRaises(errors.UniqueViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.instrument_trading_rules (
                        id, metadata_version_id, rule_namespace, rule_scope, parameters
                    ) VALUES (%s, %s, 'LOT_SIZE', 'limit_quantity', '{"stepSize":"0.002"}')
                    """,
                    (uuid.uuid4(), metadata_id),
                )

    def test_metadata_versions_and_rules_are_append_only(self):
        instrument_id = self.insert_instrument()
        metadata_id = self.insert_metadata(instrument_id)
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    "UPDATE cci.instrument_metadata_versions SET source_status = 'HALTED' WHERE id = %s",
                    (metadata_id,),
                )
        rule_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.instrument_trading_rules (
                id, metadata_version_id, rule_namespace, rule_scope, parameters
            ) VALUES (%s, %s, 'MIN_NOTIONAL', 'notional', '{"minNotional":"5"}')
            """,
            (rule_id, metadata_id),
        )
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    "DELETE FROM cci.instrument_trading_rules WHERE id = %s",
                    (rule_id,),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
