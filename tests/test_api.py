"""Tests for QuickBooks API client."""

from datetime import datetime
from decimal import Decimal

import httpx
import pytest
import respx

from easycat.api import (
    API_VERSION,
    PRODUCTION_BASE_URL,
    SANDBOX_BASE_URL,
    AccountType,
    QBOAccount,
    QBOLineItem,
    QBOTransaction,
    QBOVendor,
    QuickBooksAPIError,
    QuickBooksClient,
)
from easycat.config import QuickBooksConfig


@pytest.fixture
def sandbox_config():
    """Create a sandbox QuickBooks config."""
    return QuickBooksConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        environment="sandbox",
        redirect_uri="http://localhost:8085/callback",
    )


@pytest.fixture
def production_config():
    """Create a production QuickBooks config."""
    return QuickBooksConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        environment="production",
        redirect_uri="http://localhost:8085/callback",
    )


class TestAccountType:
    """Tests for AccountType enum."""

    def test_account_type_values(self):
        """Test AccountType enum values."""
        assert AccountType.EXPENSE.value == "Expense"
        assert AccountType.OTHER_EXPENSE.value == "Other Expense"
        assert AccountType.COST_OF_GOODS_SOLD.value == "Cost of Goods Sold"
        assert AccountType.INCOME.value == "Income"
        assert AccountType.OTHER_INCOME.value == "Other Income"
        assert AccountType.BANK.value == "Bank"
        assert AccountType.CREDIT_CARD.value == "Credit Card"


class TestQBODataclasses:
    """Tests for QBO dataclasses."""

    def test_qbo_account(self):
        """Test QBOAccount dataclass."""
        account = QBOAccount(
            id="1",
            name="Office Supplies",
            full_name="Expenses:Office Supplies",
            account_type="Expense",
            account_sub_type="OfficeGeneralAdministrativeExpenses",
            parent_id="100",
            active=True,
            current_balance=Decimal("500.00"),
        )
        assert account.id == "1"
        assert account.name == "Office Supplies"
        assert account.current_balance == Decimal("500.00")

    def test_qbo_transaction(self):
        """Test QBOTransaction dataclass."""
        txn = QBOTransaction(
            id="123",
            txn_date=datetime(2024, 1, 15),
            total_amount=Decimal("99.99"),
            account_id="1",
            account_name="Business Checking",
            doc_number="1001",
            memo="Office supplies purchase",
            entity_name="Amazon",
            entity_id="456",
            line_items=[],
        )
        assert txn.id == "123"
        assert txn.total_amount == Decimal("99.99")
        assert txn.entity_name == "Amazon"

    def test_qbo_line_item(self):
        """Test QBOLineItem dataclass."""
        item = QBOLineItem(
            id="1",
            amount=Decimal("50.00"),
            description="Printer paper",
            account_id="10",
            account_name="Office Supplies",
        )
        assert item.id == "1"
        assert item.amount == Decimal("50.00")

    def test_qbo_vendor(self):
        """Test QBOVendor dataclass."""
        vendor = QBOVendor(
            id="789",
            display_name="Amazon",
            active=True,
        )
        assert vendor.id == "789"
        assert vendor.display_name == "Amazon"


