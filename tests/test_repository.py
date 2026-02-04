"""Tests for database repository."""

from datetime import datetime, timedelta
from decimal import Decimal

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
from easycat.db.repository import Repository


class TestRepositoryConnection:
    """Tests for repository connection management."""

    async def test_connect_creates_schema(self, temp_db_path):
        """Test that connect creates the database schema."""
        repo = Repository(temp_db_path)
        await repo.connect()
        version = await repo._get_schema_version()
        assert version > 0
        await repo.close()

    async def test_close_clears_connection(self, temp_db_path):
        """Test that close clears the connection."""
        repo = Repository(temp_db_path)
        await repo.connect()
        await repo.close()
        assert repo._connection is None

    async def test_close_without_connect(self, temp_db_path):
        """Test that close is safe without connect."""
        repo = Repository(temp_db_path)
        await repo.close()
        assert repo._connection is None

    async def test_connect_twice_skips_migrations(self, temp_db_path):
        """Test that connecting to existing DB skips migrations."""
        repo1 = Repository(temp_db_path)
        await repo1.connect()
        await repo1.close()
        repo2 = Repository(temp_db_path)
        await repo2.connect()
        version = await repo2._get_schema_version()
        assert version > 0
        await repo2.close()

    async def test_run_migrations_executes_sql(self, temp_db_path):
        """Test that _run_migrations actually runs migration SQL."""
        import aiosqlite

        conn = await aiosqlite.connect(temp_db_path)
        await conn.close()
        repo = Repository(temp_db_path)
        await repo.connect()
        cursor = await repo._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tokens'"
        )
        row = await cursor.fetchone()
        assert row is not None
        await repo.close()

    async def test_migrations_run_on_fresh_db(self, temp_dir):
        """Test migrations run when schema_version table doesn't exist."""
        from easycat.db.migrations import SCHEMA_VERSION, get_migration_sql

        db_path = temp_dir / "fresh.db"
        repo = Repository(db_path)
        await repo.connect()
        version = await repo._get_schema_version()
        assert version == SCHEMA_VERSION
        migrations = get_migration_sql(0, SCHEMA_VERSION)
        assert len(migrations) == SCHEMA_VERSION
        for sql in migrations:
            assert "CREATE TABLE" in sql
        await repo.close()

    async def test_run_migrations_method_directly(self, temp_dir):
        """Test _run_migrations method by calling it directly."""
        import aiosqlite

        db_path = temp_dir / "direct.db"
        repo = Repository(db_path)
        repo._connection = await aiosqlite.connect(db_path)
        repo._connection.row_factory = aiosqlite.Row
        initial_version = await repo._get_schema_version()
        assert initial_version == 0
        await repo._run_migrations()
        final_version = await repo._get_schema_version()
        assert final_version > 0
        await repo.close()


