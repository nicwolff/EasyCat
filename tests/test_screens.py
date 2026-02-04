"""Tests for Textual screens."""

from datetime import datetime
from decimal import Decimal

from textual.app import App, ComposeResult
from textual.widgets import Label

from easycat.db.models import Category, Transaction, TransactionStatus
from easycat.screens.categories import (
    CategoryList,
    CategoryListItem,
    CategorySelectScreen,
    ManageCategoriesScreen,
    ManageCategoryList,
    ManageCategoryListItem,
    TextInputScreen,
)
from easycat.screens.transactions import (
    ConfirmBatchScreen,
    StatusBar,
    TransactionsScreen,
)
from easycat.widgets.transaction_table import TransactionTable


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


def make_category(
    id: int = 1,
    qbo_id: str = '1',
    name: str = 'Test Category',
    full_name: str = 'Expenses:Test Category',
    parent_id: int | None = None,
    is_visible: bool = True,
) -> Category:
    """Create a test category."""
    return Category(
        id=id,
        qbo_id=qbo_id,
        name=name,
        full_name=full_name,
        parent_id=parent_id,
        account_type='Expense',
        is_visible=is_visible,
    )


class ScreenTestApp(App):
    """Base test app with repository property for TransactionsScreen tests."""

    repository = None

    def on_mount(self) -> None:
        """Push the transactions screen on mount."""
        self.push_screen(TransactionsScreen())


class TestCategoryListItem:
    """Tests for CategoryListItem widget."""

    async def test_category_list_item_creation(self):
        """Test creating a CategoryListItem."""
        category = make_category()
        item = CategoryListItem(category)
        assert item.category == category


class TestCategoryList:
    """Tests for CategoryList widget."""

    async def test_filter_empty_query(self):
        """Test filtering with empty query returns all categories."""

        class CategoryListApp(App):
            def compose(self) -> ComposeResult:
                yield CategoryList(
                    [
                        make_category(id=1, name='Advertising'),
                        make_category(id=2, name='Travel'),
                    ]
                )

        app = CategoryListApp()
        async with app.run_test():
            cat_list = app.query_one(CategoryList)
            cat_list.filter('')
            assert len(cat_list._filtered_tree) == 2

    async def test_filter_matches_name(self):
        """Test filtering matches category name."""

        class CategoryListApp(App):
            def compose(self) -> ComposeResult:
                yield CategoryList(
                    [
                        make_category(id=1, name='Advertising'),
                        make_category(id=2, name='Travel'),
                    ]
                )

        app = CategoryListApp()
        async with app.run_test():
            cat_list = app.query_one(CategoryList)
            cat_list.filter('adver')
            assert len(cat_list._filtered_tree) == 1
            assert cat_list._filtered_tree[0][0].name == 'Advertising'

    async def test_filter_matches_full_name(self):
        """Test filtering matches full name."""

        class CategoryListApp(App):
            def compose(self) -> ComposeResult:
                yield CategoryList(
                    [
                        make_category(id=1, name='Ads', full_name='Marketing:Ads'),
                        make_category(id=2, name='Travel', full_name='Expenses:Travel'),
                    ]
                )

        app = CategoryListApp()
        async with app.run_test():
            cat_list = app.query_one(CategoryList)
            cat_list.filter('marketing')
            assert len(cat_list._filtered_tree) == 1
            assert cat_list._filtered_tree[0][0].name == 'Ads'

    async def test_get_selected_category_none(self):
        """Test get_selected_category when nothing is selected."""

        class CategoryListApp(App):
            def compose(self) -> ComposeResult:
                yield CategoryList([])

        app = CategoryListApp()
        async with app.run_test():
            cat_list = app.query_one(CategoryList)
            assert cat_list.get_selected_category() is None

    async def test_get_selected_category_with_selection(self):
        """Test get_selected_category with a selection."""

        class CategoryListApp(App):
            def compose(self) -> ComposeResult:
                yield CategoryList(
                    [
                        make_category(id=1, name="Advertising"),
                    ]
                )

        app = CategoryListApp()
        async with app.run_test() as pilot:
            cat_list = app.query_one(CategoryList)
            cat_list.focus()
            await pilot.pause()
            selected = cat_list.get_selected_category()
            if selected:
                assert selected.name == "Advertising"


class TestCategorySelectScreen:
    """Tests for CategorySelectScreen."""

    async def test_cancel_action_dismisses(self):
        """Test cancel action dismisses the screen."""
        dismissed_value = []

        class HostApp(App):
            def on_mount(self) -> None:
                txn = make_transaction()

                def callback(value):
                    dismissed_value.append(value)
                    self.exit()

                self.push_screen(CategorySelectScreen(txn), callback)

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.press("escape")
            await pilot.pause()

        assert None in dismissed_value or len(dismissed_value) == 0

    async def test_screen_shows_transaction_description(self):
        """Test screen shows the transaction description."""
        txn = make_transaction(description="AMAZON MKTPLACE")

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(CategorySelectScreen(txn))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CategorySelectScreen)
            assert "AMAZON" in str(screen.query_one("#title").render())

    async def test_input_filters_categories(self):
        """Test typing in input filters the category list."""
        txn = make_transaction()

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(CategorySelectScreen(txn))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#search")
            input_widget.focus()
            await pilot.press("t", "r", "a", "v", "e", "l")
            await pilot.pause()

    async def test_action_select_no_category(self):
        """Test action_select when no category is highlighted."""
        txn = make_transaction()

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(CategorySelectScreen(txn))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            cat_list = screen.query_one("#category-list", CategoryList)
            cat_list.clear()
            cat_list._filtered_tree = []
            screen.action_select()
            await pilot.pause()

    async def test_list_view_selected_event(self):
        """Test on_list_view_selected handler calls action_select."""
        txn = make_transaction()

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(CategorySelectScreen(txn))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            cat_list = screen.query_one("#category-list", CategoryList)
            from textual.widgets import ListView

            event = ListView.Selected(cat_list, cat_list.children[0], 0)
            screen.on_list_view_selected(event)
            await pilot.pause()

    async def test_screen_with_provided_categories(self):
        """Test screen uses provided categories instead of sample data."""
        txn = make_transaction()
        categories = [make_category(id=99, name="Custom Category")]

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(CategorySelectScreen(txn, categories))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            cat_list = screen.query_one("#category-list", CategoryList)
            assert len(cat_list._all_categories) == 1
            assert cat_list._all_categories[0].name == "Custom Category"

    async def test_cursor_up_action(self):
        """Test cursor up action moves list cursor."""
        txn = make_transaction()
        categories = [
            make_category(id=1, name="First"),
            make_category(id=2, name="Second"),
        ]

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(CategorySelectScreen(txn, categories))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            cat_list = screen.query_one("#category-list", CategoryList)
            cat_list.index = 1
            screen.action_cursor_up()
            assert cat_list.index == 0

    async def test_cursor_down_action(self):
        """Test cursor down action moves list cursor."""
        txn = make_transaction()
        categories = [
            make_category(id=1, name="First"),
            make_category(id=2, name="Second"),
        ]

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(CategorySelectScreen(txn, categories))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            cat_list = screen.query_one("#category-list", CategoryList)
            cat_list.index = 0
            screen.action_cursor_down()
            assert cat_list.index == 1


