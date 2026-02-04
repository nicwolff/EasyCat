"""QuickBooks API client module."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

import httpx

from easycat.config import QuickBooksConfig

SANDBOX_BASE_URL = "https://sandbox-quickbooks.api.intuit.com"
PRODUCTION_BASE_URL = "https://quickbooks.api.intuit.com"
API_VERSION = "v3"
MINOR_VERSION = "75"


class AccountType(Enum):
    """QuickBooks account types relevant for categorization."""

    EXPENSE = "Expense"
    OTHER_EXPENSE = "Other Expense"
    COST_OF_GOODS_SOLD = "Cost of Goods Sold"
    INCOME = "Income"
    OTHER_INCOME = "Other Income"
    BANK = "Bank"
    CREDIT_CARD = "Credit Card"


@dataclass
class QBOAccount:
    """QuickBooks Online account."""

    id: str
    name: str
    full_name: str
    account_type: str
    account_sub_type: str | None
    parent_id: str | None
    active: bool
    current_balance: Decimal | None


@dataclass
class QBOTransaction:
    """QuickBooks Online transaction (Purchase/Expense)."""

    id: str
    txn_date: datetime
    total_amount: Decimal
    account_id: str
    account_name: str
    doc_number: str | None
    memo: str | None
    entity_name: str | None
    entity_id: str | None
    line_items: list["QBOLineItem"]


@dataclass
class QBOLineItem:
    """Line item within a transaction."""

    id: str | None
    amount: Decimal
    description: str | None
    account_id: str | None
    account_name: str | None


@dataclass
class QBOVendor:
    """QuickBooks Online vendor."""

    id: str
    display_name: str
    active: bool


class QuickBooksClient:
    """Async client for QuickBooks Online API."""

    def __init__(self, config: QuickBooksConfig, realm_id: str, access_token: str):
        self._config = config
        self._realm_id = realm_id
        self._access_token = access_token
        self._base_url = SANDBOX_BASE_URL if config.is_sandbox else PRODUCTION_BASE_URL
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "QuickBooksClient":
        """Enter async context."""
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._get_headers(),
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authorization."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _build_url(self, endpoint: str) -> str:
        """Build API URL with realm ID."""
        return f"/{API_VERSION}/company/{self._realm_id}/{endpoint}"

    async def _query(self, query: str) -> list[dict]:
        """Execute a query against the QuickBooks API."""
        url = self._build_url("query")
        params = {"query": query, "minorversion": MINOR_VERSION}
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("QueryResponse", {})

    async def get_expense_accounts(self) -> list[QBOAccount]:
        """Fetch all expense-type accounts for categorization."""
        query = (
            "SELECT * FROM Account WHERE AccountType IN "
            "('Expense', 'Other Expense', 'Cost of Goods Sold') "
            "AND Active = true"
        )
        response = await self._query(query)
        accounts = response.get("Account", [])
        return [self._parse_account(a) for a in accounts]

    async def get_income_accounts(self) -> list[QBOAccount]:
        """Fetch all income-type accounts."""
        query = (
            "SELECT * FROM Account WHERE AccountType IN "
            "('Income', 'Other Income') AND Active = true"
        )
        response = await self._query(query)
        accounts = response.get("Account", [])
        return [self._parse_account(a) for a in accounts]

    async def get_bank_accounts(self) -> list[QBOAccount]:
        """Fetch all bank and credit card accounts."""
        query = (
            "SELECT * FROM Account WHERE AccountType IN ('Bank', 'Credit Card') AND Active = true"
        )
        response = await self._query(query)
        accounts = response.get("Account", [])
        return [self._parse_account(a) for a in accounts]

    async def get_all_categorization_accounts(self) -> list[QBOAccount]:
        """Fetch all accounts that can be used for categorization."""
        query = (
            "SELECT * FROM Account WHERE AccountType IN "
            "('Expense', 'Other Expense', 'Cost of Goods Sold', "
            "'Income', 'Other Income') AND Active = true"
        )
        response = await self._query(query)
        accounts = response.get("Account", [])
        return [self._parse_account(a) for a in accounts]

    async def get_uncategorized_transactions(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[QBOTransaction]:
        """Fetch purchases that need categorization."""
        query = "SELECT * FROM Purchase"
        conditions = []
        if start_date:
            conditions.append(f"TxnDate >= '{start_date.strftime('%Y-%m-%d')}'")
        if end_date:
            conditions.append(f"TxnDate <= '{end_date.strftime('%Y-%m-%d')}'")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDERBY TxnDate ASC MAXRESULTS 1000"
        response = await self._query(query)
        purchases = response.get("Purchase", [])
        return [self._parse_purchase(p) for p in purchases]

    async def get_vendors(self) -> list[QBOVendor]:
        """Fetch all active vendors."""
        query = "SELECT * FROM Vendor WHERE Active = true MAXRESULTS 1000"
        response = await self._query(query)
        vendors = response.get("Vendor", [])
        return [self._parse_vendor(v) for v in vendors]

    async def update_purchase(
        self,
        purchase: dict,
        line_items: list[dict],
    ) -> dict:
        """Update a purchase with new line items (categories)."""
        import logging
        log = logging.getLogger('easycat.api')

        url = self._build_url('purchase')
        params = {'minorversion': MINOR_VERSION}
        payload = {
            'Id': purchase['Id'],
            'SyncToken': purchase.get('SyncToken', '0'),
            'PaymentType': purchase['PaymentType'],
            'AccountRef': purchase['AccountRef'],
            'Line': line_items,
            'sparse': True,
        }
        log.debug(f'Update purchase payload: {payload}')
        response = await self._client.post(url, params=params, json=payload)
        if response.status_code >= 400:  # pragma: no cover
            log.error(f'QBO error response: {response.text}')
        response.raise_for_status()
        return response.json().get('Purchase', {})

    async def get_purchase(self, purchase_id: str) -> QBOTransaction:
        """Fetch a single purchase by ID."""
        url = self._build_url(f"purchase/{purchase_id}")
        params = {"minorversion": MINOR_VERSION}
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        purchase = response.json().get("Purchase", {})
        return self._parse_purchase(purchase)

    async def get_purchase_raw(self, purchase_id: str) -> dict:
        """Fetch a single purchase by ID as raw dict (for updates)."""
        url = self._build_url(f"purchase/{purchase_id}")
        params = {"minorversion": MINOR_VERSION}
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json().get("Purchase", {})

    def _parse_account(self, data: dict) -> QBOAccount:
        """Parse account data from API response."""
        return QBOAccount(
            id=data["Id"],
            name=data["Name"],
            full_name=data.get("FullyQualifiedName", data["Name"]),
            account_type=data["AccountType"],
            account_sub_type=data.get("AccountSubType"),
            parent_id=data.get("ParentRef", {}).get("value") if data.get("ParentRef") else None,
            active=data.get("Active", True),
            current_balance=Decimal(str(data["CurrentBalance"]))
            if "CurrentBalance" in data
            else None,
        )

    def _parse_purchase(self, data: dict) -> QBOTransaction:
        """Parse purchase data from API response."""
        account_ref = data.get("AccountRef", {})
        entity_ref = data.get("EntityRef", {})
        line_items = [self._parse_line_item(line) for line in data.get("Line", [])]
        return QBOTransaction(
            id=data["Id"],
            txn_date=datetime.strptime(data["TxnDate"], "%Y-%m-%d"),
            total_amount=Decimal(str(data["TotalAmt"])),
            account_id=account_ref.get("value", ""),
            account_name=account_ref.get("name", ""),
            doc_number=data.get("DocNumber"),
            memo=data.get("PrivateNote"),
            entity_name=entity_ref.get("name") if entity_ref else None,
            entity_id=entity_ref.get("value") if entity_ref else None,
            line_items=line_items,
        )

    def _parse_line_item(self, data: dict) -> QBOLineItem:
        """Parse line item data from API response."""
        detail = data.get("AccountBasedExpenseLineDetail", {})
        account_ref = detail.get("AccountRef", {})
        return QBOLineItem(
            id=data.get("Id"),
            amount=Decimal(str(data.get("Amount", 0))),
            description=data.get("Description"),
            account_id=account_ref.get("value") if account_ref else None,
            account_name=account_ref.get("name") if account_ref else None,
        )

    def _parse_vendor(self, data: dict) -> QBOVendor:
        """Parse vendor data from API response."""
        return QBOVendor(
            id=data["Id"],
            display_name=data["DisplayName"],
            active=data.get("Active", True),
        )

    async def create_account(
        self,
        name: str,
        account_type: str = 'Expense',
        parent_id: str | None = None,
    ) -> QBOAccount:
        """Create a new account in QuickBooks.

        Args:
            name: The account name.
            account_type: The account type (default: Expense).
            parent_id: Optional parent account QBO ID for subcategories.

        Returns:
            The created QBOAccount.
        """
        url = self._build_url('account')
        params = {'minorversion': MINOR_VERSION}
        payload: dict = {
            'Name': name,
            'AccountType': account_type,
        }
        if parent_id is not None:
            payload['SubAccount'] = True
            payload['ParentRef'] = {'value': parent_id}
        response = await self._client.post(url, params=params, json=payload)
        response.raise_for_status()
        account_data = response.json().get('Account', {})
        return self._parse_account(account_data)


class QuickBooksAPIError(Exception):
    """Exception raised for QuickBooks API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