class TestTokenOperations:
    """Tests for token CRUD operations."""

    async def test_save_new_token(self, repository):
        """Test saving a new token."""
        now = datetime.now()
        token = Token(
            id=None,
            realm_id="realm123",
            access_token="access_token_value",
            refresh_token="refresh_token_value",
            expires_at=now + timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )
        saved = await repository.save_token(token)
        assert saved.id is not None
        assert saved.realm_id == "realm123"
        assert saved.access_token == "access_token_value"

    async def test_save_token_upsert(self, repository):
        """Test that save_token performs upsert on realm_id conflict."""
        now = datetime.now()
        token1 = Token(
            id=None,
            realm_id="realm123",
            access_token="first_access",
            refresh_token="first_refresh",
            expires_at=now + timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )
        await repository.save_token(token1)
        token2 = Token(
            id=None,
            realm_id="realm123",
            access_token="second_access",
            refresh_token="second_refresh",
            expires_at=now + timedelta(hours=2),
            created_at=now,
            updated_at=now,
        )
        saved2 = await repository.save_token(token2)
        assert saved2.access_token == "second_access"

    async def test_update_existing_token(self, repository):
        """Test updating an existing token by ID."""
        now = datetime.now()
        token = Token(
            id=None,
            realm_id="realm456",
            access_token="original",
            refresh_token="refresh",
            expires_at=now + timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )
        saved = await repository.save_token(token)
        updated_token = Token(
            id=saved.id,
            realm_id="realm456",
            access_token="updated",
            refresh_token="new_refresh",
            expires_at=now + timedelta(hours=2),
            created_at=saved.created_at,
            updated_at=now,
        )
        updated = await repository.save_token(updated_token)
        assert updated.id == saved.id
        assert updated.access_token == "updated"

    async def test_get_token_by_id(self, repository):
        """Test getting a token by ID."""
        now = datetime.now()
        token = Token(
            id=None,
            realm_id="realm789",
            access_token="access",
            refresh_token="refresh",
            expires_at=now + timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )
        saved = await repository.save_token(token)
        retrieved = await repository.get_token_by_id(saved.id)
        assert retrieved is not None
        assert retrieved.realm_id == "realm789"

    async def test_get_token_by_id_not_found(self, repository):
        """Test getting a non-existent token by ID."""
        retrieved = await repository.get_token_by_id(99999)
        assert retrieved is None

    async def test_get_token_by_realm(self, repository):
        """Test getting a token by realm ID."""
        now = datetime.now()
        token = Token(
            id=None,
            realm_id="unique_realm",
            access_token="access",
            refresh_token="refresh",
            expires_at=now + timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )
        await repository.save_token(token)
        retrieved = await repository.get_token_by_realm("unique_realm")
        assert retrieved is not None
        assert retrieved.realm_id == "unique_realm"

    async def test_get_token_by_realm_not_found(self, repository):
        """Test getting a non-existent token by realm ID."""
        retrieved = await repository.get_token_by_realm("nonexistent")
        assert retrieved is None

    async def test_get_latest_token(self, repository):
        """Test getting the most recently updated token."""
        now = datetime.now()
        token1 = Token(
            id=None,
            realm_id="realm1",
            access_token="first",
            refresh_token="refresh1",
            expires_at=now + timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )
        await repository.save_token(token1)
        token2 = Token(
            id=None,
            realm_id="realm2",
            access_token="second",
            refresh_token="refresh2",
            expires_at=now + timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )
        await repository.save_token(token2)
        latest = await repository.get_latest_token()
        assert latest is not None
        assert latest.realm_id == "realm2"

    async def test_get_latest_token_empty(self, repository):
        """Test getting latest token when none exist."""
        latest = await repository.get_latest_token()
        assert latest is None

    async def test_delete_token(self, repository):
        """Test deleting a token."""
        now = datetime.now()
        token = Token(
            id=None,
            realm_id="to_delete",
            access_token="access",
            refresh_token="refresh",
            expires_at=now + timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )
        saved = await repository.save_token(token)
        await repository.delete_token(saved.id)
        retrieved = await repository.get_token_by_id(saved.id)
        assert retrieved is None


