"""Tests for Textual widgets."""

from datetime import datetime
from decimal import Decimal

from rich.text import Text
from textual.app import App, ComposeResult

from easycat.db.models import Transaction, TransactionStatus
from easycat.widgets.transaction_table import STATUS_ICONS, TransactionTable


def make_transaction(
    id: int = 1,
    qbo_id: str = "1001",
    amount: Decimal = Decimal("-100.00"),
    description: str = "Test Transaction",
    vendor_name: str | None = "Test Vendor",
    status: TransactionStatus = TransactionStatus.PENDING,
    assigned_category_id: int | None = None,
) -> Transaction:
    """Create a test transaction."""
    return Transaction(
        id=id,
        qbo_id=qbo_id,
        account_id="acc1",
        account_name="Test Account",
        date=datetime(2024, 1, 15),
        amount=amount,
        description=description,
        vendor_name=vendor_name,
        status=status,
        assigned_category_id=assigned_category_id,
    )


class TransactionTableTestApp(App):
    """Test app for TransactionTable widget."""

    def compose(self) -> ComposeResult:
        yield TransactionTable(id="table")


class TestStatusIcons:
    """Tests for status icon mapping."""

    def test_pending_icon(self):
        """Test pending status icon."""
        icon, color = STATUS_ICONS[TransactionStatus.PENDING]
        assert icon == "●"
        assert color == "yellow"

    def test_categorized_icon(self):
        """Test categorized status icon."""
        icon, color = STATUS_ICONS[TransactionStatus.CATEGORIZED]
        assert icon == "✓"
        assert color == "green"

    def test_posted_icon(self):
        """Test posted status icon."""
        icon, color = STATUS_ICONS[TransactionStatus.POSTED]
        assert icon == "✔"
        assert color == "blue"


