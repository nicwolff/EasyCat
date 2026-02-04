"""Tests for database models."""

from datetime import datetime
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


class TestToken:
    """Tests for Token model."""

    def test_create_token(self):
        """Test creating a Token instance."""
        now = datetime.now()
        token = Token(
            id=1,
            realm_id="realm123",
            access_token="access",
            refresh_token="refresh",
            expires_at=now,
            created_at=now,
            updated_at=now,
        )
        assert token.id == 1
        assert token.realm_id == "realm123"
        assert token.access_token == "access"
        assert token.refresh_token == "refresh"
        assert token.expires_at == now
        assert token.created_at == now
        assert token.updated_at == now

    def test_token_without_id(self):
        """Test creating a Token without an ID (for new tokens)."""
        now = datetime.now()
        token = Token(
            id=None,
            realm_id="realm123",
            access_token="access",
            refresh_token="refresh",
            expires_at=now,
            created_at=now,
            updated_at=now,
        )
        assert token.id is None


class TestCategory:
    """Tests for Category model."""

    def test_create_category(self):
        """Test creating a Category instance."""
        now = datetime.now()
        category = Category(
            id=1,
            qbo_id="qbo123",
            name="Office Supplies",
            full_name="Expenses:Office Supplies",
            parent_id="parent123",
            account_type="Expense",
            is_visible=True,
            display_order=10,
            synced_at=now,
        )
        assert category.id == 1
        assert category.qbo_id == "qbo123"
        assert category.name == "Office Supplies"
        assert category.full_name == "Expenses:Office Supplies"
        assert category.parent_id == "parent123"
        assert category.account_type == "Expense"
        assert category.is_visible is True
        assert category.display_order == 10
        assert category.synced_at == now

    def test_category_defaults(self):
        """Test Category default values."""
        now = datetime.now()
        category = Category(
            id=None,
            qbo_id="qbo123",
            name="Test",
            full_name="Test",
            parent_id=None,
            account_type="Expense",
            is_visible=True,
            display_order=0,
            synced_at=now,
        )
        assert category.parent_id is None
        assert category.display_order == 0


class TestRule:
    """Tests for Rule model."""

    def test_create_rule_with_contains_pattern(self):
        """Test creating a Rule with CONTAINS pattern type."""
        now = datetime.now()
        rule = Rule(
            id=1,
            name="Amazon Rule",
            pattern="AMAZON",
            pattern_type=PatternType.CONTAINS,
            category_id=5,
            min_amount=None,
            max_amount=None,
            priority=10,
            is_active=True,
            created_at=now,
        )
        assert rule.id == 1
        assert rule.name == "Amazon Rule"
        assert rule.pattern == "AMAZON"
        assert rule.pattern_type == PatternType.CONTAINS
        assert rule.category_id == 5
        assert rule.min_amount is None
        assert rule.max_amount is None
        assert rule.priority == 10
        assert rule.is_active is True

    def test_create_rule_with_regex_pattern(self):
        """Test creating a Rule with REGEX pattern type."""
        now = datetime.now()
        rule = Rule(
            id=2,
            name="Regex Rule",
            pattern=r"^AMZN.*MKTPLACE",
            pattern_type=PatternType.REGEX,
            category_id=5,
            min_amount=Decimal("10.00"),
            max_amount=Decimal("500.00"),
            priority=20,
            is_active=True,
            created_at=now,
        )
        assert rule.pattern_type == PatternType.REGEX
        assert rule.min_amount == Decimal("10.00")
        assert rule.max_amount == Decimal("500.00")

    def test_create_rule_with_exact_pattern(self):
        """Test creating a Rule with EXACT pattern type."""
        now = datetime.now()
        rule = Rule(
            id=3,
            name="Exact Rule",
            pattern="SPECIFIC VENDOR NAME",
            pattern_type=PatternType.EXACT,
            category_id=10,
            min_amount=None,
            max_amount=None,
            priority=30,
            is_active=False,
            created_at=now,
        )
        assert rule.pattern_type == PatternType.EXACT
        assert rule.is_active is False