class TestCategoryOperations:
    """Tests for category CRUD operations."""

    async def test_save_new_category(self, repository):
        """Test saving a new category."""
        now = datetime.now()
        category = Category(
            id=None,
            qbo_id="cat123",
            name="Office Supplies",
            full_name="Expenses:Office Supplies",
            parent_id="parent123",
            account_type="Expense",
            is_visible=True,
            display_order=10,
            synced_at=now,
        )
        saved = await repository.save_category(category)
        assert saved.id is not None
        assert saved.name == "Office Supplies"

    async def test_save_category_upsert(self, repository):
        """Test that save_category performs upsert on qbo_id conflict."""
        now = datetime.now()
        cat1 = Category(
            id=None,
            qbo_id="cat_dup",
            name="Original",
            full_name="Original",
            parent_id=None,
            account_type="Expense",
            is_visible=True,
            display_order=0,
            synced_at=now,
        )
        await repository.save_category(cat1)
        cat2 = Category(
            id=None,
            qbo_id="cat_dup",
            name="Updated",
            full_name="Updated",
            parent_id=None,
            account_type="Expense",
            is_visible=True,
            display_order=0,
            synced_at=now,
        )
        saved = await repository.save_category(cat2)
        assert saved.name == "Updated"

    async def test_update_existing_category(self, repository):
        """Test updating an existing category by ID."""
        now = datetime.now()
        category = Category(
            id=None,
            qbo_id="cat_update",
            name="Original",
            full_name="Original",
            parent_id=None,
            account_type="Expense",
            is_visible=True,
            display_order=0,
            synced_at=now,
        )
        saved = await repository.save_category(category)
        updated_cat = Category(
            id=saved.id,
            qbo_id="cat_update",
            name="Modified",
            full_name="Modified",
            parent_id=None,
            account_type="Expense",
            is_visible=False,
            display_order=5,
            synced_at=now,
        )
        updated = await repository.save_category(updated_cat)
        assert updated.name == "Modified"
        assert updated.is_visible is False

    async def test_get_category_by_id(self, repository):
        """Test getting a category by ID."""
        now = datetime.now()
        category = Category(
            id=None,
            qbo_id="cat_get",
            name="Test",
            full_name="Test",
            parent_id=None,
            account_type="Expense",
            is_visible=True,
            display_order=0,
            synced_at=now,
        )
        saved = await repository.save_category(category)
        retrieved = await repository.get_category_by_id(saved.id)
        assert retrieved is not None
        assert retrieved.qbo_id == "cat_get"

    async def test_get_category_by_id_not_found(self, repository):
        """Test getting a non-existent category by ID."""
        retrieved = await repository.get_category_by_id(99999)
        assert retrieved is None

    async def test_get_category_by_qbo_id(self, repository):
        """Test getting a category by QuickBooks ID."""
        now = datetime.now()
        category = Category(
            id=None,
            qbo_id="unique_qbo_id",
            name="Test",
            full_name="Test",
            parent_id=None,
            account_type="Expense",
            is_visible=True,
            display_order=0,
            synced_at=now,
        )
        await repository.save_category(category)
        retrieved = await repository.get_category_by_qbo_id("unique_qbo_id")
        assert retrieved is not None
        assert retrieved.name == "Test"

    async def test_get_category_by_qbo_id_not_found(self, repository):
        """Test getting a non-existent category by QuickBooks ID."""
        retrieved = await repository.get_category_by_qbo_id("nonexistent")
        assert retrieved is None

    async def test_get_all_categories(self, repository):
        """Test getting all categories."""
        now = datetime.now()
        for i in range(3):
            category = Category(
                id=None,
                qbo_id=f"cat_all_{i}",
                name=f"Category {i}",
                full_name=f"Category {i}",
                parent_id=None,
                account_type="Expense",
                is_visible=True,
                display_order=i,
                synced_at=now,
            )
            await repository.save_category(category)
        categories = await repository.get_all_categories()
        assert len(categories) == 3

    async def test_get_visible_categories(self, repository):
        """Test getting only visible categories."""
        now = datetime.now()
        cat_visible = Category(
            id=None,
            qbo_id="cat_visible",
            name="Visible",
            full_name="Visible",
            parent_id=None,
            account_type="Expense",
            is_visible=True,
            display_order=0,
            synced_at=now,
        )
        cat_hidden = Category(
            id=None,
            qbo_id="cat_hidden",
            name="Hidden",
            full_name="Hidden",
            parent_id=None,
            account_type="Expense",
            is_visible=False,
            display_order=0,
            synced_at=now,
        )
        await repository.save_category(cat_visible)
        await repository.save_category(cat_hidden)
        visible = await repository.get_visible_categories()
        assert len(visible) == 1
        assert visible[0].name == "Visible"

    async def test_update_category_visibility(self, repository):
        """Test updating category visibility."""
        now = datetime.now()
        category = Category(
            id=None,
            qbo_id="cat_vis_toggle",
            name="Toggle",
            full_name="Toggle",
            parent_id=None,
            account_type="Expense",
            is_visible=True,
            display_order=0,
            synced_at=now,
        )
        saved = await repository.save_category(category)
        await repository.update_category_visibility(saved.id, False)
        updated = await repository.get_category_by_id(saved.id)
        assert updated.is_visible is False


