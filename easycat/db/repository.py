"""Data access layer for SQLite database."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import aiosqlite

from easycat.db.migrations import SCHEMA_VERSION, get_migration_sql
from easycat.db.models import (
    Category,
    PatternType,
    Rule,
    Token,
    Transaction,
    TransactionSplit,
    TransactionStatus,
    VendorMapping,
)


class Repository:
    """Async repository for database operations."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Connect to the database and run migrations."""
        self._connection = await aiosqlite.connect(self._db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._run_migrations()

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _run_migrations(self) -> None:  # pragma: no cover
        """Run pending database migrations."""
        current_version = await self._get_schema_version()
        if current_version < SCHEMA_VERSION:
            migrations = get_migration_sql(current_version, SCHEMA_VERSION)
            for sql in migrations:
                await self._connection.executescript(sql)
            await self._connection.commit()

    async def _get_schema_version(self) -> int:
        """Get current schema version from database."""
        try:
            cursor = await self._connection.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            )
            row = await cursor.fetchone()
            return row["version"] if row else 0
        except aiosqlite.OperationalError:
            return 0

    # Token operations

    async def save_token(self, token: Token) -> Token:
        """Save or update an OAuth token."""
        now = datetime.now().isoformat()
        if token.id is None:
            await self._connection.execute(
                """INSERT INTO tokens (realm_id, access_token, refresh_token,
                   expires_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(realm_id) DO UPDATE SET
                   access_token=excluded.access_token,
                   refresh_token=excluded.refresh_token,
                   expires_at=excluded.expires_at,
                   updated_at=excluded.updated_at""",
                (
                    token.realm_id,
                    token.access_token,
                    token.refresh_token,
                    token.expires_at.isoformat(),
                    now,
                    now,
                ),
            )
            await self._connection.commit()
            saved = await self.get_token_by_realm(token.realm_id)
        else:
            await self._connection.execute(
                """UPDATE tokens SET access_token=?, refresh_token=?,
                   expires_at=?, updated_at=? WHERE id=?""",
                (
                    token.access_token,
                    token.refresh_token,
                    token.expires_at.isoformat(),
                    now,
                    token.id,
                ),
            )
            await self._connection.commit()
            saved = await self.get_token_by_id(token.id)
        return saved

    async def get_token_by_id(self, token_id: int) -> Token | None:
        """Get token by ID."""
        cursor = await self._connection.execute("SELECT * FROM tokens WHERE id = ?", (token_id,))
        row = await cursor.fetchone()
        return self._row_to_token(row) if row else None

    async def get_token_by_realm(self, realm_id: str) -> Token | None:
        """Get token by realm ID."""
        cursor = await self._connection.execute(
            "SELECT * FROM tokens WHERE realm_id = ?", (realm_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_token(row) if row else None

    async def get_latest_token(self) -> Token | None:
        """Get the most recently updated token."""
        cursor = await self._connection.execute(
            "SELECT * FROM tokens ORDER BY updated_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return self._row_to_token(row) if row else None

    async def delete_token(self, token_id: int) -> None:
        """Delete a token."""
        await self._connection.execute("DELETE FROM tokens WHERE id = ?", (token_id,))
        await self._connection.commit()

    def _row_to_token(self, row: aiosqlite.Row) -> Token:
        """Convert database row to Token object."""
        return Token(
            id=row["id"],
            realm_id=row["realm_id"],
            access_token=row["access_token"],
            refresh_token=row["refresh_token"],
            expires_at=datetime.fromisoformat(row["expires_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # Category operations

    async def save_category(self, category: Category) -> Category:
        """Save or update a category."""
        if category.id is None:
            await self._connection.execute(
                """INSERT INTO categories (qbo_id, name, full_name, parent_id,
                   account_type, is_visible, display_order, synced_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(qbo_id) DO UPDATE SET
                   name=excluded.name, full_name=excluded.full_name,
                   parent_id=excluded.parent_id, account_type=excluded.account_type,
                   synced_at=excluded.synced_at""",
                (
                    category.qbo_id,
                    category.name,
                    category.full_name,
                    category.parent_id,
                    category.account_type,
                    int(category.is_visible),
                    category.display_order,
                    category.synced_at.isoformat(),
                ),
            )
            await self._connection.commit()
            saved = await self.get_category_by_qbo_id(category.qbo_id)
        else:
            await self._connection.execute(
                """UPDATE categories SET qbo_id=?, name=?, full_name=?, parent_id=?,
                   account_type=?, is_visible=?, display_order=?, synced_at=?
                   WHERE id=?""",
                (
                    category.qbo_id,
                    category.name,
                    category.full_name,
                    category.parent_id,
                    category.account_type,
                    int(category.is_visible),
                    category.display_order,
                    category.synced_at.isoformat(),
                    category.id,
                ),
            )
            await self._connection.commit()
            saved = await self.get_category_by_id(category.id)
        return saved

    async def get_category_by_id(self, category_id: int) -> Category | None:
        """Get category by ID."""
        cursor = await self._connection.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_category(row) if row else None

    async def get_category_by_qbo_id(self, qbo_id: str) -> Category | None:
        """Get category by QuickBooks ID."""
        cursor = await self._connection.execute(
            "SELECT * FROM categories WHERE qbo_id = ?", (qbo_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_category(row) if row else None

    async def get_all_categories(self) -> list[Category]:
        """Get all categories."""
        cursor = await self._connection.execute(
            "SELECT * FROM categories ORDER BY display_order, full_name"
        )
        rows = await cursor.fetchall()
        return [self._row_to_category(row) for row in rows]

    async def get_visible_categories(self) -> list[Category]:
        """Get only visible categories."""
        cursor = await self._connection.execute(
            "SELECT * FROM categories WHERE is_visible = 1 ORDER BY display_order, full_name"
        )
        rows = await cursor.fetchall()
        return [self._row_to_category(row) for row in rows]

    async def update_category_visibility(self, category_id: int, is_visible: bool) -> None:
        """Update category visibility."""
        await self._connection.execute(
            "UPDATE categories SET is_visible = ? WHERE id = ?", (int(is_visible), category_id)
        )
        await self._connection.commit()

    def _row_to_category(self, row: aiosqlite.Row) -> Category:
        """Convert database row to Category object."""
        return Category(
            id=row["id"],
            qbo_id=row["qbo_id"],
            name=row["name"],
            full_name=row["full_name"],
            parent_id=row["parent_id"],
            account_type=row["account_type"],
            is_visible=bool(row["is_visible"]),
            display_order=row["display_order"],
            synced_at=datetime.fromisoformat(row["synced_at"]),
        )

    # Rule operations

    async def save_rule(self, rule: Rule) -> Rule:
        """Save or update a rule."""
        min_amt = str(rule.min_amount) if rule.min_amount is not None else None
        max_amt = str(rule.max_amount) if rule.max_amount is not None else None
        if rule.id is None:
            cursor = await self._connection.execute(
                """INSERT INTO rules (name, pattern, pattern_type, category_id,
                   min_amount, max_amount, priority, is_active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rule.name,
                    rule.pattern,
                    rule.pattern_type.value,
                    rule.category_id,
                    min_amt,
                    max_amt,
                    rule.priority,
                    int(rule.is_active),
                    rule.created_at.isoformat(),
                ),
            )
            await self._connection.commit()
            rule_id = cursor.lastrowid
        else:
            await self._connection.execute(
                """UPDATE rules SET name=?, pattern=?, pattern_type=?, category_id=?,
                   min_amount=?, max_amount=?, priority=?, is_active=?
                   WHERE id=?""",
                (
                    rule.name,
                    rule.pattern,
                    rule.pattern_type.value,
                    rule.category_id,
                    min_amt,
                    max_amt,
                    rule.priority,
                    int(rule.is_active),
                    rule.id,
                ),
            )
            await self._connection.commit()
            rule_id = rule.id
        return await self.get_rule_by_id(rule_id)

    async def get_rule_by_id(self, rule_id: int) -> Rule | None:
        """Get rule by ID."""
        cursor = await self._connection.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
        row = await cursor.fetchone()
        return self._row_to_rule(row) if row else None

    async def get_active_rules(self) -> list[Rule]:
        """Get all active rules ordered by priority."""
        cursor = await self._connection.execute(
            "SELECT * FROM rules WHERE is_active = 1 ORDER BY priority DESC"
        )
        rows = await cursor.fetchall()
        return [self._row_to_rule(row) for row in rows]

    async def get_all_rules(self) -> list[Rule]:
        """Get all rules."""
        cursor = await self._connection.execute("SELECT * FROM rules ORDER BY priority DESC, name")
        rows = await cursor.fetchall()
        return [self._row_to_rule(row) for row in rows]

    async def delete_rule(self, rule_id: int) -> None:
        """Delete a rule."""
        await self._connection.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        await self._connection.commit()

    def _row_to_rule(self, row: aiosqlite.Row) -> Rule:
        """Convert database row to Rule object."""
        return Rule(
            id=row["id"],
            name=row["name"],
            pattern=row["pattern"],
            pattern_type=PatternType(row["pattern_type"]),
            category_id=row["category_id"],
            min_amount=Decimal(row["min_amount"]) if row["min_amount"] else None,
            max_amount=Decimal(row["max_amount"]) if row["max_amount"] else None,
            priority=row["priority"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # Vendor mapping operations

    async def save_vendor_mapping(self, mapping: VendorMapping) -> VendorMapping:
        """Save or update a vendor mapping."""
        now = datetime.now().isoformat()
        if mapping.id is None:
            cursor = await self._connection.execute(
                """INSERT INTO vendor_mappings (vendor_name, vendor_id,
                   default_category_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(vendor_name) DO UPDATE SET
                   vendor_id=excluded.vendor_id,
                   default_category_id=excluded.default_category_id,
                   updated_at=excluded.updated_at""",
                (mapping.vendor_name, mapping.vendor_id, mapping.default_category_id, now, now),
            )
            await self._connection.commit()
            mapping_id = cursor.lastrowid
        else:
            await self._connection.execute(
                """UPDATE vendor_mappings SET vendor_name=?, vendor_id=?,
                   default_category_id=?, updated_at=? WHERE id=?""",
                (
                    mapping.vendor_name,
                    mapping.vendor_id,
                    mapping.default_category_id,
                    now,
                    mapping.id,
                ),
            )
            await self._connection.commit()
            mapping_id = mapping.id
        return await self.get_vendor_mapping_by_id(mapping_id)

    async def get_vendor_mapping_by_id(self, mapping_id: int) -> VendorMapping | None:
        """Get vendor mapping by ID."""
        cursor = await self._connection.execute(
            "SELECT * FROM vendor_mappings WHERE id = ?", (mapping_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_vendor_mapping(row) if row else None

    async def get_vendor_mapping_by_name(self, vendor_name: str) -> VendorMapping | None:
        """Get vendor mapping by vendor name."""
        cursor = await self._connection.execute(
            "SELECT * FROM vendor_mappings WHERE vendor_name = ?", (vendor_name,)
        )
        row = await cursor.fetchone()
        return self._row_to_vendor_mapping(row) if row else None

    async def get_all_vendor_mappings(self) -> list[VendorMapping]:
        """Get all vendor mappings."""
        cursor = await self._connection.execute(
            "SELECT * FROM vendor_mappings ORDER BY vendor_name"
        )
        rows = await cursor.fetchall()
        return [self._row_to_vendor_mapping(row) for row in rows]

    async def delete_vendor_mapping(self, mapping_id: int) -> None:
        """Delete a vendor mapping."""
        await self._connection.execute("DELETE FROM vendor_mappings WHERE id = ?", (mapping_id,))
        await self._connection.commit()

    def _row_to_vendor_mapping(self, row: aiosqlite.Row) -> VendorMapping:
        """Convert database row to VendorMapping object."""
        return VendorMapping(
            id=row["id"],
            vendor_name=row["vendor_name"],
            vendor_id=row["vendor_id"],
            default_category_id=row["default_category_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # Transaction operations

    async def save_transaction(self, txn: Transaction) -> Transaction:
        """Save or update a transaction."""
        if txn.id is None:
            await self._connection.execute(
                """INSERT INTO transactions (qbo_id, account_id, account_name, date,
                   amount, description, vendor_name, status, assigned_category_id,
                   fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(qbo_id) DO UPDATE SET
                   account_id=excluded.account_id, account_name=excluded.account_name,
                   date=excluded.date, amount=excluded.amount,
                   description=excluded.description, vendor_name=excluded.vendor_name,
                   fetched_at=excluded.fetched_at""",
                (
                    txn.qbo_id,
                    txn.account_id,
                    txn.account_name,
                    txn.date.isoformat(),
                    str(txn.amount),
                    txn.description,
                    txn.vendor_name,
                    txn.status.value,
                    txn.assigned_category_id,
                    txn.fetched_at.isoformat(),
                ),
            )
            await self._connection.commit()
            saved = await self.get_transaction_by_qbo_id(txn.qbo_id)
        else:
            await self._connection.execute(
                """UPDATE transactions SET qbo_id=?, account_id=?, account_name=?,
                   date=?, amount=?, description=?, vendor_name=?, status=?,
                   assigned_category_id=?, fetched_at=?
                   WHERE id=?""",
                (
                    txn.qbo_id,
                    txn.account_id,
                    txn.account_name,
                    txn.date.isoformat(),
                    str(txn.amount),
                    txn.description,
                    txn.vendor_name,
                    txn.status.value,
                    txn.assigned_category_id,
                    txn.fetched_at.isoformat(),
                    txn.id,
                ),
            )
            await self._connection.commit()
            saved = await self.get_transaction_by_id(txn.id)
        return saved

    async def get_transaction_by_id(self, txn_id: int) -> Transaction | None:
        """Get transaction by ID."""
        cursor = await self._connection.execute(
            "SELECT * FROM transactions WHERE id = ?", (txn_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_transaction(row) if row else None

    async def get_transaction_by_qbo_id(self, qbo_id: str) -> Transaction | None:
        """Get transaction by QuickBooks ID."""
        cursor = await self._connection.execute(
            "SELECT * FROM transactions WHERE qbo_id = ?", (qbo_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_transaction(row) if row else None

    async def get_transactions_by_status(self, status: TransactionStatus) -> list[Transaction]:
        """Get transactions by status."""
        cursor = await self._connection.execute(
            "SELECT * FROM transactions WHERE status = ? ORDER BY date ASC", (status.value,)
        )
        rows = await cursor.fetchall()
        return [self._row_to_transaction(row) for row in rows]

    async def get_pending_transactions(self) -> list[Transaction]:
        """Get all pending transactions."""
        return await self.get_transactions_by_status(TransactionStatus.PENDING)

    async def search_transactions(
        self,
        status: TransactionStatus | None = None,
        search_text: str | None = None,
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Transaction]:
        """Search transactions with filters."""
        conditions = []
        params = []
        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)
        if search_text:
            conditions.append("(description LIKE ? OR vendor_name LIKE ?)")
            search_pattern = f"%{search_text}%"
            params.extend([search_pattern, search_pattern])
        if min_amount is not None:
            conditions.append("CAST(amount AS REAL) >= ?")
            params.append(float(min_amount))
        if max_amount is not None:
            conditions.append("CAST(amount AS REAL) <= ?")
            params.append(float(max_amount))
        if start_date is not None:
            conditions.append("date >= ?")
            params.append(start_date.isoformat())
        if end_date is not None:
            conditions.append("date <= ?")
            params.append(end_date.isoformat())
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM transactions WHERE {where_clause} ORDER BY date ASC"
        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_transaction(row) for row in rows]

    async def update_transaction_status(
        self, txn_id: int, status: TransactionStatus, category_id: int | None = None
    ) -> None:
        """Update transaction status and optionally category."""
        await self._connection.execute(
            "UPDATE transactions SET status = ?, assigned_category_id = ? WHERE id = ?",
            (status.value, category_id, txn_id),
        )
        await self._connection.commit()

    async def delete_transaction(self, txn_id: int) -> None:
        """Delete a transaction and its splits."""
        await self._connection.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
        await self._connection.commit()

    async def clear_posted_transactions(self) -> int:
        """Delete all posted transactions. Returns count deleted."""
        cursor = await self._connection.execute("DELETE FROM transactions WHERE status = 'posted'")
        await self._connection.commit()
        return cursor.rowcount

    def _row_to_transaction(self, row: aiosqlite.Row) -> Transaction:
        """Convert database row to Transaction object."""
        return Transaction(
            id=row["id"],
            qbo_id=row["qbo_id"],
            account_id=row["account_id"],
            account_name=row["account_name"],
            date=datetime.fromisoformat(row["date"]),
            amount=Decimal(row["amount"]),
            description=row["description"],
            vendor_name=row["vendor_name"],
            status=TransactionStatus(row["status"]),
            assigned_category_id=row["assigned_category_id"],
            fetched_at=datetime.fromisoformat(row["fetched_at"]),
        )

    # Transaction split operations

    async def save_transaction_split(self, split: TransactionSplit) -> TransactionSplit:
        """Save a transaction split."""
        if split.id is None:
            cursor = await self._connection.execute(
                """INSERT INTO transaction_splits (transaction_id, category_id,
                   amount, memo) VALUES (?, ?, ?, ?)""",
                (split.transaction_id, split.category_id, str(split.amount), split.memo),
            )
            await self._connection.commit()
            split_id = cursor.lastrowid
        else:
            await self._connection.execute(
                """UPDATE transaction_splits SET transaction_id=?, category_id=?,
                   amount=?, memo=? WHERE id=?""",
                (split.transaction_id, split.category_id, str(split.amount), split.memo, split.id),
            )
            await self._connection.commit()
            split_id = split.id
        return await self.get_split_by_id(split_id)

    async def get_split_by_id(self, split_id: int) -> TransactionSplit | None:
        """Get split by ID."""
        cursor = await self._connection.execute(
            "SELECT * FROM transaction_splits WHERE id = ?", (split_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_split(row) if row else None

    async def get_splits_for_transaction(self, txn_id: int) -> list[TransactionSplit]:
        """Get all splits for a transaction."""
        cursor = await self._connection.execute(
            "SELECT * FROM transaction_splits WHERE transaction_id = ?", (txn_id,)
        )
        rows = await cursor.fetchall()
        return [self._row_to_split(row) for row in rows]

    async def delete_splits_for_transaction(self, txn_id: int) -> None:
        """Delete all splits for a transaction."""
        await self._connection.execute(
            "DELETE FROM transaction_splits WHERE transaction_id = ?", (txn_id,)
        )
        await self._connection.commit()

    def _row_to_split(self, row: aiosqlite.Row) -> TransactionSplit:
        """Convert database row to TransactionSplit object."""
        return TransactionSplit(
            id=row["id"],
            transaction_id=row["transaction_id"],
            category_id=row["category_id"],
            amount=Decimal(row["amount"]),
            memo=row["memo"],
        )

    # Settings operations

    async def get_setting(self, key: str) -> str | None:
        """Get a setting value by key."""
        cursor = await self._connection.execute(
            'SELECT value FROM settings WHERE key = ?', (key,)
        )
        row = await cursor.fetchone()
        return row['value'] if row else None

    async def save_setting(self, key: str, value: str) -> None:
        """Save a setting value."""
        await self._connection.execute(
            'INSERT INTO settings (key, value) VALUES (?, ?) '
            'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
            (key, value),
        )
        await self._connection.commit()

    async def delete_setting(self, key: str) -> None:
        """Delete a setting."""
        await self._connection.execute('DELETE FROM settings WHERE key = ?', (key,))
        await self._connection.commit()