class TestPatternType:
    """Tests for PatternType enum."""

    def test_pattern_type_values(self):
        """Test PatternType enum values."""
        assert PatternType.CONTAINS.value == "contains"
        assert PatternType.REGEX.value == "regex"
        assert PatternType.EXACT.value == "exact"

    def test_pattern_type_from_value(self):
        """Test creating PatternType from string value."""
        assert PatternType("contains") == PatternType.CONTAINS
        assert PatternType("regex") == PatternType.REGEX
        assert PatternType("exact") == PatternType.EXACT


class TestVendorMapping:
    """Tests for VendorMapping model."""

    def test_create_vendor_mapping(self):
        """Test creating a VendorMapping instance."""
        now = datetime.now()
        mapping = VendorMapping(
            id=1,
            vendor_name="AMAZON.COM",
            vendor_id="vendor123",
            default_category_id=5,
            created_at=now,
            updated_at=now,
        )
        assert mapping.id == 1
        assert mapping.vendor_name == "AMAZON.COM"
        assert mapping.vendor_id == "vendor123"
        assert mapping.default_category_id == 5

    def test_vendor_mapping_without_vendor_id(self):
        """Test VendorMapping without a QuickBooks vendor ID."""
        now = datetime.now()
        mapping = VendorMapping(
            id=2,
            vendor_name="LOCAL STORE",
            vendor_id=None,
            default_category_id=10,
            created_at=now,
            updated_at=now,
        )
        assert mapping.vendor_id is None


class TestTransaction:
    """Tests for Transaction model."""

    def test_create_transaction(self):
        """Test creating a Transaction instance."""
        now = datetime.now()
        txn = Transaction(
            id=1,
            qbo_id="txn123",
            account_id="acct456",
            account_name="Business Checking",
            date=now,
            amount=Decimal("125.50"),
            description="AMAZON MKTPLACE PMTS",
            vendor_name="Amazon",
            status=TransactionStatus.PENDING,
            assigned_category_id=None,
            fetched_at=now,
        )
        assert txn.id == 1
        assert txn.qbo_id == "txn123"
        assert txn.account_id == "acct456"
        assert txn.account_name == "Business Checking"
        assert txn.amount == Decimal("125.50")
        assert txn.status == TransactionStatus.PENDING
        assert txn.assigned_category_id is None

    def test_transaction_with_category(self):
        """Test Transaction with assigned category."""
        now = datetime.now()
        txn = Transaction(
            id=2,
            qbo_id="txn456",
            account_id="acct456",
            account_name="Business Checking",
            date=now,
            amount=Decimal("50.00"),
            description="Office supplies",
            vendor_name="Staples",
            status=TransactionStatus.CATEGORIZED,
            assigned_category_id=10,
            fetched_at=now,
        )
        assert txn.status == TransactionStatus.CATEGORIZED
        assert txn.assigned_category_id == 10


class TestTransactionStatus:
    """Tests for TransactionStatus enum."""

    def test_transaction_status_values(self):
        """Test TransactionStatus enum values."""
        assert TransactionStatus.PENDING.value == "pending"
        assert TransactionStatus.CATEGORIZED.value == "categorized"
        assert TransactionStatus.POSTED.value == "posted"

    def test_transaction_status_from_value(self):
        """Test creating TransactionStatus from string value."""
        assert TransactionStatus("pending") == TransactionStatus.PENDING
        assert TransactionStatus("categorized") == TransactionStatus.CATEGORIZED
        assert TransactionStatus("posted") == TransactionStatus.POSTED


class TestTransactionSplit:
    """Tests for TransactionSplit model."""

    def test_create_transaction_split(self):
        """Test creating a TransactionSplit instance."""
        split = TransactionSplit(
            id=1,
            transaction_id=10,
            category_id=5,
            amount=Decimal("75.00"),
            memo="Office supplies portion",
        )
        assert split.id == 1
        assert split.transaction_id == 10
        assert split.category_id == 5
        assert split.amount == Decimal("75.00")
        assert split.memo == "Office supplies portion"

    def test_transaction_split_without_memo(self):
        """Test TransactionSplit without a memo."""
        split = TransactionSplit(
            id=2,
            transaction_id=10,
            category_id=8,
            amount=Decimal("50.00"),
            memo=None,
        )
        assert split.memo is None