class TestRuleOperations:
    """Tests for rule CRUD operations."""

    async def test_save_new_rule(self, repository):
        """Test saving a new rule."""
        now = datetime.now()
        rule = Rule(
            id=None,
            name="Amazon Rule",
            pattern="AMAZON",
            pattern_type=PatternType.CONTAINS,
            category_id=1,
            min_amount=None,
            max_amount=None,
            priority=10,
            is_active=True,
            created_at=now,
        )
        saved = await repository.save_rule(rule)
        assert saved.id is not None
        assert saved.name == "Amazon Rule"

    async def test_save_rule_with_amounts(self, repository):
        """Test saving a rule with amount constraints."""
        now = datetime.now()
        rule = Rule(
            id=None,
            name="Amount Rule",
            pattern="TEST",
            pattern_type=PatternType.CONTAINS,
            category_id=1,
            min_amount=Decimal("10.00"),
            max_amount=Decimal("500.00"),
            priority=10,
            is_active=True,
            created_at=now,
        )
        saved = await repository.save_rule(rule)
        assert saved.min_amount == Decimal("10.00")
        assert saved.max_amount == Decimal("500.00")

    async def test_update_existing_rule(self, repository):
        """Test updating an existing rule."""
        now = datetime.now()
        rule = Rule(
            id=None,
            name="Original",
            pattern="PATTERN",
            pattern_type=PatternType.CONTAINS,
            category_id=1,
            min_amount=None,
            max_amount=None,
            priority=10,
            is_active=True,
            created_at=now,
        )
        saved = await repository.save_rule(rule)
        updated_rule = Rule(
            id=saved.id,
            name="Updated",
            pattern="NEW_PATTERN",
            pattern_type=PatternType.REGEX,
            category_id=2,
            min_amount=Decimal("50.00"),
            max_amount=None,
            priority=20,
            is_active=False,
            created_at=saved.created_at,
        )
        updated = await repository.save_rule(updated_rule)
        assert updated.name == "Updated"
        assert updated.pattern_type == PatternType.REGEX

    async def test_get_rule_by_id(self, repository):
        """Test getting a rule by ID."""
        now = datetime.now()
        rule = Rule(
            id=None,
            name="Test Rule",
            pattern="TEST",
            pattern_type=PatternType.EXACT,
            category_id=1,
            min_amount=None,
            max_amount=None,
            priority=10,
            is_active=True,
            created_at=now,
        )
        saved = await repository.save_rule(rule)
        retrieved = await repository.get_rule_by_id(saved.id)
        assert retrieved is not None
        assert retrieved.name == "Test Rule"

    async def test_get_rule_by_id_not_found(self, repository):
        """Test getting a non-existent rule by ID."""
        retrieved = await repository.get_rule_by_id(99999)
        assert retrieved is None

    async def test_get_active_rules(self, repository):
        """Test getting only active rules."""
        now = datetime.now()
        active_rule = Rule(
            id=None,
            name="Active",
            pattern="ACTIVE",
            pattern_type=PatternType.CONTAINS,
            category_id=1,
            min_amount=None,
            max_amount=None,
            priority=10,
            is_active=True,
            created_at=now,
        )
        inactive_rule = Rule(
            id=None,
            name="Inactive",
            pattern="INACTIVE",
            pattern_type=PatternType.CONTAINS,
            category_id=1,
            min_amount=None,
            max_amount=None,
            priority=5,
            is_active=False,
            created_at=now,
        )
        await repository.save_rule(active_rule)
        await repository.save_rule(inactive_rule)
        active = await repository.get_active_rules()
        assert len(active) == 1
        assert active[0].name == "Active"

    async def test_get_all_rules(self, repository):
        """Test getting all rules."""
        now = datetime.now()
        for i in range(3):
            rule = Rule(
                id=None,
                name=f"Rule {i}",
                pattern=f"PATTERN_{i}",
                pattern_type=PatternType.CONTAINS,
                category_id=1,
                min_amount=None,
                max_amount=None,
                priority=i,
                is_active=True,
                created_at=now,
            )
            await repository.save_rule(rule)
        rules = await repository.get_all_rules()
        assert len(rules) == 3

    async def test_delete_rule(self, repository):
        """Test deleting a rule."""
        now = datetime.now()
        rule = Rule(
            id=None,
            name="To Delete",
            pattern="DELETE",
            pattern_type=PatternType.CONTAINS,
            category_id=1,
            min_amount=None,
            max_amount=None,
            priority=10,
            is_active=True,
            created_at=now,
        )
        saved = await repository.save_rule(rule)
        await repository.delete_rule(saved.id)
        retrieved = await repository.get_rule_by_id(saved.id)
        assert retrieved is None


