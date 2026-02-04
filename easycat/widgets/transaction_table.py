"""Transaction table widget for displaying and navigating transactions."""

from datetime import datetime
from decimal import Decimal

from rich.text import Text
from textual.message import Message
from textual.widgets import DataTable

from easycat.db.models import Transaction, TransactionStatus

STATUS_ICONS = {
    TransactionStatus.PENDING: ("●", "yellow"),
    TransactionStatus.CATEGORIZED: ("✓", "green"),
    TransactionStatus.POSTED: ("✔", "blue"),
}


class TransactionTable(DataTable):
    """Data table specialized for displaying transactions."""

    class TransactionSelected(Message):
        """Message emitted when a transaction is selected."""

        def __init__(self, transaction: Transaction) -> None:
            super().__init__()
            self.transaction = transaction

    class TransactionHighlighted(Message):
        """Message emitted when cursor moves to a transaction."""

        def __init__(self, transaction: Transaction | None) -> None:
            super().__init__()
            self.transaction = transaction

    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("g", "scroll_top", "Top"),
        ("G", "scroll_bottom", "Bottom"),
    ]

    COLUMN_NAMES = ("Status", "Date", "Amount", "Description", "Vendor", "Category")

    def __init__(
        self, categories: dict[int, tuple[str, str | None]] | None = None, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._transactions: list[Transaction] = []
        self._transaction_map: dict[str, Transaction] = {}
        self._categories: dict[int, tuple[str, str | None]] = categories or {}
        self.cursor_type = "row"
        self._column_keys: dict[str, str] = {}

    def set_categories(self, categories: dict[int, tuple[str, str | None]]) -> None:
        """Update the category lookup dictionary."""
        self._categories = categories

    COLUMN_WIDTHS = {
        'Status': 6,
        'Date': 12,
        'Amount': 12,
        'Description': 40,
        'Vendor': 20,
        'Category': None,  # Auto-expand to fill remaining space
    }

    def on_mount(self) -> None:
        """Set up table columns on mount."""
        for name in self.COLUMN_NAMES:
            width = self.COLUMN_WIDTHS.get(name)
            col_key = self.add_column(name, key=name, width=width)
            self._column_keys[name] = str(col_key)

    def load_transactions(self, transactions: list[Transaction]) -> None:
        """Load transactions into the table."""
        self._transactions = transactions
        self._transaction_map.clear()
        self.clear()

        for txn in transactions:
            row_key = str(txn.qbo_id)
            self._transaction_map[row_key] = txn
            self.add_row(
                self._status_cell(txn.status),
                self._date_cell(txn.date),
                self._amount_cell(txn.amount),
                self._description_cell(txn.description),
                self._vendor_cell(txn.vendor_name),
                self._category_cell(txn.assigned_category_id),
                key=row_key,
            )

    def get_current_transaction(self) -> Transaction | None:
        """Get the currently highlighted transaction."""
        if self.row_count == 0:
            return None
        row = self.cursor_row
        if row < 0 or row >= len(self._transactions):
            return None
        return self._transactions[row]

    def update_transaction(self, transaction: Transaction) -> None:
        """Update a single transaction row."""
        row_key = str(transaction.qbo_id)
        if row_key in self._transaction_map:
            self._transaction_map[row_key] = transaction
            for i, txn in enumerate(self._transactions):
                if txn.qbo_id == transaction.qbo_id:
                    self._transactions[i] = transaction
                    break
            self.update_cell(row_key, "Status", self._status_cell(transaction.status))
            self.update_cell(
                row_key, "Category", self._category_cell(transaction.assigned_category_id)
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (Enter key)."""
        txn = self._transaction_map.get(str(event.row_key))
        if txn:
            self.post_message(self.TransactionSelected(txn))

    def on_click(self, event) -> None:
        """Handle mouse clicks - double-click opens category selection."""
        if event.chain == 2:
            txn = self.get_current_transaction()
            if txn:
                self.post_message(self.TransactionSelected(txn))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight change."""
        txn = self._transaction_map.get(str(event.row_key)) if event.row_key else None
        self.post_message(self.TransactionHighlighted(txn))

    def action_scroll_top(self) -> None:
        """Move cursor to first row."""
        if self.row_count > 0:
            self.move_cursor(row=0)

    def action_scroll_bottom(self) -> None:
        """Move cursor to last row."""
        if self.row_count > 0:
            self.move_cursor(row=self.row_count - 1)

    def _status_cell(self, status: TransactionStatus) -> Text:
        """Create status indicator cell."""
        icon, color = STATUS_ICONS.get(status, ("?", "red"))
        return Text(icon, style=color)

    def _date_cell(self, date: datetime) -> str:
        """Format date for display."""
        return date.strftime("%Y-%m-%d")

    def _amount_cell(self, amount: Decimal) -> Text:
        """Format amount with color based on sign."""
        formatted = f"${abs(amount):,.2f}"
        if amount < 0:
            return Text(f"-{formatted}", style="red")
        return Text(formatted, style="green")

    def _description_cell(self, description: str) -> str:
        """Truncate description for display."""
        max_len = 40
        if len(description) > max_len:
            return description[: max_len - 3] + "..."
        return description

    def _vendor_cell(self, vendor_name: str | None) -> str:
        """Format vendor name."""
        if not vendor_name:
            return "-"
        max_len = 20
        if len(vendor_name) > max_len:
            return vendor_name[: max_len - 3] + "..."
        return vendor_name

    def _category_cell(self, category_id: int | None) -> Text:
        """Format category assignment with optional parent."""
        if category_id is None:
            return Text('Uncategorized', style='dim italic')
        category_info = self._categories.get(category_id)
        if category_info is None:
            return Text(f'#{category_id}', style='cyan')
        name, parent_name = category_info
        if 'Uncategorized' in name:
            return Text(name, style='dim italic')
        result = Text(name, style='cyan')
        if parent_name:
            result.append(' < ', style='dim')
            result.append(parent_name, style='dim cyan')
        return result