class TestQuickBooksClient:
    """Tests for QuickBooksClient."""

    def test_init_sandbox(self, sandbox_config):
        """Test client initialization with sandbox config."""
        client = QuickBooksClient(sandbox_config, "realm123", "access_token")
        assert client._base_url == SANDBOX_BASE_URL
        assert client._realm_id == "realm123"
        assert client._access_token == "access_token"

    def test_init_production(self, production_config):
        """Test client initialization with production config."""
        client = QuickBooksClient(production_config, "realm123", "access_token")
        assert client._base_url == PRODUCTION_BASE_URL

    def test_get_headers(self, sandbox_config):
        """Test header generation."""
        client = QuickBooksClient(sandbox_config, "realm123", "my_token")
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer my_token"
        assert headers["Accept"] == "application/json"
        assert headers["Content-Type"] == "application/json"

    def test_build_url(self, sandbox_config):
        """Test URL building."""
        client = QuickBooksClient(sandbox_config, "realm123", "token")
        url = client._build_url("query")
        assert url == f"/{API_VERSION}/company/realm123/query"

    @respx.mock
    async def test_context_manager(self, sandbox_config):
        """Test async context manager."""
        async with QuickBooksClient(sandbox_config, "realm123", "token") as client:
            assert client._client is not None
        assert client._client is None

    async def test_context_manager_exit_without_client(self, sandbox_config):
        """Test __aexit__ when client is None."""
        client = QuickBooksClient(sandbox_config, "realm123", "token")
        assert client._client is None
        await client.__aexit__(None, None, None)
        assert client._client is None

    @respx.mock
    async def test_get_expense_accounts(self, sandbox_config):
        """Test fetching expense accounts."""
        respx.get(f"{SANDBOX_BASE_URL}/{API_VERSION}/company/realm123/query").mock(
            return_value=httpx.Response(
                200,
                json={
                    "QueryResponse": {
                        "Account": [
                            {
                                "Id": "1",
                                "Name": "Office Supplies",
                                "FullyQualifiedName": "Office Supplies",
                                "AccountType": "Expense",
                                "AccountSubType": "OfficeGeneralAdministrativeExpenses",
                                "Active": True,
                                "CurrentBalance": 500.00,
                            },
                            {
                                "Id": "2",
                                "Name": "Travel",
                                "FullyQualifiedName": "Travel",
                                "AccountType": "Expense",
                                "Active": True,
                            },
                        ]
                    }
                },
            )
        )
        async with QuickBooksClient(sandbox_config, "realm123", "token") as client:
            accounts = await client.get_expense_accounts()
        assert len(accounts) == 2
        assert accounts[0].name == "Office Supplies"
        assert accounts[0].current_balance == Decimal("500")
        assert accounts[1].current_balance is None

    @respx.mock
    async def test_get_income_accounts(self, sandbox_config):
        """Test fetching income accounts."""
        respx.get(f"{SANDBOX_BASE_URL}/{API_VERSION}/company/realm123/query").mock(
            return_value=httpx.Response(
                200,
                json={
                    "QueryResponse": {
                        "Account": [
                            {
                                "Id": "10",
                                "Name": "Sales",
                                "FullyQualifiedName": "Sales",
                                "AccountType": "Income",
                                "Active": True,
                            },
                        ]
                    }
                },
            )
        )
        async with QuickBooksClient(sandbox_config, "realm123", "token") as client:
            accounts = await client.get_income_accounts()
        assert len(accounts) == 1
        assert accounts[0].account_type == "Income"

    @respx.mock
    async def test_get_bank_accounts(self, sandbox_config):
        """Test fetching bank accounts."""
        respx.get(f"{SANDBOX_BASE_URL}/{API_VERSION}/company/realm123/query").mock(
            return_value=httpx.Response(
                200,
                json={
                    "QueryResponse": {
                        "Account": [
                            {
                                "Id": "20",
                                "Name": "Business Checking",
                                "FullyQualifiedName": "Business Checking",
                                "AccountType": "Bank",
                                "Active": True,
                                "CurrentBalance": 10000.00,
                            },
                        ]
                    }
                },
            )
        )
        async with QuickBooksClient(sandbox_config, "realm123", "token") as client:
            accounts = await client.get_bank_accounts()
        assert len(accounts) == 1
        assert accounts[0].account_type == "Bank"

    @respx.mock
    async def test_get_all_categorization_accounts(self, sandbox_config):
        """Test fetching all categorization accounts."""
        respx.get(f"{SANDBOX_BASE_URL}/{API_VERSION}/company/realm123/query").mock(
            return_value=httpx.Response(
                200,
                json={
                    "QueryResponse": {
                        "Account": [
                            {
                                "Id": "1",
                                "Name": "Expense1",
                                "FullyQualifiedName": "Expense1",
                                "AccountType": "Expense",
                                "Active": True,
                            },
                            {
                                "Id": "2",
                                "Name": "Income1",
                                "FullyQualifiedName": "Income1",
                                "AccountType": "Income",
                                "Active": True,
                            },
                        ]
                    }
                },
            )
        )
        async with QuickBooksClient(sandbox_config, "realm123", "token") as client:
            accounts = await client.get_all_categorization_accounts()
        assert len(accounts) == 2

    @respx.mock
    async def test_get_uncategorized_transactions(self, sandbox_config):
        """Test fetching uncategorized transactions."""
        respx.get(f"{SANDBOX_BASE_URL}/{API_VERSION}/company/realm123/query").mock(
            return_value=httpx.Response(
                200,
                json={
                    "QueryResponse": {
                        "Purchase": [
                            {
                                "Id": "100",
                                "TxnDate": "2024-01-15",
                                "TotalAmt": 99.99,
                                "AccountRef": {"value": "1", "name": "Checking"},
                                "EntityRef": {"value": "50", "name": "Amazon"},
                                "DocNumber": "1001",
                                "PrivateNote": "Office supplies",
                                "Line": [
                                    {
                                        "Id": "1",
                                        "Amount": 99.99,
                                        "Description": "Supplies",
                                        "AccountBasedExpenseLineDetail": {
                                            "AccountRef": {"value": "10", "name": "Office Supplies"}
                                        },
                                    }
                                ],
                            }
                        ]
                    }
                },
            )
        )
        async with QuickBooksClient(sandbox_config, "realm123", "token") as client:
            transactions = await client.get_uncategorized_transactions()
        assert len(transactions) == 1
        assert transactions[0].id == "100"
        assert transactions[0].entity_name == "Amazon"
        assert len(transactions[0].line_items) == 1
        assert transactions[0].line_items[0].account_name == "Office Supplies"

    @respx.mock
    async def test_get_uncategorized_transactions_with_dates(self, sandbox_config):
        """Test fetching transactions with date filters."""
        respx.get(f"{SANDBOX_BASE_URL}/{API_VERSION}/company/realm123/query").mock(
            return_value=httpx.Response(200, json={"QueryResponse": {"Purchase": []}})
        )
        async with QuickBooksClient(sandbox_config, "realm123", "token") as client:
            start = datetime(2024, 1, 1)
            end = datetime(2024, 1, 31)
            transactions = await client.get_uncategorized_transactions(
                start_date=start,
                end_date=end,
            )
        assert len(transactions) == 0

    @respx.mock
    async def test_get_vendors(self, sandbox_config):
        """Test fetching vendors."""
        respx.get(f"{SANDBOX_BASE_URL}/{API_VERSION}/company/realm123/query").mock(
            return_value=httpx.Response(
                200,
                json={
                    "QueryResponse": {
                        "Vendor": [
                            {"Id": "1", "DisplayName": "Amazon", "Active": True},
                            {"Id": "2", "DisplayName": "Office Depot", "Active": True},
                        ]
                    }
                },
            )
        )
        async with QuickBooksClient(sandbox_config, "realm123", "token") as client:
            vendors = await client.get_vendors()
        assert len(vendors) == 2
        assert vendors[0].display_name == "Amazon"

    @respx.mock
    async def test_get_purchase(self, sandbox_config):
        """Test fetching a single purchase."""
        respx.get(f"{SANDBOX_BASE_URL}/{API_VERSION}/company/realm123/purchase/100").mock(
            return_value=httpx.Response(
                200,
                json={
                    "Purchase": {
                        "Id": "100",
                        "TxnDate": "2024-01-15",
                        "TotalAmt": 50.00,
                        "AccountRef": {"value": "1", "name": "Checking"},
                        "Line": [],
                    }
                },
            )
        )
        async with QuickBooksClient(sandbox_config, "realm123", "token") as client:
            purchase = await client.get_purchase("100")
        assert purchase.id == "100"
        assert purchase.total_amount == Decimal("50")

    @respx.mock
    async def test_get_purchase_raw(self, sandbox_config):
        """Test fetching a single purchase as raw dict."""
        respx.get(f"{SANDBOX_BASE_URL}/{API_VERSION}/company/realm123/purchase/100").mock(
            return_value=httpx.Response(
                200,
                json={
                    "Purchase": {
                        "Id": "100",
                        "SyncToken": "0",
                        "TxnDate": "2024-01-15",
                        "TotalAmt": 50.00,
                    }
                },
            )
        )
        async with QuickBooksClient(sandbox_config, "realm123", "token") as client:
            purchase = await client.get_purchase_raw("100")
        assert purchase["Id"] == "100"
        assert purchase["SyncToken"] == "0"

    @respx.mock
    async def test_update_purchase(self, sandbox_config):
        """Test updating a purchase."""
        respx.post(f"{SANDBOX_BASE_URL}/{API_VERSION}/company/realm123/purchase").mock(
            return_value=httpx.Response(
                200,
                json={
                    "Purchase": {
                        "Id": "100",
                        "SyncToken": "1",
                        "TxnDate": "2024-01-15",
                        "TotalAmt": 50.00,
                    }
                },
            )
        )
        async with QuickBooksClient(sandbox_config, "realm123", "token") as client:
            purchase = {
                "Id": "100",
                "SyncToken": "0",
                "PaymentType": "CreditCard",
                "AccountRef": {"value": "41", "name": "Credit Card"},
            }
            result = await client.update_purchase(
                purchase=purchase,
                line_items=[{"Amount": 50.00}],
            )
        assert result["Id"] == "100"
        assert result["SyncToken"] == "1"

    @respx.mock
    async def test_empty_query_response(self, sandbox_config):
        """Test handling empty query response."""
        respx.get(f"{SANDBOX_BASE_URL}/{API_VERSION}/company/realm123/query").mock(
            return_value=httpx.Response(200, json={"QueryResponse": {}})
        )
        async with QuickBooksClient(sandbox_config, "realm123", "token") as client:
            accounts = await client.get_expense_accounts()
        assert accounts == []

    def test_parse_account_with_parent(self, sandbox_config):
        """Test parsing account with parent reference."""
        client = QuickBooksClient(sandbox_config, "realm123", "token")
        data = {
            "Id": "5",
            "Name": "Sub Account",
            "FullyQualifiedName": "Parent:Sub Account",
            "AccountType": "Expense",
            "ParentRef": {"value": "1", "name": "Parent"},
            "Active": True,
        }
        account = client._parse_account(data)
        assert account.parent_id == "1"
        assert account.full_name == "Parent:Sub Account"

    def test_parse_account_without_optional_fields(self, sandbox_config):
        """Test parsing account without optional fields."""
        client = QuickBooksClient(sandbox_config, "realm123", "token")
        data = {
            "Id": "5",
            "Name": "Simple Account",
            "AccountType": "Expense",
        }
        account = client._parse_account(data)
        assert account.full_name == "Simple Account"
        assert account.account_sub_type is None
        assert account.parent_id is None
        assert account.current_balance is None
        assert account.active is True

    def test_parse_purchase_without_entity(self, sandbox_config):
        """Test parsing purchase without entity reference."""
        client = QuickBooksClient(sandbox_config, "realm123", "token")
        data = {
            "Id": "100",
            "TxnDate": "2024-01-15",
            "TotalAmt": 50.00,
            "AccountRef": {"value": "1", "name": "Checking"},
            "Line": [],
        }
        txn = client._parse_purchase(data)
        assert txn.entity_name is None
        assert txn.entity_id is None

    def test_parse_line_item_without_account(self, sandbox_config):
        """Test parsing line item without account reference."""
        client = QuickBooksClient(sandbox_config, "realm123", "token")
        data = {
            "Amount": 25.00,
            "Description": "Miscellaneous",
        }
        item = client._parse_line_item(data)
        assert item.account_id is None
        assert item.account_name is None
        assert item.id is None

    def test_parse_vendor_default_active(self, sandbox_config):
        """Test parsing vendor with default active status."""
        client = QuickBooksClient(sandbox_config, "realm123", "token")
        data = {
            "Id": "1",
            "DisplayName": "Test Vendor",
        }
        vendor = client._parse_vendor(data)
        assert vendor.active is True

    @respx.mock
    async def test_create_account(self, sandbox_config):
        """Test creating a new account."""
        respx.post(f'{SANDBOX_BASE_URL}/{API_VERSION}/company/realm123/account').mock(
            return_value=httpx.Response(
                200,
                json={
                    'Account': {
                        'Id': '123',
                        'Name': 'New Expense',
                        'FullyQualifiedName': 'New Expense',
                        'AccountType': 'Expense',
                        'Active': True,
                    }
                },
            )
        )
        async with QuickBooksClient(sandbox_config, 'realm123', 'token') as client:
            account = await client.create_account('New Expense')
        assert account.id == '123'
        assert account.name == 'New Expense'
        assert account.account_type == 'Expense'

    @respx.mock
    async def test_create_account_with_parent(self, sandbox_config):
        """Test creating a subcategory account."""
        respx.post(f'{SANDBOX_BASE_URL}/{API_VERSION}/company/realm123/account').mock(
            return_value=httpx.Response(
                200,
                json={
                    'Account': {
                        'Id': '124',
                        'Name': 'Sub Category',
                        'FullyQualifiedName': 'Parent:Sub Category',
                        'AccountType': 'Expense',
                        'AccountSubType': 'SuppliesMaterials',
                        'ParentRef': {'value': '100'},
                        'Active': True,
                    }
                },
            )
        )
        async with QuickBooksClient(sandbox_config, 'realm123', 'token') as client:
            account = await client.create_account('Sub Category', 'Expense', '100')
        assert account.id == '124'
        assert account.name == 'Sub Category'
        assert account.parent_id == '100'


class TestQuickBooksAPIError:
    """Tests for QuickBooksAPIError."""

    def test_error_with_status_code(self):
        """Test error with status code."""
        error = QuickBooksAPIError("Not found", status_code=404)
        assert str(error) == "Not found"
        assert error.status_code == 404

    def test_error_without_status_code(self):
        """Test error without status code."""
        error = QuickBooksAPIError("Unknown error")
        assert str(error) == "Unknown error"
        assert error.status_code is None
