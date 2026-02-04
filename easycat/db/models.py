"""Database models and schema definitions."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class TransactionStatus(Enum):
    """Status of a transaction in the review workflow."""

    PENDING = "pending"
    CATEGORIZED = "categorized"
    POSTED = "posted"


class PatternType(Enum):
    """Type of pattern matching for rules."""

    CONTAINS = "contains"
    REGEX = "regex"
    EXACT = "exact"


@dataclass
class Token:
    """OAuth token storage."""

    id: int | None
    realm_id: str
    access_token: str
    refresh_token: str
    expires_at: datetime
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Category:
    """Category from QuickBooks Chart of Accounts."""

    id: int | None
    qbo_id: str
    name: str
    full_name: str
    parent_id: int | None
    account_type: str
    is_visible: bool = True
    display_order: int = 0
    synced_at: datetime = field(default_factory=datetime.now)


@dataclass
class Rule:
    """Categorization rule for auto-matching transactions."""

    id: int | None
    name: str
    pattern: str
    pattern_type: PatternType
    category_id: int
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    priority: int = 0
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class VendorMapping:
    """Vendor to category default mapping."""

    id: int | None
    vendor_name: str
    vendor_id: str | None
    default_category_id: int
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Transaction:
    """Cached transaction from QuickBooks."""

    id: int | None
    qbo_id: str
    account_id: str
    account_name: str
    date: datetime
    amount: Decimal
    description: str
    vendor_name: str | None
    status: TransactionStatus = TransactionStatus.PENDING
    assigned_category_id: int | None = None
    fetched_at: datetime = field(default_factory=datetime.now)


@dataclass
class TransactionSplit:
    """Split portion of a transaction across multiple categories."""

    id: int | None
    transaction_id: int
    category_id: int
    amount: Decimal
    memo: str | None = None