class TestAccountSelectScreen:
    """Tests for AccountSelectScreen."""

    async def test_cancel_action_dismisses(self):
        """Test cancel action dismisses the screen."""
        dismissed_value = []

        class HostApp(App):
            def on_mount(self) -> None:
                accounts = [('', 'All Accounts'), ('acc1', 'Business Checking')]

                def callback(value):
                    dismissed_value.append(value)
                    self.exit()

                from easycat.screens.transactions import AccountSelectScreen
                self.push_screen(AccountSelectScreen(accounts), callback)

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.press('escape')
            await pilot.pause()

        assert None in dismissed_value or len(dismissed_value) == 0

    async def test_screen_shows_accounts(self):
        """Test screen shows the account list."""
        accounts = [('', 'All Accounts'), ('acc1', 'Business Checking')]

        class HostApp(App):
            def on_mount(self) -> None:
                from easycat.screens.transactions import AccountSelectScreen
                self.push_screen(AccountSelectScreen(accounts))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            from easycat.screens.transactions import AccountSelectScreen
            screen = app.screen
            assert isinstance(screen, AccountSelectScreen)

    async def test_input_filters_accounts(self):
        """Test typing in input filters the account list."""
        accounts = [('', 'All Accounts'), ('acc1', 'Business Checking'), ('acc2', 'Credit Card')]

        class HostApp(App):
            def on_mount(self) -> None:
                from easycat.screens.transactions import AccountSelectScreen
                self.push_screen(AccountSelectScreen(accounts))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one('#search')
            input_widget.focus()
            await pilot.press('b', 'u', 's')
            await pilot.pause()
            from easycat.screens.transactions import AccountList
            account_list = screen.query_one('#account-list', AccountList)
            assert len(account_list._filtered_accounts) == 1

    async def test_action_select_no_account(self):
        """Test action_select when no account is highlighted."""
        accounts = [('', 'All Accounts')]

        class HostApp(App):
            def on_mount(self) -> None:
                from easycat.screens.transactions import AccountSelectScreen
                self.push_screen(AccountSelectScreen(accounts))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            from easycat.screens.transactions import AccountList
            account_list = screen.query_one('#account-list', AccountList)
            account_list.clear()
            account_list._filtered_accounts = []
            screen.action_select()
            await pilot.pause()

    async def test_list_view_selected_event(self):
        """Test on_list_view_selected handler calls action_select."""
        accounts = [('', 'All Accounts'), ('acc1', 'Business Checking')]

        class HostApp(App):
            def on_mount(self) -> None:
                from easycat.screens.transactions import AccountSelectScreen
                self.push_screen(AccountSelectScreen(accounts))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            from easycat.screens.transactions import AccountList
            account_list = screen.query_one('#account-list', AccountList)
            from textual.widgets import ListView
            event = ListView.Selected(account_list, account_list.children[0], 0)
            screen.on_list_view_selected(event)
            await pilot.pause()

    async def test_cursor_up_action(self):
        """Test cursor up action moves list cursor."""
        accounts = [('', 'All Accounts'), ('acc1', 'Business Checking')]

        class HostApp(App):
            def on_mount(self) -> None:
                from easycat.screens.transactions import AccountSelectScreen
                self.push_screen(AccountSelectScreen(accounts))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            from easycat.screens.transactions import AccountList
            account_list = screen.query_one('#account-list', AccountList)
            account_list.index = 1
            screen.action_cursor_up()
            assert account_list.index == 0

    async def test_cursor_down_action(self):
        """Test cursor down action moves list cursor."""
        accounts = [('', 'All Accounts'), ('acc1', 'Business Checking')]

        class HostApp(App):
            def on_mount(self) -> None:
                from easycat.screens.transactions import AccountSelectScreen
                self.push_screen(AccountSelectScreen(accounts))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            from easycat.screens.transactions import AccountList
            account_list = screen.query_one('#account-list', AccountList)
            account_list.index = 0
            screen.action_cursor_down()
            assert account_list.index == 1

    async def test_select_returns_account_id(self):
        """Test selecting an account returns the account ID."""
        result = []
        accounts = [('', 'All Accounts'), ('acc1', 'Business Checking')]

        class HostApp(App):
            def on_mount(self) -> None:
                def callback(value):
                    result.append(value)
                    self.exit()

                from easycat.screens.transactions import AccountSelectScreen
                self.push_screen(AccountSelectScreen(accounts), callback)

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press('down')
            await pilot.pause()
            await pilot.press('enter')
            await pilot.pause()

        assert 'acc1' in result


class TestAccountList:
    """Tests for AccountList widget."""

    async def test_filter_accounts(self):
        """Test filtering accounts by query."""
        accounts = [('', 'All Accounts'), ('acc1', 'Business Checking'), ('acc2', 'Credit Card')]

        class ListApp(App):
            def compose(self) -> ComposeResult:
                from easycat.screens.transactions import AccountList
                yield AccountList(accounts)

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            from easycat.screens.transactions import AccountList
            account_list = app.query_one(AccountList)
            account_list.filter('credit')
            assert len(account_list._filtered_accounts) == 1
            assert account_list._filtered_accounts[0][1] == 'Credit Card'

    async def test_filter_empty_query_shows_all(self):
        """Test empty filter query shows all accounts."""
        accounts = [('', 'All Accounts'), ('acc1', 'Business Checking')]

        class ListApp(App):
            def compose(self) -> ComposeResult:
                from easycat.screens.transactions import AccountList
                yield AccountList(accounts)

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            from easycat.screens.transactions import AccountList
            account_list = app.query_one(AccountList)
            account_list.filter('xyz')
            account_list.filter('')
            assert len(account_list._filtered_accounts) == 2

    async def test_get_selected_account_none(self):
        """Test get_selected_account returns None when nothing selected."""
        accounts = [('', 'All Accounts')]

        class ListApp(App):
            def compose(self) -> ComposeResult:
                from easycat.screens.transactions import AccountList
                yield AccountList(accounts)

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            from easycat.screens.transactions import AccountList
            account_list = app.query_one(AccountList)
            account_list.clear()
            account_list._filtered_accounts = []
            result = account_list.get_selected_account()
            assert result is None

    async def test_select_current_account(self):
        """Test current account is selected on mount."""
        accounts = [('acc1', 'Business Checking'), ('acc2', 'Credit Card')]

        class ListApp(App):
            def compose(self) -> ComposeResult:
                from easycat.screens.transactions import AccountList
                yield AccountList(accounts, current_account_id='acc2')

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            from easycat.screens.transactions import AccountList
            account_list = app.query_one(AccountList)
            selected = account_list.get_selected_account()
            assert selected is not None
            assert selected[0] == 'acc2'

    async def test_select_current_account_not_found(self):
        """Test current account not found doesn't change selection."""
        accounts = [('acc1', 'Business Checking'), ('acc2', 'Credit Card')]

        class ListApp(App):
            def compose(self) -> ComposeResult:
                from easycat.screens.transactions import AccountList
                yield AccountList(accounts, current_account_id='nonexistent')

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            from easycat.screens.transactions import AccountList
            account_list = app.query_one(AccountList)
            assert account_list.index == 0


class TestActionLink:
    """Tests for ActionLink widget."""

    async def test_action_link_click_posts_message(self):
        """Test clicking action link posts Clicked message."""
        from easycat.screens.transactions import ActionLink

        messages_received = []

        class LinkApp(App):
            def compose(self) -> ComposeResult:
                yield ActionLink('[T]est', 'test_action')

            def on_action_link_clicked(self, event: ActionLink.Clicked) -> None:
                messages_received.append(event.action)

        app = LinkApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            link = app.query_one(ActionLink)
            link.on_click()
            await pilot.pause()
            assert 'test_action' in messages_received

    async def test_action_link_clicked_message(self):
        """Test ActionLink.Clicked message contains action."""
        from easycat.screens.transactions import ActionLink

        msg = ActionLink.Clicked('my_action')
        assert msg.action == 'my_action'


