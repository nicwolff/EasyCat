"""Tests for the QuickBooks sync module."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from easycat.api import QBOAccount, QBOLineItem, QBOTransaction
from easycat.api.sync import (
    _build_categorized_line_items,
    _qbo_transaction_to_model,
    post_categorized_transactions,
    sync_categories,
    sync_transactions,
)
from easycat.db.models import Category, Transaction, TransactionStatus


def make_qbo_account(
    id: str = "1",
    name: str = "Test Account",
    full_name: str = "Expenses:Test Account",
    account_type: str = "Expense",
) -> QBOAccount:
    """Create a test QBO account."""
    return QBOAccount(
        id=id,
        name=name,
        full_name=full_name,
        account_type=account_type,
        account_sub_type=None,
        parent_id=None,
        active=True,
        current_balance=None,
    )


def make_qbo_transaction(
    id: str = "1001",
    memo: str | None = "Test memo",
    entity_name: str | None = "Test Vendor",
) -> QBOTransaction:
    """Create a test QBO transaction."""
    return QBOTransaction(
        id=id,
        txn_date=datetime(2024, 1, 15),
        total_amount=Decimal("125.50"),
        account_id="acc1",
        account_name="Business Checking",
        doc_number="DOC001",
        memo=memo,
        entity_name=entity_name,
        entity_id="v1" if entity_name else None,
        line_items=[
            QBOLineItem(
                id="1",
                amount=Decimal("125.50"),
                description="Line item description",
                account_id="exp1",
                account_name="Uncategorized Expense",
            )
        ],
    )


def make_category(
    id: int = 1,
    qbo_id: str = "1",
    name: str = "Test Category",
    full_name: str = "Expenses:Test Category",
) -> Category:
    """Create a test category."""
    return Category(
        id=id,
        qbo_id=qbo_id,
        name=name,
        full_name=full_name,
        parent_id=None,
        account_type="Expense",
        is_visible=True,
        display_order=0,
        synced_at=datetime.now(),
    )


def make_transaction(
    id: int = 1,
    qbo_id: str = "1001",
    status: TransactionStatus = TransactionStatus.CATEGORIZED,
    assigned_category_id: int | None = 5,
) -> Transaction:
    """Create a test transaction."""
    return Transaction(
        id=id,
        qbo_id=qbo_id,
        account_id="acc1",
        account_name="Test Account",
        date=datetime(2024, 1, 15),
        amount=Decimal("-100.00"),
        description="Test Transaction",
        vendor_name="Test Vendor",
        status=status,
        assigned_category_id=assigned_category_id,
    )


class TestSyncCategories:
    """Tests for sync_categories function."""

    @pytest.mark.asyncio
    async def test_sync_categories_saves_all(self):
        """Test that sync_categories saves all fetched categories."""
        mock_client = AsyncMock()
        mock_client.get_all_categorization_accounts.return_value = [
            make_qbo_account(id="1", name="Advertising"),
            make_qbo_account(id="2", name="Travel"),
        ]

        mock_repo = AsyncMock()
        mock_repo.save_category.side_effect = [
            make_category(id=1, qbo_id="1", name="Advertising"),
            make_category(id=2, qbo_id="2", name="Travel"),
        ]

        result = await sync_categories(mock_client, mock_repo)

        assert len(result) == 2
        assert mock_repo.save_category.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_categories_empty_list(self):
        """Test sync_categories with no accounts."""
        mock_client = AsyncMock()
        mock_client.get_all_categorization_accounts.return_value = []

        mock_repo = AsyncMock()

        result = await sync_categories(mock_client, mock_repo)

        assert len(result) == 0
        mock_repo.save_category.assert_not_called()


class TestSyncTransactions:
    """Tests for sync_transactions function."""

    @pytest.mark.asyncio
    async def test_sync_transactions_saves_all(self):
        """Test that sync_transactions saves all fetched transactions."""
        mock_client = AsyncMock()
        mock_client.get_uncategorized_transactions.return_value = [
            make_qbo_transaction(id='1001'),
            make_qbo_transaction(id='1002'),
        ]

        mock_repo = AsyncMock()
        mock_repo.get_all_categories.return_value = []
        mock_repo.save_transaction.side_effect = [
            make_transaction(id=1, qbo_id='1001'),
            make_transaction(id=2, qbo_id='1002'),
        ]

        result = await sync_transactions(mock_client, mock_repo)

        assert len(result) == 2
        assert mock_repo.save_transaction.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_transactions_with_date_range(self):
        """Test sync_transactions passes date range to client."""
        mock_client = AsyncMock()
        mock_client.get_uncategorized_transactions.return_value = []

        mock_repo = AsyncMock()
        mock_repo.get_all_categories.return_value = []

        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        await sync_transactions(mock_client, mock_repo, start, end)

        mock_client.get_uncategorized_transactions.assert_called_once_with(start, end)


class TestPostCategorizedTransactions:
    """Tests for post_categorized_transactions function."""

    @pytest.mark.asyncio
    async def test_post_categorized_transactions_success(self):
        """Test successfully posting categorized transactions."""
        txn = make_transaction(id=1, qbo_id="1001", assigned_category_id=5)
        category = make_category(id=5, qbo_id="cat5", name="Office Supplies")

        mock_client = AsyncMock()
        mock_client.get_purchase_raw.return_value = {
            "Id": "1001",
            "SyncToken": "0",
            "Line": [
                {
                    "Id": "1",
                    "Amount": 100.00,
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "Description": "Test",
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": {"value": "old", "name": "Old Category"}
                    },
                }
            ],
        }
        mock_client.update_purchase.return_value = {}

        mock_repo = AsyncMock()
        mock_repo.get_transactions_by_status.return_value = [txn]
        mock_repo.get_category_by_id.return_value = category

        result = await post_categorized_transactions(mock_client, mock_repo)

        assert len(result) == 1
        mock_client.update_purchase.assert_called_once()
        mock_repo.update_transaction_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_categorized_transactions_no_category_id(self):
        """Test posting skips transactions without category ID."""
        txn = make_transaction(id=1, qbo_id="1001", assigned_category_id=None)

        mock_client = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.get_transactions_by_status.return_value = [txn]

        result = await post_categorized_transactions(mock_client, mock_repo)

        assert len(result) == 0
        mock_client.update_purchase.assert_not_called()

    @pytest.mark.asyncio
    async def test_post_categorized_transactions_category_not_found(self):
        """Test posting skips transactions when category not found."""
        txn = make_transaction(id=1, qbo_id="1001", assigned_category_id=5)

        mock_client = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.get_transactions_by_status.return_value = [txn]
        mock_repo.get_category_by_id.return_value = None

        result = await post_categorized_transactions(mock_client, mock_repo)

        assert len(result) == 0
        mock_client.update_purchase.assert_not_called()

    @pytest.mark.asyncio
    async def test_post_categorized_transactions_api_error(self):
        """Test posting continues on API error."""
        txn = make_transaction(id=1, qbo_id="1001", assigned_category_id=5)
        category = make_category(id=5, qbo_id="cat5")

        mock_client = AsyncMock()
        mock_client.get_purchase_raw.side_effect = Exception("API Error")

        mock_repo = AsyncMock()
        mock_repo.get_transactions_by_status.return_value = [txn]
        mock_repo.get_category_by_id.return_value = category

        result = await post_categorized_transactions(mock_client, mock_repo)

        assert len(result) == 0


class TestQboTransactionToModel:
    """Tests for _qbo_transaction_to_model function."""

    def test_converts_basic_fields(self):
        """Test basic field conversion."""
        qbo_txn = make_qbo_transaction(id='1001', entity_name='Amazon')
        result = _qbo_transaction_to_model(qbo_txn, {})

        assert result.qbo_id == '1001'
        assert result.account_id == 'acc1'
        assert result.account_name == 'Business Checking'
        assert result.vendor_name == 'Amazon'
        assert result.status == TransactionStatus.PENDING
        assert result.amount == Decimal('-125.50')

    def test_uses_line_item_description(self):
        """Test that line item description is used when available."""
        qbo_txn = make_qbo_transaction(memo=None)
        result = _qbo_transaction_to_model(qbo_txn, {})

        assert result.description == 'Line item description'

    def test_uses_memo_when_no_line_description(self):
        """Test that memo is used when line item has no description."""
        qbo_txn = QBOTransaction(
            id='1001',
            txn_date=datetime(2024, 1, 15),
            total_amount=Decimal('100.00'),
            account_id='acc1',
            account_name='Checking',
            doc_number=None,
            memo='Memo description',
            entity_name=None,
            entity_id=None,
            line_items=[
                QBOLineItem(
                    id='1',
                    amount=Decimal('100.00'),
                    description=None,
                    account_id=None,
                    account_name=None,
                )
            ],
        )
        result = _qbo_transaction_to_model(qbo_txn, {})

        assert result.description == 'Memo description'

    def test_fallback_description(self):
        """Test fallback description when no memo or line description."""
        qbo_txn = QBOTransaction(
            id='1001',
            txn_date=datetime(2024, 1, 15),
            total_amount=Decimal('100.00'),
            account_id='acc1',
            account_name='Checking',
            doc_number='DOC123',
            memo=None,
            entity_name=None,
            entity_id=None,
            line_items=[],
        )
        result = _qbo_transaction_to_model(qbo_txn, {})

        assert result.description == 'Purchase DOC123'

    def test_fallback_description_no_doc_number(self):
        """Test fallback description with no doc number."""
        qbo_txn = QBOTransaction(
            id='1001',
            txn_date=datetime(2024, 1, 15),
            total_amount=Decimal('100.00'),
            account_id='acc1',
            account_name='Checking',
            doc_number=None,
            memo=None,
            entity_name=None,
            entity_id=None,
            line_items=[],
        )
        result = _qbo_transaction_to_model(qbo_txn, {})

        assert result.description == 'Purchase 1001'
        assert result.status == TransactionStatus.PENDING

    def test_assigns_category_from_line_item(self):
        """Test that category is assigned from line item account."""
        category = make_category(id=5, qbo_id='cat5', name='Office Supplies')
        qbo_txn = QBOTransaction(
            id='1001',
            txn_date=datetime(2024, 1, 15),
            total_amount=Decimal('100.00'),
            account_id='acc1',
            account_name='Checking',
            doc_number=None,
            memo='Test',
            entity_name=None,
            entity_id=None,
            line_items=[
                QBOLineItem(
                    id='1',
                    amount=Decimal('100.00'),
                    description='Test item',
                    account_id='cat5',
                    account_name='Office Supplies',
                )
            ],
        )
        result = _qbo_transaction_to_model(qbo_txn, {'cat5': category})

        assert result.assigned_category_id == 5
        assert result.status == TransactionStatus.PENDING

    def test_no_category_when_not_in_lookup(self):
        """Test that no category is assigned when not in lookup."""
        qbo_txn = QBOTransaction(
            id='1001',
            txn_date=datetime(2024, 1, 15),
            total_amount=Decimal('100.00'),
            account_id='acc1',
            account_name='Checking',
            doc_number=None,
            memo='Test',
            entity_name=None,
            entity_id=None,
            line_items=[
                QBOLineItem(
                    id='1',
                    amount=Decimal('100.00'),
                    description='Test item',
                    account_id='unknown_cat',
                    account_name='Unknown Category',
                )
            ],
        )
        result = _qbo_transaction_to_model(qbo_txn, {})

        assert result.assigned_category_id is None
        assert result.status == TransactionStatus.PENDING


class TestBuildCategorizedLineItems:
    """Tests for _build_categorized_line_items function."""

    def test_updates_account_ref(self):
        """Test that AccountRef is updated with new category."""
        purchase = {
            "Line": [
                {
                    "Id": "1",
                    "Amount": 100.00,
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "Description": "Test item",
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": {"value": "old", "name": "Old Category"}
                    },
                }
            ]
        }
        category = make_category(qbo_id="new_cat", full_name="Expenses:New Category")

        result = _build_categorized_line_items(purchase, category)

        assert len(result) == 1
        assert result[0]["AccountBasedExpenseLineDetail"]["AccountRef"]["value"] == "new_cat"
        assert result[0]["AccountBasedExpenseLineDetail"]["AccountRef"]["name"] == (
            "Expenses:New Category"
        )
        assert result[0]["Description"] == "Test item"

    def test_preserves_non_expense_lines(self):
        """Test that non-expense line items are preserved."""
        purchase = {
            "Line": [
                {
                    "Id": "1",
                    "Amount": 100.00,
                    "DetailType": "ItemBasedExpenseLineDetail",
                    "ItemBasedExpenseLineDetail": {},
                }
            ]
        }
        category = make_category()

        result = _build_categorized_line_items(purchase, category)

        assert len(result) == 1
        assert result[0]["DetailType"] == "ItemBasedExpenseLineDetail"

    def test_handles_line_without_description(self):
        """Test handling line items without description."""
        purchase = {
            "Line": [
                {
                    "Id": "1",
                    "Amount": 100.00,
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": {"value": "old", "name": "Old"}
                    },
                }
            ]
        }
        category = make_category(qbo_id="new_cat")

        result = _build_categorized_line_items(purchase, category)

        assert "Description" not in result[0]