class TestTransactionTable:
    """Tests for TransactionTable widget."""

    async def test_table_adds_columns_on_mount(self):
        """Test that columns are added on mount."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            assert len(table.columns) == 6

    async def test_load_transactions_empty_list(self):
        """Test loading empty transaction list."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            table.load_transactions([])
            assert table.row_count == 0

    async def test_load_transactions_single(self):
        """Test loading a single transaction."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            txn = make_transaction()
            table.load_transactions([txn])
            assert table.row_count == 1

    async def test_load_transactions_multiple(self):
        """Test loading multiple transactions."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            transactions = [
                make_transaction(id=1, qbo_id="1001"),
                make_transaction(id=2, qbo_id="1002"),
                make_transaction(id=3, qbo_id="1003"),
            ]
            table.load_transactions(transactions)
            assert table.row_count == 3

    async def test_get_current_transaction_none(self):
        """Test getting current transaction when none selected."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            table.load_transactions([])
            assert table.get_current_transaction() is None

    async def test_get_current_transaction_with_data(self):
        """Test getting current transaction with data loaded."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            txn = make_transaction(qbo_id="test-qbo-id")
            table.load_transactions([txn])
            table.move_cursor(row=0)
            current = table.get_current_transaction()
            assert current is not None
            assert current.qbo_id == "test-qbo-id"

    async def test_get_current_transaction_row_out_of_bounds(self):
        """Test getting current transaction when cursor exceeds internal list."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            txn = make_transaction(qbo_id="test-qbo-id")
            table.load_transactions([txn])
            table.move_cursor(row=0)
            # Manually clear the internal list while keeping DataTable row
            table._transactions = []
            current = table.get_current_transaction()
            assert current is None

    async def test_update_transaction(self):
        """Test updating a transaction row."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            txn = make_transaction(status=TransactionStatus.PENDING)
            table.load_transactions([txn])

            txn.status = TransactionStatus.CATEGORIZED
            txn.assigned_category_id = 5
            table.update_transaction(txn)

            current = table.get_current_transaction()
            assert current is not None
            assert current.status == TransactionStatus.CATEGORIZED
            assert current.assigned_category_id == 5

    async def test_update_transaction_not_found(self):
        """Test updating a non-existent transaction."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            txn1 = make_transaction(qbo_id="1001")
            table.load_transactions([txn1])

            txn2 = make_transaction(qbo_id="9999")
            table.update_transaction(txn2)
            assert table.row_count == 1

    async def test_update_transaction_list_mismatch(self):
        """Test updating when transaction exists in map but not in list."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            txn = make_transaction(qbo_id="1001")
            table.load_transactions([txn])

            table._transactions = []
            updated_txn = make_transaction(qbo_id="1001", status=TransactionStatus.CATEGORIZED)
            table.update_transaction(updated_txn)

    async def test_update_transaction_not_first(self):
        """Test updating a transaction that is not the first in the list."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            txn1 = make_transaction(id=1, qbo_id="1001")
            txn2 = make_transaction(id=2, qbo_id="1002")
            txn3 = make_transaction(id=3, qbo_id="1003")
            table.load_transactions([txn1, txn2, txn3])

            updated_txn = make_transaction(
                id=3, qbo_id="1003", status=TransactionStatus.CATEGORIZED
            )
            table.update_transaction(updated_txn)

            updated = table._transactions[2]
            assert updated.status == TransactionStatus.CATEGORIZED

    async def test_keyboard_navigation_j_down(self):
        """Test j key moves cursor down."""
        app = TransactionTableTestApp()
        async with app.run_test() as pilot:
            table = app.query_one("#table", TransactionTable)
            transactions = [
                make_transaction(id=1, qbo_id="1001"),
                make_transaction(id=2, qbo_id="1002"),
            ]
            table.load_transactions(transactions)
            table.focus()
            await pilot.press("j")
            assert table.cursor_row == 1

    async def test_keyboard_navigation_k_up(self):
        """Test k key moves cursor up."""
        app = TransactionTableTestApp()
        async with app.run_test() as pilot:
            table = app.query_one("#table", TransactionTable)
            transactions = [
                make_transaction(id=1, qbo_id="1001"),
                make_transaction(id=2, qbo_id="1002"),
            ]
            table.load_transactions(transactions)
            table.focus()
            table.move_cursor(row=1)
            await pilot.press("k")
            assert table.cursor_row == 0

    async def test_scroll_top_action(self):
        """Test scroll to top action."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            transactions = [make_transaction(id=i, qbo_id=str(1000 + i)) for i in range(5)]
            table.load_transactions(transactions)
            table.move_cursor(row=4)
            table.action_scroll_top()
            assert table.cursor_row == 0

    async def test_scroll_bottom_action(self):
        """Test scroll to bottom action."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            transactions = [make_transaction(id=i, qbo_id=str(1000 + i)) for i in range(5)]
            table.load_transactions(transactions)
            table.action_scroll_bottom()
            assert table.cursor_row == 4

    async def test_scroll_top_empty_table(self):
        """Test scroll to top with empty table."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            table.load_transactions([])
            table.action_scroll_top()

    async def test_scroll_bottom_empty_table(self):
        """Test scroll to bottom with empty table."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            table.load_transactions([])
            table.action_scroll_bottom()


class TestTransactionTableFormatting:
    """Tests for TransactionTable cell formatting."""

    async def test_status_cell_pending(self):
        """Test status cell for pending transaction."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            result = table._status_cell(TransactionStatus.PENDING)
            assert isinstance(result, Text)
            assert "●" in str(result)

    async def test_date_cell_format(self):
        """Test date cell formatting."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            result = table._date_cell(datetime(2024, 3, 15))
            assert result == "2024-03-15"

    async def test_amount_cell_negative(self):
        """Test amount cell for negative amount."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            result = table._amount_cell(Decimal("-125.50"))
            assert isinstance(result, Text)
            assert "-$125.50" in str(result)

    async def test_amount_cell_positive(self):
        """Test amount cell for positive amount."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            result = table._amount_cell(Decimal("100.00"))
            assert isinstance(result, Text)
            assert "$100.00" in str(result)

    async def test_description_cell_short(self):
        """Test description cell with short text."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            result = table._description_cell("Short desc")
            assert result == "Short desc"

    async def test_description_cell_long(self):
        """Test description cell with long text truncation."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            long_desc = "A" * 50
            result = table._description_cell(long_desc)
            assert len(result) == 40
            assert result.endswith("...")

    async def test_vendor_cell_none(self):
        """Test vendor cell with None value."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            result = table._vendor_cell(None)
            assert result == "-"

    async def test_vendor_cell_short(self):
        """Test vendor cell with short name."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            result = table._vendor_cell("Amazon")
            assert result == "Amazon"

    async def test_vendor_cell_long(self):
        """Test vendor cell with long name truncation."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            long_name = "Very Long Vendor Name Inc"
            result = table._vendor_cell(long_name)
            assert len(result) == 20
            assert result.endswith("...")

    async def test_category_cell_none(self):
        """Test category cell with no category."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            result = table._category_cell(None)
            assert isinstance(result, Text)
            assert "Uncategorized" in str(result)

    async def test_category_cell_with_id(self):
        """Test category cell with category ID."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            result = table._category_cell(5)
            assert isinstance(result, Text)
            assert "#5" in str(result)

    async def test_category_cell_with_name_lookup(self):
        """Test category cell shows name when in lookup dict."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            table.set_categories({5: ('Office Supplies', None)})
            result = table._category_cell(5)
            assert isinstance(result, Text)
            assert 'Office Supplies' in str(result)

    async def test_category_cell_with_parent(self):
        """Test category cell shows parent in dim style."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            table.set_categories({5: ('Fuel', 'Automobile')})
            result = table._category_cell(5)
            assert isinstance(result, Text)
            assert 'Fuel' in str(result)
            assert ' < ' in str(result)
            assert 'Automobile' in str(result)

    async def test_category_cell_uncategorized_in_name(self):
        """Test category cell with 'Uncategorized' in name shows dim italic."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            table.set_categories({5: ('Uncategorized Expense', None)})
            result = table._category_cell(5)
            assert isinstance(result, Text)
            assert 'Uncategorized Expense' in str(result)
            assert result.style == 'dim italic'

    async def test_set_categories(self):
        """Test set_categories updates the lookup dictionary."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            table.set_categories({1: ('Travel', None), 2: ('Meals', 'Entertainment')})
            assert table._categories[1] == ('Travel', None)
            assert table._categories[2] == ('Meals', 'Entertainment')

    async def test_init_with_categories(self):
        """Test initializing table with categories."""

        class CatTableApp(App):
            def compose(self) -> ComposeResult:
                yield TransactionTable(categories={10: ('Insurance', 'Business')}, id='table')

        app = CatTableApp()
        async with app.run_test():
            table = app.query_one('#table', TransactionTable)
            assert table._categories[10] == ('Insurance', 'Business')