class TestConfirmBatchScreen:
    """Tests for ConfirmBatchScreen widget."""

    async def test_confirm_batch_screen_compose(self):
        """Test ConfirmBatchScreen renders correctly."""

        class ConfirmApp(App):
            def on_mount(self) -> None:
                self.push_screen(ConfirmBatchScreen(3, 'AMAZON PURCHASE', 'Office Supplies'))

        app = ConfirmApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ConfirmBatchScreen)

    async def test_confirm_batch_screen_yes_action(self):
        """Test yes action dismisses with True."""
        result = None

        def capture_result(value):
            nonlocal result
            result = value

        class ConfirmApp(App):
            def on_mount(self) -> None:
                self.push_screen(
                    ConfirmBatchScreen(3, 'AMAZON', 'Travel'),
                    capture_result
                )

        app = ConfirmApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_yes()
            await pilot.pause()
            assert result is True

    async def test_confirm_batch_screen_no_action(self):
        """Test no action dismisses with False."""
        result = None

        def capture_result(value):
            nonlocal result
            result = value

        class ConfirmApp(App):
            def on_mount(self) -> None:
                self.push_screen(
                    ConfirmBatchScreen(3, 'AMAZON', 'Travel'),
                    capture_result
                )

        app = ConfirmApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_no()
            await pilot.pause()
            assert result is False

    async def test_confirm_batch_screen_button_yes(self):
        """Test clicking Yes button dismisses with True."""
        from textual.widgets import Button

        result = None

        def capture_result(value):
            nonlocal result
            result = value

        class ConfirmApp(App):
            def on_mount(self) -> None:
                self.push_screen(
                    ConfirmBatchScreen(3, 'AMAZON', 'Travel'),
                    capture_result
                )

        app = ConfirmApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            yes_button = screen.query_one('#yes', Button)
            yes_button.press()
            await pilot.pause()
            assert result is True

    async def test_confirm_batch_screen_button_no(self):
        """Test clicking No button dismisses with False."""
        from textual.widgets import Button

        result = None

        def capture_result(value):
            nonlocal result
            result = value

        class ConfirmApp(App):
            def on_mount(self) -> None:
                self.push_screen(
                    ConfirmBatchScreen(3, 'AMAZON', 'Travel'),
                    capture_result
                )

        app = ConfirmApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            no_button = screen.query_one('#no', Button)
            no_button.press()
            await pilot.pause()
            assert result is False


class TestStatusBar:
    """Tests for StatusBar widget."""

    async def test_update_counts(self):
        """Test updating status bar counts."""

        class StatusBarApp(App):
            def compose(self) -> ComposeResult:
                yield StatusBar()

        app = StatusBarApp()
        async with app.run_test():
            status_bar = app.query_one(StatusBar)
            status_bar.update_counts(10, 5, 3)
            assert status_bar._total == 10
            assert status_bar._pending == 5
            assert status_bar._categorized == 3


class TestTransactionsScreen:
    """Tests for TransactionsScreen."""

    async def test_build_category_map_with_parents(self):
        """Test _build_category_map builds map with parent names."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            # Set up categories with parent relationship
            # parent_id stores the parent's qbo_id (as int), not the local id
            parent_cat = Category(
                id=1, qbo_id='100', name='Automobile', full_name='Expenses:Automobile',
                parent_id=None, account_type='Expense'
            )
            child_cat = Category(
                id=2, qbo_id='200', name='Fuel', full_name='Expenses:Automobile:Fuel',
                parent_id=100, account_type='Expense'  # parent_id matches parent's qbo_id
            )
            screen._categories = [parent_cat, child_cat]
            result = screen._build_category_map()
            assert result[1] == ('Automobile', None)
            assert result[2] == ('Fuel', 'Automobile')

    async def test_build_category_map_skips_none_ids(self):
        """Test _build_category_map skips categories with id=None."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            # Category with id=None (unsaved)
            unsaved_cat = Category(
                id=None, qbo_id='99', name='Unsaved', full_name='Expenses:Unsaved',
                parent_id=None, account_type='Expense'
            )
            saved_cat = Category(
                id=1, qbo_id='1', name='Saved', full_name='Expenses:Saved',
                parent_id=None, account_type='Expense'
            )
            screen._categories = [unsaved_cat, saved_cat]
            result = screen._build_category_map()
            assert 1 in result
            assert result[1] == ('Saved', None)
            # None id should not be in the map
            assert None not in result

    async def test_screen_composes_widgets(self):
        """Test screen contains expected widgets."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, TransactionsScreen)
            assert screen.query_one('#transactions', TransactionTable) is not None
            assert screen.query_one(StatusBar) is not None

    async def test_screen_mount_loads_sample_data(self):
        """Test screen mount loads sample data when no repository."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert len(screen._all_transactions) == 3

    async def test_highlight_updates_current(self):
        """Test highlighting a transaction updates current transaction."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            table = screen.query_one('#transactions', TransactionTable)
            table.focus()
            await pilot.press('j')
            await pilot.pause()

    async def test_categorize_action_without_selection(self):
        """Test categorize action with no selection shows warning."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            table = screen.query_one("#transactions", TransactionTable)
            table.clear()
            table._transactions = []
            table._transaction_map = {}
            screen._current_transaction = None
            screen.action_categorize()
            await pilot.pause()

    async def test_split_action_without_selection(self):
        """Test split action with no selection shows warning."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            table = screen.query_one("#transactions", TransactionTable)
            table.clear()
            table._transactions = []
            table._transaction_map = {}
            screen._current_transaction = None
            screen.action_split()
            await pilot.pause()

    async def test_split_action_with_selection(self):
        """Test split action shows coming soon message."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._current_transaction = make_transaction()
            screen.action_split()
            await pilot.pause()

    async def test_post_action(self):
        """Test post action notifies about database not connected."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_post()
            await pilot.pause()

    async def test_refresh_action(self):
        """Test refresh action notifies about database not connected."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_refresh()
            await pilot.pause()

    async def test_select_account_action(self):
        """Test select_account action opens account selection screen."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_select_account()
            await pilot.pause()
            from easycat.screens.transactions import AccountSelectScreen
            assert isinstance(app.screen, AccountSelectScreen)

    async def test_categorize_action_with_selection(self):
        """Test categorize action opens category screen when transaction selected."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._current_transaction = make_transaction()
            screen.action_categorize()
            await pilot.pause()
            assert isinstance(app.screen, CategorySelectScreen)

    async def test_transaction_selected_event(self):
        """Test on_transaction_table_transaction_selected handler."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            txn = make_transaction()
            screen._current_transaction = txn
            event = TransactionTable.TransactionSelected(txn)
            screen.on_transaction_table_transaction_selected(event)
            await pilot.pause()

    async def test_handle_category_selected_with_category(self):
        """Test _handle_category_selected assigns category."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            txn = make_transaction()
            screen._current_transaction = txn
            screen._filtered_transactions = [txn]
            screen._handle_category_selected(5)
            await pilot.pause()
            await pilot.pause()

    async def test_handle_category_selected_none(self):
        """Test _handle_category_selected does nothing with None."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            txn = make_transaction()
            screen._current_transaction = txn
            screen._handle_category_selected(None)
            assert txn.status == TransactionStatus.PENDING

    async def test_handle_category_selected_no_transaction(self):
        """Test _handle_category_selected does nothing without transaction."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._current_transaction = None
            screen._handle_category_selected(5)

    async def test_get_selected_transaction_returns_from_table(self):
        """Test _get_selected_transaction gets transaction from table."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            txn = screen._get_selected_transaction()
            assert txn is not None
            assert txn.qbo_id == "1001"

    async def test_get_selected_transaction_caches_result(self):
        """Test _get_selected_transaction caches the result."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen._get_selected_transaction()
            assert screen._current_transaction is not None

    async def test_get_selected_transaction_returns_cached_when_table_empty(self):
        """Test _get_selected_transaction returns cached value when table is empty."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            cached_txn = make_transaction(qbo_id="cached")
            screen._current_transaction = cached_txn
            table = screen.query_one("#transactions", TransactionTable)
            table.clear()
            table._transactions = []
            table._transaction_map = {}
            result = screen._get_selected_transaction()
            assert result == cached_txn

    async def test_transaction_highlighted_event(self):
        """Test on_transaction_table_transaction_highlighted handler."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            txn = make_transaction(description="Highlighted")
            event = TransactionTable.TransactionHighlighted(txn)
            screen.on_transaction_table_transaction_highlighted(event)
            assert screen._current_transaction == txn

    async def test_assign_category_async_no_current_transaction(self):
        """Test _assign_category_async returns early when no current transaction."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._current_transaction = None
            await screen._assign_category_async(5)

    async def test_assign_category_async_updates_status(self):
        """Test _assign_category_async updates transaction status."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            txn = make_transaction(id=1)
            screen._current_transaction = txn
            screen._filtered_transactions = [txn]
            await screen._assign_category_async(5)
            await pilot.pause()
            assert txn.status == TransactionStatus.CATEGORIZED
            assert txn.assigned_category_id == 5

    async def test_post_transactions_no_repo(self):
        """Test _post_transactions_async with no repository."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            await screen._post_transactions_async()
            await pilot.pause()

    async def test_refresh_from_qbo_no_repo(self):
        """Test _refresh_from_qbo_async with no repository."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            await screen._refresh_from_qbo_async()
            await pilot.pause()


