"""Database schema migrations."""

SCHEMA_VERSION = 2

MIGRATIONS = {
    1: """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            realm_id TEXT NOT NULL UNIQUE,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qbo_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            full_name TEXT NOT NULL,
            parent_id INTEGER REFERENCES categories(id),
            account_type TEXT NOT NULL,
            is_visible INTEGER NOT NULL DEFAULT 1,
            display_order INTEGER NOT NULL DEFAULT 0,
            synced_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pattern TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            category_id INTEGER NOT NULL REFERENCES categories(id),
            min_amount TEXT,
            max_amount TEXT,
            priority INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_rules_active_priority
            ON rules(is_active, priority DESC);

        CREATE TABLE IF NOT EXISTS vendor_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name TEXT NOT NULL UNIQUE,
            vendor_id TEXT,
            default_category_id INTEGER NOT NULL REFERENCES categories(id),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_vendor_mappings_name
            ON vendor_mappings(vendor_name);

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qbo_id TEXT NOT NULL UNIQUE,
            account_id TEXT NOT NULL,
            account_name TEXT NOT NULL,
            date TEXT NOT NULL,
            amount TEXT NOT NULL,
            description TEXT NOT NULL,
            vendor_name TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            assigned_category_id INTEGER REFERENCES categories(id),
            fetched_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_transactions_status
            ON transactions(status);
        CREATE INDEX IF NOT EXISTS idx_transactions_date
            ON transactions(date);

        CREATE TABLE IF NOT EXISTS transaction_splits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
            category_id INTEGER NOT NULL REFERENCES categories(id),
            amount TEXT NOT NULL,
            memo TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_transaction_splits_transaction
            ON transaction_splits(transaction_id);

        INSERT INTO schema_version (version) VALUES (1);
    """,
    2: """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        UPDATE schema_version SET version = 2;
    """,
}


def get_migration_sql(from_version: int, to_version: int) -> list[str]:
    """Get list of migration SQL statements to run."""
    statements = []
    for version in range(from_version + 1, to_version + 1):
        if version in MIGRATIONS:
            statements.append(MIGRATIONS[version])
    return statements