class TestTransactionTableMessages:
    """Tests for TransactionTable message handling."""

    async def test_row_selected_message_handler(self):
        """Test that on_data_table_row_selected posts TransactionSelected message."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            txn = make_transaction()
            table.load_transactions([txn])

            messages_received = []
            original_post = table.post_message

            def capture_post(msg):
                if isinstance(msg, TransactionTable.TransactionSelected):
                    messages_received.append(msg.transaction)
                return original_post(msg)

            table.post_message = capture_post

            from textual.widgets import DataTable

            event = DataTable.RowSelected(table, table.cursor_row, txn.qbo_id)
            table.on_data_table_row_selected(event)

            assert len(messages_received) == 1
            assert messages_received[0].qbo_id == txn.qbo_id

    async def test_row_selected_message_handler_not_found(self):
        """Test on_data_table_row_selected when row key not in map."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            txn = make_transaction()
            table.load_transactions([txn])

            messages_received = []
            original_post = table.post_message

            def capture_post(msg):
                if isinstance(msg, TransactionTable.TransactionSelected):
                    messages_received.append(msg.transaction)
                return original_post(msg)

            table.post_message = capture_post

            from textual.widgets import DataTable

            event = DataTable.RowSelected(table, table.cursor_row, "nonexistent")
            table.on_data_table_row_selected(event)

            assert len(messages_received) == 0

    async def test_row_highlighted_message(self):
        """Test that row highlight change posts TransactionHighlighted message."""
        messages_received = []

        class HighlightTestApp(App):
            def compose(self) -> ComposeResult:
                yield TransactionTable(id="table")

            def on_transaction_table_transaction_highlighted(
                self, event: TransactionTable.TransactionHighlighted
            ) -> None:
                messages_received.append(event.transaction)

        app = HighlightTestApp()
        async with app.run_test() as pilot:
            table = app.query_one("#table", TransactionTable)
            transactions = [
                make_transaction(id=1, qbo_id="1001"),
                make_transaction(id=2, qbo_id="1002"),
            ]
            table.load_transactions(transactions)
            table.focus()
            await pilot.press("j")
            assert len(messages_received) >= 1

    async def test_double_click_posts_selected_message(self):
        """Test that double-click posts TransactionSelected message."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            txn = make_transaction()
            table.load_transactions([txn])

            messages_received = []
            original_post = table.post_message

            def capture_post(msg):
                if isinstance(msg, TransactionTable.TransactionSelected):
                    messages_received.append(msg.transaction)
                return original_post(msg)

            table.post_message = capture_post

            class MockClickEvent:
                chain = 2

            table.on_click(MockClickEvent())

            assert len(messages_received) == 1
            assert messages_received[0].qbo_id == txn.qbo_id

    async def test_double_click_no_transaction(self):
        """Test that double-click with no transaction does nothing."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)

            messages_received = []
            original_post = table.post_message

            def capture_post(msg):
                if isinstance(msg, TransactionTable.TransactionSelected):
                    messages_received.append(msg.transaction)
                return original_post(msg)

            table.post_message = capture_post

            class MockClickEvent:
                chain = 2

            table.on_click(MockClickEvent())

            assert len(messages_received) == 0

    async def test_single_click_does_not_post_message(self):
        """Test that single-click does not post TransactionSelected."""
        app = TransactionTableTestApp()
        async with app.run_test():
            table = app.query_one("#table", TransactionTable)
            txn = make_transaction()
            table.load_transactions([txn])

            messages_received = []
            original_post = table.post_message

            def capture_post(msg):
                if isinstance(msg, TransactionTable.TransactionSelected):
                    messages_received.append(msg.transaction)
                return original_post(msg)

            table.post_message = capture_post

            class MockClickEvent:
                chain = 1

            table.on_click(MockClickEvent())

            assert len(messages_received) == 0