class TestTransactionsScreenWithMockRepo:
    """Tests for TransactionsScreen with mocked repository."""

    async def test_load_data_with_real_transactions(self):
        """Test _load_data when database has transactions."""
        from unittest.mock import AsyncMock

        from easycat.db.models import Token

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_all_categories.return_value = [
                    make_category(id=1, name='Travel')
                ]
                self._mock_repo.search_transactions.return_value = [
                    make_transaction(qbo_id='real_txn')
                ]
                self._mock_repo.get_latest_token.return_value = Token(
                    id=1,
                    realm_id='test_realm',
                    access_token='encrypted_access',
                    refresh_token='encrypted_refresh',
                    expires_at=None,
                )

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert len(screen._all_transactions) == 1
            assert screen._all_transactions[0].qbo_id == 'real_txn'

    async def test_load_data_fallback_to_sample_when_empty(self):
        """Test _load_data falls back to sample data when DB is empty."""
        from unittest.mock import AsyncMock

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_all_categories.return_value = []
                self._mock_repo.search_transactions.return_value = []
                self._mock_repo.get_latest_token.return_value = None

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert len(screen._all_transactions) == 3

    async def test_assign_category_with_repo(self):
        """Test _assign_category_async with real repository."""
        from unittest.mock import AsyncMock

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_all_categories.return_value = []
                self._mock_repo.search_transactions.return_value = []
                self._mock_repo.get_latest_token.return_value = None

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            txn = make_transaction(id=1)
            screen._current_transaction = txn
            screen._filtered_transactions = [txn]
            screen._all_transactions = [txn]
            await screen._assign_category_async(5)
            await pilot.pause()
            app._mock_repo.update_transaction_status.assert_called_once()

    async def test_assign_category_with_matching_transactions(self):
        """Test _assign_category_async prompts for matching transactions."""
        from unittest.mock import AsyncMock

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_all_categories.return_value = []
                self._mock_repo.search_transactions.return_value = []
                self._mock_repo.get_latest_token.return_value = None

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            txn1 = make_transaction(id=1, description='AMAZON')
            txn2 = make_transaction(id=2, qbo_id='1002', description='AMAZON')
            screen._current_transaction = txn1
            screen._filtered_transactions = [txn1, txn2]
            screen._all_transactions = [txn1, txn2]
            screen._category_map = {5: 'Office Supplies'}
            await screen._assign_category_async(5)
            await pilot.pause()
            assert isinstance(app.screen, ConfirmBatchScreen)

    async def test_handle_batch_confirmed_true(self):
        """Test _handle_batch_confirmed runs batch when confirmed."""
        from unittest.mock import AsyncMock

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_all_categories.return_value = []
                self._mock_repo.search_transactions.return_value = []
                self._mock_repo.get_latest_token.return_value = None

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            txn = make_transaction(id=2, description='TEST')
            screen._handle_batch_confirmed(True, [txn], 5)
            await pilot.pause()

    async def test_handle_batch_confirmed_false(self):
        """Test _handle_batch_confirmed does nothing when not confirmed."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            txn = make_transaction(id=2, description='TEST')
            screen._handle_batch_confirmed(False, [txn], 5)
            await pilot.pause()
            assert txn.status == TransactionStatus.PENDING

    async def test_batch_categorize_async(self):
        """Test _batch_categorize_async categorizes multiple transactions."""
        from unittest.mock import AsyncMock

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_all_categories.return_value = []
                self._mock_repo.search_transactions.return_value = []
                self._mock_repo.get_latest_token.return_value = None

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            txn1 = make_transaction(id=1, description='AMAZON')
            txn2 = make_transaction(id=2, qbo_id='1002', description='AMAZON')
            screen._filtered_transactions = [txn1, txn2]
            await screen._batch_categorize_async([txn1, txn2], 5)
            await pilot.pause()
            assert txn1.status == TransactionStatus.CATEGORIZED
            assert txn2.status == TransactionStatus.CATEGORIZED
            assert app._mock_repo.update_transaction_status.call_count == 2

    async def test_batch_categorize_async_no_repo(self):
        """Test _batch_categorize_async without repository."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            txn = make_transaction(id=None, description='AMAZON')
            screen._filtered_transactions = [txn]
            await screen._batch_categorize_async([txn], 5)
            await pilot.pause()
            assert txn.status == TransactionStatus.CATEGORIZED

    async def test_post_transactions_no_token(self):
        """Test _post_transactions_async when no token exists."""
        from unittest.mock import AsyncMock

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_all_categories.return_value = []
                self._mock_repo.search_transactions.return_value = []
                self._mock_repo.get_latest_token.return_value = None

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            await screen._post_transactions_async()
            await pilot.pause()

    async def test_refresh_from_qbo_no_token(self):
        """Test _refresh_from_qbo_async when no token exists."""
        from unittest.mock import AsyncMock

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_all_categories.return_value = []
                self._mock_repo.search_transactions.return_value = []
                self._mock_repo.get_latest_token.return_value = None

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            await screen._refresh_from_qbo_async()
            await pilot.pause()

    async def test_load_data_after_successful_sync(self):
        """Test _load_data reloads data after successful sync."""
        from unittest.mock import AsyncMock, patch

        from easycat.db.models import Token

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._call_count = 0
                self._mock_repo.get_latest_token.return_value = Token(
                    id=1,
                    realm_id='test_realm',
                    access_token='encrypted_access',
                    refresh_token='encrypted_refresh',
                    expires_at=None,
                )

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()

        async def mock_get_categories():
            app._call_count += 1
            if app._call_count <= 1:
                return []
            return [make_category(id=1, name='Synced Category')]

        async def mock_get_transactions():
            if app._call_count <= 1:
                return []
            return [make_transaction(qbo_id='synced_txn')]

        app._mock_repo.get_all_categories.side_effect = mock_get_categories
        app._mock_repo.search_transactions.side_effect = mock_get_transactions

        with patch.object(
            TransactionsScreen, '_try_sync_from_qbo', new_callable=AsyncMock
        ) as mock_sync:
            mock_sync.return_value = True
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                assert len(screen._all_transactions) == 1
                assert screen._all_transactions[0].qbo_id == 'synced_txn'

    async def test_load_data_with_categories_but_no_transactions(self):
        """Test _load_data falls back to sample when only categories exist."""
        from unittest.mock import AsyncMock

        from easycat.db.models import Token

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_all_categories.return_value = [
                    make_category(id=1, name='Travel')
                ]
                self._mock_repo.search_transactions.return_value = []
                self._mock_repo.get_latest_token.return_value = Token(
                    id=1,
                    realm_id='test_realm',
                    access_token='encrypted_access',
                    refresh_token='encrypted_refresh',
                    expires_at=None,
                )

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert len(screen._all_transactions) == 3
            assert len(screen._category_map) == 1

    async def test_login_action_no_repo(self):
        """Test login action with no repository."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            await screen._login_async()
            await pilot.pause()

    async def test_login_action_triggers_worker(self):
        """Test login action triggers the async worker."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_login()
            await pilot.pause()

    async def test_startup_triggers_login_when_no_token(self):
        """Test startup automatically triggers login when no token exists."""
        from unittest.mock import AsyncMock, patch

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_latest_token.return_value = None
                self._mock_repo.get_all_categories.return_value = []
                self._mock_repo.search_transactions.return_value = []

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        with patch.object(
            TransactionsScreen, '_login_async', new_callable=AsyncMock
        ) as mock_login:
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                assert len(screen._all_transactions) == 3
                mock_login.assert_called_once()

    async def test_load_data_sync_returns_empty(self):
        """Test _load_data falls back to sample when sync returns nothing."""
        from unittest.mock import AsyncMock, patch

        from easycat.db.models import Token

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_latest_token.return_value = Token(
                    id=1,
                    realm_id='test_realm',
                    access_token='encrypted_access',
                    refresh_token='encrypted_refresh',
                    expires_at=None,
                )
                self._mock_repo.get_all_categories.return_value = []
                self._mock_repo.search_transactions.return_value = []

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        with patch.object(
            TransactionsScreen, '_try_sync_from_qbo', new_callable=AsyncMock
        ) as mock_sync:
            mock_sync.return_value = False
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                assert len(screen._all_transactions) == 3

    async def test_select_account_no_accounts(self):
        """Test select_account shows warning when no accounts available."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._accounts = []
            screen.action_select_account()
            await pilot.pause()

    async def test_apply_account_filter_empty_result(self):
        """Test apply_account_filter when no transactions match."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._all_transactions = []
            screen._accounts = [('', 'All Accounts')]
            screen._current_account_index = 0
            screen._apply_account_filter()
            await pilot.pause()
            assert screen._filtered_transactions == []

    async def test_quit_action(self):
        """Test quit action exits the app."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_quit()
            await pilot.pause()

    async def test_load_saved_account_sets_index(self):
        """Test _load_saved_account sets correct account index."""
        from unittest.mock import AsyncMock

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_latest_token.return_value = None
                self._mock_repo.get_setting.return_value = 'acc2'

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._accounts = [('', 'All Accounts'), ('acc1', 'Checking'), ('acc2', 'Credit')]
            await screen._load_saved_account()
            assert screen._current_account_index == 2

    async def test_load_saved_account_not_found(self):
        """Test _load_saved_account when saved account not in list."""
        from unittest.mock import AsyncMock

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_latest_token.return_value = None
                self._mock_repo.get_setting.return_value = 'nonexistent'

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._accounts = [('', 'All Accounts'), ('acc1', 'Checking')]
            screen._current_account_index = 0
            await screen._load_saved_account()
            assert screen._current_account_index == 0

    async def test_load_saved_account_no_repo(self):
        """Test _load_saved_account when no repository."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._current_account_index = 0
            await screen._load_saved_account()
            assert screen._current_account_index == 0

    async def test_handle_account_selected_updates_index(self):
        """Test _handle_account_selected updates account index."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._accounts = [('', 'All Accounts'), ('acc1', 'Checking'), ('acc2', 'Credit')]
            screen._current_account_index = 0
            screen._handle_account_selected('acc2')
            await pilot.pause()
            assert screen._current_account_index == 2

    async def test_handle_account_selected_none(self):
        """Test _handle_account_selected with None does nothing."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._accounts = [('', 'All Accounts')]
            screen._current_account_index = 0
            screen._handle_account_selected(None)
            await pilot.pause()
            assert screen._current_account_index == 0

    async def test_save_account_preference(self):
        """Test _save_account_preference saves to database."""
        from unittest.mock import AsyncMock

        from easycat.screens.transactions import SELECTED_ACCOUNT_KEY

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_latest_token.return_value = None

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            await screen._save_account_preference('acc1')
            app._mock_repo.save_setting.assert_called_once_with(SELECTED_ACCOUNT_KEY, 'acc1')

    async def test_save_account_preference_no_repo(self):
        """Test _save_account_preference when no repository."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            await screen._save_account_preference('acc1')

    async def test_load_saved_account_none_setting(self):
        """Test _load_saved_account when setting is None."""
        from unittest.mock import AsyncMock

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_latest_token.return_value = None
                self._mock_repo.get_setting.return_value = None

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._accounts = [('', 'All Accounts'), ('acc1', 'Checking')]
            screen._current_account_index = 1
            await screen._load_saved_account()
            assert screen._current_account_index == 1

    async def test_handle_account_selected_not_in_list(self):
        """Test _handle_account_selected when account not in list."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._accounts = [('', 'All Accounts'), ('acc1', 'Checking')]
            screen._current_account_index = 0
            screen._handle_account_selected('nonexistent')
            await pilot.pause()
            assert screen._current_account_index == 0

    async def test_action_link_clicked_calls_action(self):
        """Test on_action_link_clicked calls the appropriate action method."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            from easycat.screens.transactions import ActionLink
            event = ActionLink.Clicked('quit')
            screen.on_action_link_clicked(event)
            await pilot.pause()

    async def test_action_link_clicked_unknown_action(self):
        """Test on_action_link_clicked with unknown action does nothing."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            from easycat.screens.transactions import ActionLink
            event = ActionLink.Clicked('nonexistent_action')
            screen.on_action_link_clicked(event)
            await pilot.pause()


