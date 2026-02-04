"""Tests for database migrations."""

from easycat.db.migrations import (
    MIGRATIONS,
    SCHEMA_VERSION,
    get_migration_sql,
)


class TestMigrations:
    """Tests for migration functions."""

    def test_schema_version_matches_migrations(self):
        """Test that SCHEMA_VERSION matches the number of migrations."""
        assert len(MIGRATIONS) == SCHEMA_VERSION

    def test_get_migration_sql_from_zero(self):
        """Test getting all migrations from version 0."""
        migrations = get_migration_sql(0, SCHEMA_VERSION)
        assert len(migrations) == SCHEMA_VERSION
        assert migrations == [MIGRATIONS[v] for v in range(1, SCHEMA_VERSION + 1)]

    def test_get_migration_sql_partial(self):
        """Test getting a subset of migrations."""
        if SCHEMA_VERSION >= 2:
            migrations = get_migration_sql(1, SCHEMA_VERSION)
            assert len(migrations) == SCHEMA_VERSION - 1

    def test_get_migration_sql_same_version(self):
        """Test getting migrations when already at target version."""
        migrations = get_migration_sql(SCHEMA_VERSION, SCHEMA_VERSION)
        assert migrations == []

    def test_get_migration_sql_beyond_target(self):
        """Test getting migrations when current is beyond target."""
        migrations = get_migration_sql(SCHEMA_VERSION + 1, SCHEMA_VERSION)
        assert migrations == []

    def test_migration_v1_creates_tables(self):
        """Test that migration v1 creates all required tables."""
        v1_sql = MIGRATIONS[1]
        assert "CREATE TABLE" in v1_sql
        assert "schema_version" in v1_sql
        assert "tokens" in v1_sql
        assert "categories" in v1_sql
        assert "rules" in v1_sql
        assert "vendor_mappings" in v1_sql
        assert "transactions" in v1_sql
        assert "transaction_splits" in v1_sql

    def test_migration_v1_creates_indexes(self):
        """Test that migration v1 creates indexes."""
        v1_sql = MIGRATIONS[1]
        assert "CREATE INDEX" in v1_sql
        assert "idx_transactions_status" in v1_sql
        assert "idx_transactions_date" in v1_sql

    def test_migrations_dict_keys_are_sequential(self):
        """Test that migration versions are sequential starting from 1."""
        expected_versions = list(range(1, SCHEMA_VERSION + 1))
        assert sorted(MIGRATIONS.keys()) == expected_versions

    def test_get_migration_sql_with_missing_version(self, monkeypatch):
        """Test get_migration_sql handles missing versions gracefully."""
        sparse_migrations = {1: "SQL1", 3: "SQL3"}
        monkeypatch.setattr("easycat.db.migrations.MIGRATIONS", sparse_migrations)
        migrations = get_migration_sql(0, 3)
        assert len(migrations) == 2
        assert "SQL1" in migrations
        assert "SQL3" in migrations