class TestVendorMappingOperations:
    """Tests for vendor mapping CRUD operations."""

    async def test_save_new_vendor_mapping(self, repository):
        """Test saving a new vendor mapping."""
        mapping = VendorMapping(
            id=None,
            vendor_name="AMAZON.COM",
            vendor_id="vendor123",
            default_category_id=5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        saved = await repository.save_vendor_mapping(mapping)
        assert saved.id is not None
        assert saved.vendor_name == "AMAZON.COM"

    async def test_save_vendor_mapping_upsert(self, repository):
        """Test that save_vendor_mapping performs upsert on name conflict."""
        mapping1 = VendorMapping(
            id=None,
            vendor_name="DUP_VENDOR",
            vendor_id="first",
            default_category_id=1,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        await repository.save_vendor_mapping(mapping1)
        mapping2 = VendorMapping(
            id=None,
            vendor_name="DUP_VENDOR",
            vendor_id="second",
            default_category_id=2,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        saved = await repository.save_vendor_mapping(mapping2)
        assert saved.vendor_id == "second"

    async def test_update_existing_vendor_mapping(self, repository):
        """Test updating an existing vendor mapping."""
        mapping = VendorMapping(
            id=None,
            vendor_name="UPDATE_VENDOR",
            vendor_id="original",
            default_category_id=1,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        saved = await repository.save_vendor_mapping(mapping)
        updated_mapping = VendorMapping(
            id=saved.id,
            vendor_name="UPDATE_VENDOR_NEW",
            vendor_id="updated",
            default_category_id=2,
            created_at=saved.created_at,
            updated_at=datetime.now(),
        )
        updated = await repository.save_vendor_mapping(updated_mapping)
        assert updated.vendor_name == "UPDATE_VENDOR_NEW"
        assert updated.vendor_id == "updated"

    async def test_get_vendor_mapping_by_id(self, repository):
        """Test getting a vendor mapping by ID."""
        mapping = VendorMapping(
            id=None,
            vendor_name="GET_BY_ID",
            vendor_id="vendor",
            default_category_id=1,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        saved = await repository.save_vendor_mapping(mapping)
        retrieved = await repository.get_vendor_mapping_by_id(saved.id)
        assert retrieved is not None
        assert retrieved.vendor_name == "GET_BY_ID"

    async def test_get_vendor_mapping_by_id_not_found(self, repository):
        """Test getting a non-existent vendor mapping by ID."""
        retrieved = await repository.get_vendor_mapping_by_id(99999)
        assert retrieved is None

    async def test_get_vendor_mapping_by_name(self, repository):
        """Test getting a vendor mapping by name."""
        mapping = VendorMapping(
            id=None,
            vendor_name="UNIQUE_NAME",
            vendor_id="vendor",
            default_category_id=1,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        await repository.save_vendor_mapping(mapping)
        retrieved = await repository.get_vendor_mapping_by_name("UNIQUE_NAME")
        assert retrieved is not None
        assert retrieved.vendor_id == "vendor"

    async def test_get_vendor_mapping_by_name_not_found(self, repository):
        """Test getting a non-existent vendor mapping by name."""
        retrieved = await repository.get_vendor_mapping_by_name("NONEXISTENT")
        assert retrieved is None

    async def test_get_all_vendor_mappings(self, repository):
        """Test getting all vendor mappings."""
        for i in range(3):
            mapping = VendorMapping(
                id=None,
                vendor_name=f"VENDOR_{i}",
                vendor_id=f"id_{i}",
                default_category_id=i,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            await repository.save_vendor_mapping(mapping)
        mappings = await repository.get_all_vendor_mappings()
        assert len(mappings) == 3

    async def test_delete_vendor_mapping(self, repository):
        """Test deleting a vendor mapping."""
        mapping = VendorMapping(
            id=None,
            vendor_name="TO_DELETE",
            vendor_id="vendor",
            default_category_id=1,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        saved = await repository.save_vendor_mapping(mapping)
        await repository.delete_vendor_mapping(saved.id)
        retrieved = await repository.get_vendor_mapping_by_id(saved.id)
        assert retrieved is None


class TestTransactionOperations:
    """Tests for transaction CRUD operations."""

    async def test_save_new_transaction(self, repository):
        """Test saving a new transaction."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn123",
            account_id="acct456",
            account_name="Business Checking",
            date=now,
            amount=Decimal("125.50"),
            description="AMAZON MKTPLACE",
            vendor_name="Amazon",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        saved = await repository.save_transaction(txn)
        assert saved.id is not None
        assert saved.qbo_id == "txn123"

    async def test_save_transaction_upsert(self, repository):
        """Test that save_transaction performs upsert on qbo_id conflict."""
        now = datetime.now()
        txn1 = Transaction(
            id=None,
            qbo_id="txn_dup",
            account_id="acct1",
            account_name="Account 1",
            date=now,
            amount=Decimal("100.00"),
            description="First",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        await repository.save_transaction(txn1)
        txn2 = Transaction(
            id=None,
            qbo_id="txn_dup",
            account_id="acct2",
            account_name="Account 2",
            date=now,
            amount=Decimal("200.00"),
            description="Second",
            vendor_name="New Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        saved = await repository.save_transaction(txn2)
        assert saved.account_name == "Account 2"
        assert saved.amount == Decimal("200.00")

    async def test_update_existing_transaction(self, repository):
        """Test updating an existing transaction."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_update",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Original",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        saved = await repository.save_transaction(txn)
        updated_txn = Transaction(
            id=saved.id,
            qbo_id="txn_update",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("150.00"),
            description="Updated",
            vendor_name="New Vendor",
            status=TransactionStatus.CATEGORIZED,
            assigned_category_id=5,
            fetched_at=now,
        )
        updated = await repository.save_transaction(updated_txn)
        assert updated.description == "Updated"
        assert updated.status == TransactionStatus.CATEGORIZED

    async def test_get_transaction_by_id(self, repository):
        """Test getting a transaction by ID."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_get",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Test",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        saved = await repository.save_transaction(txn)
        retrieved = await repository.get_transaction_by_id(saved.id)
        assert retrieved is not None
        assert retrieved.qbo_id == "txn_get"

    async def test_get_transaction_by_id_not_found(self, repository):
        """Test getting a non-existent transaction by ID."""
        retrieved = await repository.get_transaction_by_id(99999)
        assert retrieved is None

    async def test_get_transactions_by_status(self, repository):
        """Test getting transactions by status."""
        now = datetime.now()
        pending_txn = Transaction(
            id=None,
            qbo_id="txn_pending",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Pending",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        posted_txn = Transaction(
            id=None,
            qbo_id="txn_posted",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("200.00"),
            description="Posted",
            vendor_name="Vendor",
            status=TransactionStatus.POSTED,
            assigned_category_id=1,
            fetched_at=now,
        )
        await repository.save_transaction(pending_txn)
        await repository.save_transaction(posted_txn)
        pending = await repository.get_transactions_by_status(TransactionStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].description == "Pending"

    async def test_get_pending_transactions(self, repository):
        """Test getting pending transactions."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_pending_test",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Pending",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        await repository.save_transaction(txn)
        pending = await repository.get_pending_transactions()
        assert len(pending) >= 1

    async def test_search_transactions_by_status(self, repository):
        """Test searching transactions by status."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_search_status",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Search",
            vendor_name="Vendor",
            status=TransactionStatus.CATEGORIZED,
            assigned_category_id=1,
            fetched_at=now,
        )
        await repository.save_transaction(txn)
        results = await repository.search_transactions(status=TransactionStatus.CATEGORIZED)
        assert len(results) >= 1

    async def test_search_transactions_by_text(self, repository):
        """Test searching transactions by text."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_search_text",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="UNIQUE_DESCRIPTION",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        await repository.save_transaction(txn)
        results = await repository.search_transactions(search_text="UNIQUE_DESC")
        assert len(results) == 1
        assert results[0].description == "UNIQUE_DESCRIPTION"

    async def test_search_transactions_by_vendor_name(self, repository):
        """Test searching transactions by vendor name."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_search_vendor",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Desc",
            vendor_name="UNIQUE_VENDOR",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        await repository.save_transaction(txn)
        results = await repository.search_transactions(search_text="UNIQUE_VEN")
        assert len(results) == 1

    async def test_search_transactions_by_amount(self, repository):
        """Test searching transactions by amount range."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_search_amount",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("150.00"),
            description="Amount test",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        await repository.save_transaction(txn)
        results = await repository.search_transactions(
            min_amount=Decimal("100.00"), max_amount=Decimal("200.00")
        )
        assert any(r.qbo_id == "txn_search_amount" for r in results)

    async def test_search_transactions_by_date(self, repository):
        """Test searching transactions by date range."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_search_date",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Date test",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        await repository.save_transaction(txn)
        results = await repository.search_transactions(
            start_date=now - timedelta(days=1), end_date=now + timedelta(days=1)
        )
        assert any(r.qbo_id == "txn_search_date" for r in results)

    async def test_search_transactions_no_filters(self, repository):
        """Test searching transactions with no filters returns all."""
        now = datetime.now()
        for i in range(3):
            txn = Transaction(
                id=None,
                qbo_id=f"txn_no_filter_{i}",
                account_id="acct",
                account_name="Account",
                date=now,
                amount=Decimal("100.00"),
                description=f"No filter {i}",
                vendor_name="Vendor",
                status=TransactionStatus.PENDING,
                assigned_category_id=None,
                fetched_at=now,
            )
            await repository.save_transaction(txn)
        results = await repository.search_transactions()
        assert len(results) >= 3

    async def test_update_transaction_status(self, repository):
        """Test updating transaction status."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_status_update",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Status update",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        saved = await repository.save_transaction(txn)
        await repository.update_transaction_status(
            saved.id, TransactionStatus.CATEGORIZED, category_id=5
        )
        updated = await repository.get_transaction_by_id(saved.id)
        assert updated.status == TransactionStatus.CATEGORIZED
        assert updated.assigned_category_id == 5

    async def test_delete_transaction(self, repository):
        """Test deleting a transaction."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_delete",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Delete",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        saved = await repository.save_transaction(txn)
        await repository.delete_transaction(saved.id)
        retrieved = await repository.get_transaction_by_id(saved.id)
        assert retrieved is None

    async def test_clear_posted_transactions(self, repository):
        """Test clearing all posted transactions."""
        now = datetime.now()
        pending_txn = Transaction(
            id=None,
            qbo_id="txn_clear_pending",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Pending",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        posted_txn = Transaction(
            id=None,
            qbo_id="txn_clear_posted",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("200.00"),
            description="Posted",
            vendor_name="Vendor",
            status=TransactionStatus.POSTED,
            assigned_category_id=1,
            fetched_at=now,
        )
        await repository.save_transaction(pending_txn)
        await repository.save_transaction(posted_txn)
        count = await repository.clear_posted_transactions()
        assert count >= 1
        pending = await repository.get_pending_transactions()
        assert any(t.qbo_id == "txn_clear_pending" for t in pending)


class TestTransactionSplitOperations:
    """Tests for transaction split CRUD operations."""

    async def test_save_new_split(self, repository):
        """Test saving a new transaction split."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_split",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Split test",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        saved_txn = await repository.save_transaction(txn)
        split = TransactionSplit(
            id=None,
            transaction_id=saved_txn.id,
            category_id=5,
            amount=Decimal("60.00"),
            memo="Split portion",
        )
        saved_split = await repository.save_transaction_split(split)
        assert saved_split.id is not None
        assert saved_split.amount == Decimal("60.00")

    async def test_update_existing_split(self, repository):
        """Test updating an existing split."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_split_update",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Split update",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        saved_txn = await repository.save_transaction(txn)
        split = TransactionSplit(
            id=None,
            transaction_id=saved_txn.id,
            category_id=5,
            amount=Decimal("60.00"),
            memo="Original",
        )
        saved_split = await repository.save_transaction_split(split)
        updated_split = TransactionSplit(
            id=saved_split.id,
            transaction_id=saved_txn.id,
            category_id=10,
            amount=Decimal("75.00"),
            memo="Updated",
        )
        updated = await repository.save_transaction_split(updated_split)
        assert updated.category_id == 10
        assert updated.memo == "Updated"

    async def test_get_split_by_id(self, repository):
        """Test getting a split by ID."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_split_get",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Split get",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        saved_txn = await repository.save_transaction(txn)
        split = TransactionSplit(
            id=None,
            transaction_id=saved_txn.id,
            category_id=5,
            amount=Decimal("60.00"),
            memo="Get test",
        )
        saved_split = await repository.save_transaction_split(split)
        retrieved = await repository.get_split_by_id(saved_split.id)
        assert retrieved is not None
        assert retrieved.memo == "Get test"

    async def test_get_split_by_id_not_found(self, repository):
        """Test getting a non-existent split by ID."""
        retrieved = await repository.get_split_by_id(99999)
        assert retrieved is None

    async def test_get_splits_for_transaction(self, repository):
        """Test getting all splits for a transaction."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_splits_list",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Splits list",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        saved_txn = await repository.save_transaction(txn)
        for i in range(3):
            split = TransactionSplit(
                id=None,
                transaction_id=saved_txn.id,
                category_id=i + 1,
                amount=Decimal("30.00"),
                memo=f"Split {i}",
            )
            await repository.save_transaction_split(split)
        splits = await repository.get_splits_for_transaction(saved_txn.id)
        assert len(splits) == 3

    async def test_delete_splits_for_transaction(self, repository):
        """Test deleting all splits for a transaction."""
        now = datetime.now()
        txn = Transaction(
            id=None,
            qbo_id="txn_splits_delete",
            account_id="acct",
            account_name="Account",
            date=now,
            amount=Decimal("100.00"),
            description="Splits delete",
            vendor_name="Vendor",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        saved_txn = await repository.save_transaction(txn)
        for i in range(2):
            split = TransactionSplit(
                id=None,
                transaction_id=saved_txn.id,
                category_id=i + 1,
                amount=Decimal("50.00"),
                memo=f"Split {i}",
            )
            await repository.save_transaction_split(split)
        await repository.delete_splits_for_transaction(saved_txn.id)
        splits = await repository.get_splits_for_transaction(saved_txn.id)
        assert len(splits) == 0


class TestSettingsOperations:
    """Tests for settings operations."""

    async def test_save_and_get_setting(self, repository):
        """Test saving and retrieving a setting."""
        await repository.save_setting('test_key', 'test_value')
        value = await repository.get_setting('test_key')
        assert value == 'test_value'

    async def test_get_setting_not_found(self, repository):
        """Test getting a setting that doesn't exist."""
        value = await repository.get_setting('nonexistent_key')
        assert value is None

    async def test_save_setting_upsert(self, repository):
        """Test that save_setting updates existing value."""
        await repository.save_setting('upsert_key', 'original')
        await repository.save_setting('upsert_key', 'updated')
        value = await repository.get_setting('upsert_key')
        assert value == 'updated'

    async def test_delete_setting(self, repository):
        """Test deleting a setting."""
        await repository.save_setting('delete_key', 'to_delete')
        await repository.delete_setting('delete_key')
        value = await repository.get_setting('delete_key')
        assert value is None

    async def test_delete_setting_nonexistent(self, repository):
        """Test deleting a setting that doesn't exist is safe."""
        await repository.delete_setting('nonexistent_delete_key')