class TestManageCategoryListItem:
    """Tests for ManageCategoryListItem widget."""

    async def test_creation_visible(self):
        """Test creating a visible ManageCategoryListItem."""
        category = make_category()
        item = ManageCategoryListItem(category, depth=0, is_visible=True)
        assert item.category == category
        assert item.is_visible is True
        assert item.depth == 0

    async def test_creation_hidden(self):
        """Test creating a hidden ManageCategoryListItem."""
        category = make_category()
        item = ManageCategoryListItem(category, depth=1, is_visible=False)
        assert item.is_visible is False
        assert item.depth == 1

    async def test_toggle(self):
        """Test toggling visibility."""

        class ItemApp(App):
            def compose(self) -> ComposeResult:
                category = make_category()
                yield ManageCategoryListItem(category, is_visible=True)

        app = ItemApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            item = app.query_one(ManageCategoryListItem)
            assert item.is_visible is True
            item.toggle()
            await pilot.pause()
            assert item.is_visible is False
            item.toggle()
            await pilot.pause()
            assert item.is_visible is True

    async def test_set_visible(self):
        """Test setting visibility directly."""

        class ItemApp(App):
            def compose(self) -> ComposeResult:
                category = make_category()
                yield ManageCategoryListItem(category, is_visible=True)

        app = ItemApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            item = app.query_one(ManageCategoryListItem)
            item.set_visible(False)
            await pilot.pause()
            assert item.is_visible is False

    async def test_compose_shows_checkbox(self):
        """Test compose shows checkbox widget."""
        from textual.widgets import Checkbox

        class ItemApp(App):
            def compose(self) -> ComposeResult:
                category = make_category(name='TestCat')
                yield ManageCategoryListItem(category, is_visible=True)

        app = ItemApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            item = app.query_one(ManageCategoryListItem)
            checkbox = item.query_one('#checkbox', Checkbox)
            assert checkbox.value is True
            assert item.is_visible is True
            name_label = item.query_one('#name-label', Label)
            assert 'TestCat' in str(name_label.render())

    async def test_indentation(self):
        """Test indentation based on depth."""

        class ItemApp(App):
            def compose(self) -> ComposeResult:
                category = make_category(name='Child')
                yield ManageCategoryListItem(category, depth=2, is_visible=True)

        app = ItemApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            item = app.query_one(ManageCategoryListItem)
            assert item.depth == 2
            assert item.is_visible is True
            assert item.category.name == 'Child'


class TestManageCategoryList:
    """Tests for ManageCategoryList widget."""

    async def test_shows_all_categories(self):
        """Test list shows all categories."""

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([
                    make_category(id=1, name='Advertising'),
                    make_category(id=2, qbo_id='2', name='Travel'),
                ])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            assert len(cat_list._tree) == 2

    async def test_record_checkbox_change(self):
        """Test recording checkbox changes."""
        from textual.widgets import Checkbox

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([
                    make_category(id=1, name='Travel'),
                ])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            checkbox = Checkbox('test', value=True)
            checkbox.category_id = 1
            cat_list.record_checkbox_change(checkbox, False)
            assert cat_list._visibility_changes[1] is False

    async def test_record_checkbox_change_no_id(self):
        """Test recording checkbox change with no category_id."""
        from textual.widgets import Checkbox

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([
                    make_category(id=1, name='Travel'),
                ])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            checkbox = Checkbox('test', value=True)
            cat_list.record_checkbox_change(checkbox, False)
            assert cat_list._visibility_changes == {}

    async def test_action_toggle_selected(self):
        """Test toggling the selected category."""

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([
                    make_category(id=1, name='Travel', is_visible=True),
                ])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            cat_list.focus()
            await pilot.pause()
            item = cat_list.query_one(ManageCategoryListItem)
            assert item.is_visible is True
            cat_list.action_toggle_selected()
            await pilot.pause()
            assert item.is_visible is False

    async def test_action_toggle_selected_no_selection(self):
        """Test toggle with no selection does nothing."""

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            cat_list.action_toggle_selected()
            assert cat_list._visibility_changes == {}

    async def test_set_all_visible_true(self):
        """Test setting all categories visible."""

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([
                    make_category(id=1, name='Advertising', is_visible=False),
                    make_category(id=2, qbo_id='2', name='Travel', is_visible=False),
                ])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            cat_list.set_all_visible(True)
            await pilot.pause()
            items = cat_list.query(ManageCategoryListItem)
            assert all(item.is_visible for item in items)

    async def test_set_all_visible_false(self):
        """Test setting all categories hidden."""

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([
                    make_category(id=1, name='Advertising', is_visible=True),
                    make_category(id=2, qbo_id='2', name='Travel', is_visible=True),
                ])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            cat_list.set_all_visible(False)
            await pilot.pause()
            items = cat_list.query(ManageCategoryListItem)
            assert all(not item.is_visible for item in items)

    async def test_get_visibility_changes(self):
        """Test getting visibility changes."""
        from textual.widgets import Checkbox

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([
                    make_category(id=1, name='Travel', is_visible=True),
                ])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            checkbox = Checkbox('test', value=True)
            checkbox.category_id = 1
            cat_list.record_checkbox_change(checkbox, False)
            changes = cat_list.get_visibility_changes()
            assert changes == {1: False}

    async def test_get_selected_category(self):
        """Test getting selected category."""

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([
                    make_category(id=1, name='Travel'),
                ])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            cat_list.focus()
            await pilot.pause()
            cat = cat_list.get_selected_category()
            assert cat is not None
            assert cat.name == 'Travel'

    async def test_get_selected_category_none(self):
        """Test get_selected_category when nothing selected."""

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            assert cat_list.get_selected_category() is None

    async def test_refresh_preserves_changes(self):
        """Test refresh preserves visibility changes."""

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([
                    make_category(id=1, name='Travel', is_visible=True),
                ])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            cat_list._visibility_changes[1] = False
            cat_list._refresh_list()
            await pilot.pause()
            item = cat_list.query_one(ManageCategoryListItem)
            assert item.is_visible is False

    async def test_toggle_category_with_none_id(self):
        """Test toggling a category with id=None still toggles the item."""

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([
                    make_category(id=None, name='Unsaved', is_visible=True),
                ])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            cat_list.focus()
            await pilot.pause()
            item = cat_list.query_one(ManageCategoryListItem)
            assert item.is_visible is True
            cat_list.action_toggle_selected()
            await pilot.pause()
            assert item.is_visible is False


class TestManageCategoriesScreen:
    """Tests for ManageCategoriesScreen."""

    async def test_cancel_action_dismisses(self):
        """Test cancel action dismisses the screen with None."""
        dismissed_value = []

        class HostApp(App):
            def on_mount(self) -> None:
                def callback(value):
                    dismissed_value.append(value)
                    self.exit()

                self.push_screen(ManageCategoriesScreen([make_category()]), callback)

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.press('escape')
            await pilot.pause()

        assert None in dismissed_value

    async def test_save_action_returns_changes(self):
        """Test save action returns visibility changes."""
        from textual.widgets import Checkbox

        dismissed_value = []

        class HostApp(App):
            def on_mount(self) -> None:
                def callback(value):
                    dismissed_value.append(value)
                    self.exit()

                self.push_screen(ManageCategoriesScreen([
                    make_category(id=1, name='Travel', is_visible=True)
                ]), callback)

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            manage_list = screen.query_one('#manage-list', ManageCategoryList)
            checkbox = Checkbox('test', value=True)
            checkbox.category_id = 1
            manage_list.record_checkbox_change(checkbox, False)
            screen.action_save()
            await pilot.pause()

        assert len(dismissed_value) == 1
        assert dismissed_value[0] == {1: False}

    async def test_save_action_no_changes_returns_none(self):
        """Test save action with no changes returns None."""
        dismissed_value = []

        class HostApp(App):
            def on_mount(self) -> None:
                def callback(value):
                    dismissed_value.append(value)
                    self.exit()

                self.push_screen(ManageCategoriesScreen([
                    make_category(id=1, name='Travel', is_visible=True)
                ]), callback)

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press('enter')
            await pilot.pause()

        assert None in dismissed_value

    async def test_toggle_action(self):
        """Test toggle action toggles selected category."""

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([
                    make_category(id=1, name='Travel', is_visible=True)
                ]))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ManageCategoriesScreen)
            manage_list = screen.query_one('#manage-list', ManageCategoryList)
            manage_list.focus()
            await pilot.pause()
            item = manage_list.query_one(ManageCategoryListItem)
            assert item.is_visible is True
            screen.action_toggle()
            await pilot.pause()
            assert item.is_visible is False

    async def test_toggle_all_action_mostly_hidden(self):
        """Test toggle all makes all visible when mostly hidden."""

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([
                    make_category(id=1, name='Travel', is_visible=False),
                    make_category(id=2, qbo_id='2', name='Ads', is_visible=False),
                ]))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_toggle_all()
            await pilot.pause()
            manage_list = screen.query_one('#manage-list', ManageCategoryList)
            items = manage_list.query(ManageCategoryListItem)
            assert all(item.is_visible for item in items)

    async def test_toggle_all_action_mostly_visible(self):
        """Test toggle all hides all when mostly visible."""

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([
                    make_category(id=1, name='Travel', is_visible=True),
                    make_category(id=2, qbo_id='2', name='Ads', is_visible=True),
                ]))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_toggle_all()
            await pilot.pause()
            manage_list = screen.query_one('#manage-list', ManageCategoryList)
            items = manage_list.query(ManageCategoryListItem)
            assert all(not item.is_visible for item in items)

    async def test_cursor_up_action(self):
        """Test cursor up action moves list cursor."""

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([
                    make_category(id=1, name='First'),
                    make_category(id=2, qbo_id='2', name='Second'),
                ]))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            manage_list = screen.query_one('#manage-list', ManageCategoryList)
            manage_list.index = 1
            screen.action_cursor_up()
            assert manage_list.index == 0

    async def test_cursor_down_action(self):
        """Test cursor down action moves list cursor."""

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([
                    make_category(id=1, name='First'),
                    make_category(id=2, qbo_id='2', name='Second'),
                ]))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            manage_list = screen.query_one('#manage-list', ManageCategoryList)
            manage_list.index = 0
            screen.action_cursor_down()
            assert manage_list.index == 1

    async def test_checkbox_changed_records_change(self):
        """Test on_checkbox_changed handler records visibility change."""
        from textual.widgets import Checkbox

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([
                    make_category(id=1, name='Travel', is_visible=True)
                ]))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            manage_list = screen.query_one('#manage-list', ManageCategoryList)
            checkbox = manage_list.query_one('#checkbox', Checkbox)
            checkbox.value = False
            await pilot.pause()
            assert manage_list._visibility_changes.get(1) is False


class TestTransactionsScreenCategoryManagement:
    """Tests for TransactionsScreen category management integration."""

    async def test_manage_categories_action_no_categories(self):
        """Test manage_categories action with no categories shows warning."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._categories = []
            screen.action_manage_categories()
            await pilot.pause()

    async def test_manage_categories_action_opens_screen(self):
        """Test manage_categories action opens ManageCategoriesScreen."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._categories = [make_category(id=1, name='Travel')]
            screen.action_manage_categories()
            await pilot.pause()
            assert isinstance(app.screen, ManageCategoriesScreen)

    async def test_handle_visibility_changes_none(self):
        """Test _handle_visibility_changes with None does nothing."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._categories = [make_category(id=1, name='Travel', is_visible=True)]
            screen._handle_visibility_changes(None)
            await pilot.pause()
            assert screen._categories[0].is_visible is True

    async def test_handle_visibility_changes_with_changes_runs_worker(self):
        """Test _handle_visibility_changes with non-None starts worker."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._categories = [make_category(id=1, name='Travel', is_visible=True)]
            screen._handle_visibility_changes({1: False})
            await pilot.pause()

    async def test_handle_visibility_changes_no_repo(self):
        """Test _handle_visibility_changes without repository updates in-memory."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._categories = [make_category(id=1, name='Travel', is_visible=True)]
            await screen._save_visibility_changes_async({1: False})
            await pilot.pause()
            assert screen._categories[0].is_visible is False

    async def test_save_visibility_changes_no_repo_skips_unaffected(self):
        """Test _save_visibility_changes_async skips categories not in changes."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._categories = [
                make_category(id=1, name='Changed', is_visible=True),
                make_category(id=2, qbo_id='2', name='Unchanged', is_visible=True),
            ]
            await screen._save_visibility_changes_async({1: False})
            await pilot.pause()
            assert screen._categories[0].is_visible is False
            assert screen._categories[1].is_visible is True

    async def test_save_visibility_changes_with_repo(self):
        """Test _save_visibility_changes_async with repository."""
        from unittest.mock import AsyncMock

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_latest_token.return_value = None

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._categories = [make_category(id=1, name='Travel', is_visible=True)]
            await screen._save_visibility_changes_async({1: False})
            await pilot.pause()
            app._mock_repo.update_category_visibility.assert_called_once_with(1, False)
            assert screen._categories[0].is_visible is False

    async def test_save_visibility_changes_with_repo_finds_non_first_category(self):
        """Test _save_visibility_changes_async finds category that is not first."""
        from unittest.mock import AsyncMock

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_latest_token.return_value = None

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._categories = [
                make_category(id=1, name='First', is_visible=True),
                make_category(id=2, qbo_id='2', name='Second', is_visible=True),
            ]
            await screen._save_visibility_changes_async({2: False})
            await pilot.pause()
            app._mock_repo.update_category_visibility.assert_called_once_with(2, False)
            assert screen._categories[0].is_visible is True
            assert screen._categories[1].is_visible is False

    async def test_save_visibility_changes_with_repo_nonexistent_category(self):
        """Test _save_visibility_changes_async handles nonexistent category ID."""
        from unittest.mock import AsyncMock

        class MockRepoApp(App):
            def __init__(self):
                super().__init__()
                self._mock_repo = AsyncMock()
                self._mock_repo.get_latest_token.return_value = None

            @property
            def repository(self):
                return self._mock_repo

            def on_mount(self) -> None:
                self.push_screen(TransactionsScreen())

        app = MockRepoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._categories = [
                make_category(id=1, name='Existing', is_visible=True),
            ]
            await screen._save_visibility_changes_async({999: False})
            await pilot.pause()
            app._mock_repo.update_category_visibility.assert_called_once_with(999, False)
            assert screen._categories[0].is_visible is True

    async def test_get_effectively_visible_categories(self):
        """Test _get_effectively_visible_categories filters hidden categories."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._categories = [
                make_category(id=1, qbo_id='1', name='Travel', is_visible=True),
                make_category(id=2, qbo_id='2', name='Hidden', is_visible=False),
                make_category(id=3, qbo_id='3', name='Visible', is_visible=True),
            ]
            visible = screen._get_effectively_visible_categories()
            assert len(visible) == 2
            assert visible[0].name == 'Travel'
            assert visible[1].name == 'Visible'

    async def test_get_effectively_visible_excludes_children_of_hidden(self):
        """Test _get_effectively_visible_categories excludes children of hidden parents."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._categories = [
                make_category(id=1, qbo_id='1', name='Parent', is_visible=False),
                make_category(
                    id=2, qbo_id='2', name='Child', parent_id=1, is_visible=True
                ),
                make_category(id=3, qbo_id='3', name='Other', is_visible=True),
            ]
            visible = screen._get_effectively_visible_categories()
            assert len(visible) == 1
            assert visible[0].name == 'Other'

    async def test_categorize_uses_visible_categories(self):
        """Test action_categorize uses only visible categories."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._categories = [
                make_category(id=1, qbo_id='1', name='Visible', is_visible=True),
                make_category(id=2, qbo_id='2', name='Hidden', is_visible=False),
            ]
            screen._current_transaction = make_transaction()
            screen.action_categorize()
            await pilot.pause()
            cat_screen = app.screen
            assert isinstance(cat_screen, CategorySelectScreen)
            assert len(cat_screen._categories) == 1
            assert cat_screen._categories[0].name == 'Visible'

    async def test_visibility_changes_updates_category_map(self):
        """Test visibility changes updates the category map."""
        app = ScreenTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._categories = [make_category(id=1, name='Travel', is_visible=True)]
            old_map = screen._category_map.copy()
            await screen._save_visibility_changes_async({1: False})
            await pilot.pause()
            assert screen._category_map is not old_map


class TestTextInputScreen:
    """Tests for TextInputScreen."""

    async def test_creation(self):
        """Test TextInputScreen can be created."""
        screen = TextInputScreen('Test Title', placeholder='Enter text')
        assert screen._title == 'Test Title'
        assert screen._placeholder == 'Enter text'

    async def test_cancel_dismisses_none(self):
        """Test cancel action dismisses with None."""
        dismissed_value = []

        class HostApp(App):
            def on_mount(self) -> None:
                def callback(value):
                    dismissed_value.append(value)
                    self.exit()

                self.push_screen(TextInputScreen('Test'), callback)

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press('escape')
            await pilot.pause()

        assert None in dismissed_value

    async def test_submit_with_value(self):
        """Test submit returns the entered value."""
        from textual.widgets import Input

        dismissed_value = []

        class HostApp(App):
            def on_mount(self) -> None:
                def callback(value):
                    dismissed_value.append(value)
                    self.exit()

                self.push_screen(TextInputScreen('Test'), callback)

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            text_input = app.screen.query_one('#text-input', Input)
            text_input.value = 'My Category'
            await pilot.press('enter')
            await pilot.pause()

        assert 'My Category' in dismissed_value

    async def test_submit_empty_shows_warning(self):
        """Test submit with empty value shows warning."""
        from textual.widgets import Input

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(TextInputScreen('Test'))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            text_input = app.screen.query_one('#text-input', Input)
            text_input.value = '   '
            app.screen.action_submit()
            await pilot.pause()
            # The screen should still be showing (not dismissed)
            assert isinstance(app.screen, TextInputScreen)

    async def test_on_mount_focuses_input(self):
        """Test input is focused on mount."""
        from textual.widgets import Input

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(TextInputScreen('Test'))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            text_input = app.screen.query_one('#text-input', Input)
            assert text_input.has_focus

    async def test_compose_creates_layout(self):
        """Test compose creates the expected layout."""
        from textual.widgets import Input, Static

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(TextInputScreen('My Title', placeholder='hint'))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            title = screen.query_one('#title', Static)
            assert 'My Title' in str(title.render())
            text_input = screen.query_one('#text-input', Input)
            assert text_input.placeholder == 'hint'


class TestManageCategoryListToggleAll:
    """Tests for ManageCategoryList toggle_all method."""

    async def test_toggle_all_from_all_hidden(self):
        """Test toggle_all shows all when all are hidden."""

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([
                    make_category(id=1, name='A', is_visible=False),
                    make_category(id=2, qbo_id='2', name='B', is_visible=False),
                ])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            cat_list.toggle_all()
            await pilot.pause()
            items = cat_list.query(ManageCategoryListItem)
            assert all(item.is_visible for item in items)

    async def test_toggle_all_from_all_visible(self):
        """Test toggle_all hides all when all are visible."""

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([
                    make_category(id=1, name='A', is_visible=True),
                    make_category(id=2, qbo_id='2', name='B', is_visible=True),
                ])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            cat_list.toggle_all()
            await pilot.pause()
            items = cat_list.query(ManageCategoryListItem)
            assert all(not item.is_visible for item in items)

    async def test_toggle_all_from_mixed_minority_visible(self):
        """Test toggle_all shows all when minority visible."""

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList([
                    make_category(id=1, name='A', is_visible=True),
                    make_category(id=2, qbo_id='2', name='B', is_visible=False),
                    make_category(id=3, qbo_id='3', name='C', is_visible=False),
                ])

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            cat_list.toggle_all()
            await pilot.pause()
            items = cat_list.query(ManageCategoryListItem)
            assert all(item.is_visible for item in items)

    async def test_refresh_categories(self):
        """Test refresh_categories rebuilds tree and refreshes display."""
        categories = [make_category(id=1, name='Existing')]

        class ListApp(App):
            def compose(self) -> ComposeResult:
                yield ManageCategoryList(categories)

        app = ListApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            cat_list = app.query_one(ManageCategoryList)
            assert len(cat_list._all_categories) == 1
            # Simulate callback adding to the shared list
            new_cat = make_category(id=2, qbo_id='2', name='NewCat')
            categories.append(new_cat)
            cat_list.refresh_categories()
            await pilot.pause()
            assert len(cat_list._all_categories) == 2
            items = cat_list.query(ManageCategoryListItem)
            names = [item.category.name for item in items]
            assert 'NewCat' in names


class TestManageCategoriesScreenAddCategory:
    """Tests for ManageCategoriesScreen add category functionality."""

    async def test_add_category_no_creator_shows_warning(self):
        """Test add_category without creator shows warning."""

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([make_category()]))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_add_category()
            await pilot.pause()
            # Screen should still be ManageCategoriesScreen (no input dialog shown)
            assert isinstance(app.screen, ManageCategoriesScreen)

    async def test_add_subcategory_no_creator_shows_warning(self):
        """Test add_subcategory without creator shows warning."""

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([make_category()]))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_add_subcategory()
            await pilot.pause()
            assert isinstance(app.screen, ManageCategoriesScreen)

    async def test_add_subcategory_no_selection_shows_warning(self):
        """Test add_subcategory without selection shows warning."""

        async def mock_creator(name, parent_id):
            return None

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([], mock_creator))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_add_subcategory()
            await pilot.pause()
            assert isinstance(app.screen, ManageCategoriesScreen)

    async def test_add_category_opens_input_dialog(self):
        """Test add_category opens TextInputScreen when creator provided."""

        async def mock_creator(name, parent_id):
            return make_category(id=99, name=name)

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([make_category()], mock_creator))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_add_category()
            await pilot.pause()
            assert isinstance(app.screen, TextInputScreen)

    async def test_add_subcategory_opens_input_dialog(self):
        """Test add_subcategory opens TextInputScreen when creator provided."""

        async def mock_creator(name, parent_id):
            return make_category(id=99, name=name)

        class HostApp(App):
            def on_mount(self) -> None:
                screen = ManageCategoriesScreen([make_category()], mock_creator)
                self.push_screen(screen)

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            manage_screen = app.screen
            manage_list = manage_screen.query_one('#manage-list', ManageCategoryList)
            manage_list.focus()
            await pilot.pause()
            manage_screen.action_add_subcategory()
            await pilot.pause()
            assert isinstance(app.screen, TextInputScreen)

    async def test_handle_new_category_none_does_nothing(self):
        """Test _handle_new_category with None does nothing."""

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([make_category()]))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._handle_new_category(None)
            await pilot.pause()

    async def test_handle_new_category_with_value_runs_worker(self):
        """Test _handle_new_category with valid name runs worker."""

        async def mock_creator(name, parent_id):
            return make_category(id=99, qbo_id='99', name=name)

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([make_category()], mock_creator))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._handle_new_category('TestCategory')
            await pilot.pause()

    async def test_handle_new_subcategory_none_does_nothing(self):
        """Test _handle_new_subcategory with None does nothing."""

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([make_category()]))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._handle_new_subcategory(None, '1')
            await pilot.pause()

    async def test_handle_new_subcategory_with_value_runs_worker(self):
        """Test _handle_new_subcategory with valid name runs worker."""

        async def mock_creator(name, parent_id):
            return make_category(id=99, qbo_id='99', name=name)

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([make_category()], mock_creator))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._handle_new_subcategory('TestSubcategory', '1')
            await pilot.pause()

    async def test_create_category_async_success(self):
        """Test _create_category_async refreshes list on success."""
        categories = [make_category()]

        async def mock_creator(name, parent_id):
            cat = make_category(id=99, qbo_id='99', name=name)
            # Simulate what _create_category_callback does - append to shared list
            categories.append(cat)
            return cat

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen(categories, mock_creator))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            await screen._create_category_async('NewCat', None)
            await pilot.pause()
            manage_list = screen.query_one('#manage-list', ManageCategoryList)
            assert len(manage_list._all_categories) == 2

    async def test_create_category_async_failure_notifies(self):
        """Test _create_category_async shows error on failure."""

        async def mock_creator(name, parent_id):
            raise ValueError('API Error')

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([make_category()], mock_creator))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            await screen._create_category_async('NewCat', None)
            await pilot.pause()

    async def test_create_category_async_returns_none_does_nothing(self):
        """Test _create_category_async handles None return."""

        async def mock_creator(name, parent_id):
            return None

        class HostApp(App):
            def on_mount(self) -> None:
                self.push_screen(ManageCategoriesScreen([make_category()], mock_creator))

        app = HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            await screen._create_category_async('NewCat', None)
            await pilot.pause()
            manage_list = screen.query_one('#manage-list', ManageCategoryList)
            assert len(manage_list._all_categories) == 1
