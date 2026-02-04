"""Main transaction review screen."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from easycat.db.models import Category, Transaction, TransactionStatus
from easycat.screens.categories import CategorySelectScreen, ManageCategoriesScreen
from easycat.widgets.transaction_table import TransactionTable

SELECTED_ACCOUNT_KEY = 'selected_account_id'


class ActionLink(Static):
    """Clickable action link."""

    DEFAULT_CSS = """
    ActionLink {
        height: 1;
        padding: 0;
    }

    ActionLink:hover {
        background: $primary-darken-2;
        text-style: bold;
    }
    """

    class Clicked(Message):
        """Message emitted when action link is clicked."""

        def __init__(self, action: str) -> None:
            super().__init__()
            self.action = action

    def __init__(self, label: str, action: str, **kwargs) -> None:
        super().__init__(label, **kwargs)
        self._action = action

    def on_click(self) -> None:
        """Handle click event."""
        self.post_message(self.Clicked(self._action))


class ConfirmBatchScreen(ModalScreen[bool]):
    """Modal screen to confirm batch categorization."""

    DEFAULT_CSS = """
    ConfirmBatchScreen {
        align: center middle;
    }

    #confirm-dialog {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #confirm-dialog #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #confirm-dialog #message {
        text-align: center;
        margin-bottom: 1;
    }

    #confirm-dialog #buttons {
        height: auto;
        align: center middle;
    }

    #confirm-dialog Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding('y', 'yes', 'Yes', show=True),
        Binding('n', 'no', 'No', show=True),
        Binding('escape', 'no', 'Cancel', show=False),
    ]

    def __init__(self, count: int, description: str, category_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._count = count
        self._description = description
        self._category_name = category_name

    def compose(self) -> ComposeResult:
        """Create dialog layout."""
        with Container(id='confirm-dialog'):
            yield Label('Categorize Similar Transactions?', id='title')
            yield Label(
                f'Found {self._count} other pending transaction(s) with description:\n'
                f'[dim]{self._description[:45]}[/dim]\n\n'
                f'Categorize all as [bold]{self._category_name}[/bold]?',
                id='message'
            )
            with Container(id='buttons'):
                yield Button(r'\[Y]es', id='yes', variant='primary')
                yield Button(r'\[N]o', id='no')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        self.dismiss(event.button.id == 'yes')

    def action_yes(self) -> None:
        """Confirm batch categorization."""
        self.dismiss(True)

    def action_no(self) -> None:
        """Cancel batch categorization."""
        self.dismiss(False)


class AccountListItem(ListItem):
    """List item for an account."""

    def __init__(self, account_id: str, account_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.account_id = account_id
        self.account_name = account_name

    def compose(self) -> ComposeResult:
        """Create list item content."""
        yield Label(self.account_name)


class AccountList(ListView):
    """Filterable list of accounts."""

    BINDINGS = [
        ('j', 'cursor_down', 'Down'),
        ('k', 'cursor_up', 'Up'),
    ]

    def __init__(
        self, accounts: list[tuple[str, str]], current_account_id: str | None = None, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._all_accounts = accounts
        self._filtered_accounts: list[tuple[str, str]] = accounts.copy()
        self._current_account_id = current_account_id
        self._refresh_counter = 0

    def on_mount(self) -> None:
        """Populate list on mount."""
        self._refresh_list()
        self.call_after_refresh(self._select_current_account)

    def _select_current_account(self) -> None:
        """Select the current account in the list."""
        if self._current_account_id is None:
            return
        for i, (account_id, _) in enumerate(self._filtered_accounts):
            if account_id == self._current_account_id:
                self.index = i
                return

    def filter(self, query: str) -> None:
        """Filter accounts by query string."""
        query = query.lower().strip()
        if not query:
            self._filtered_accounts = self._all_accounts.copy()
        else:
            self._filtered_accounts = [
                (aid, name)
                for aid, name in self._all_accounts
                if query in name.lower()
            ]
        self._refresh_list()

    def get_selected_account(self) -> tuple[str, str] | None:
        """Get the currently selected account (id, name) tuple."""
        if self.highlighted_child is None:
            return None
        if isinstance(self.highlighted_child, AccountListItem):
            return self.highlighted_child.account_id, self.highlighted_child.account_name
        return None  # pragma: no cover - defensive, ListView only contains AccountListItems

    def _refresh_list(self) -> None:
        """Refresh the list with filtered accounts."""
        self._refresh_counter += 1
        self.clear()
        for account_id, account_name in self._filtered_accounts:
            item_id = f'acc-{self._refresh_counter}-{account_id or "all"}'
            self.append(AccountListItem(account_id, account_name, id=item_id))


class AccountSelectScreen(ModalScreen[str | None]):
    """Modal screen for selecting an account."""

    DEFAULT_CSS = """
    AccountSelectScreen {
        align: center middle;
    }

    #account-dialog {
        width: 60;
        height: 25;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #account-dialog #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #account-dialog #search {
        margin-bottom: 1;
    }

    #account-dialog #account-list {
        height: 1fr;
        border: solid $secondary;
    }

    #account-dialog #hint {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding('escape', 'cancel', 'Cancel', show=True),
        Binding('enter', 'select', 'Select', show=True, priority=True),
        Binding('up', 'cursor_up', 'Up', show=False, priority=True),
        Binding('down', 'cursor_down', 'Down', show=False, priority=True),
        Binding('j', 'cursor_down', 'Down', show=False, priority=True),
        Binding('k', 'cursor_up', 'Up', show=False, priority=True),
    ]

    def __init__(
        self, accounts: list[tuple[str, str]], current_account_id: str | None = None, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._accounts = accounts
        self._current_account_id = current_account_id

    def compose(self) -> ComposeResult:
        """Create dialog layout."""
        with Container(id='account-dialog'):
            yield Static('Select Account', id='title')
            yield Input(placeholder='Type to filter...', id='search')
            yield AccountList(self._accounts, self._current_account_id, id='account-list')
            yield Static('↑↓/jk: Navigate | Enter: Select | Esc: Cancel', id='hint')

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        account_list = self.query_one('#account-list', AccountList)
        account_list.filter(event.value)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle account selection from list."""
        self.action_select()

    def action_cancel(self) -> None:
        """Cancel account selection."""
        self.dismiss(None)

    def action_cursor_up(self) -> None:
        """Move cursor up in the account list."""
        account_list = self.query_one('#account-list', AccountList)
        account_list.action_cursor_up()

    def action_cursor_down(self) -> None:
        """Move cursor down in the account list."""
        account_list = self.query_one('#account-list', AccountList)
        account_list.action_cursor_down()

    def action_select(self) -> None:
        """Confirm account selection."""
        account_list = self.query_one('#account-list', AccountList)
        account = account_list.get_selected_account()
        if account:
            self.dismiss(account[0])
        else:
            self.notify('No account selected', severity='warning')


class StatusBar(Static):
    """Status bar showing summary information."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._account_name = ''
        self._total = 0
        self._pending = 0
        self._categorized = 0

    def compose(self) -> ComposeResult:
        """Create status bar content."""
        yield Label('', id='status-text')

    def set_account(self, account_name: str) -> None:
        """Update the displayed account name."""
        self._account_name = account_name
        self._refresh_text()

    def update_counts(self, total: int, pending: int, categorized: int) -> None:
        """Update the status bar counts."""
        self._total = total
        self._pending = pending
        self._categorized = categorized
        self._refresh_text()

    def _refresh_text(self) -> None:
        """Refresh the status bar text."""
        text = self.query_one('#status-text', Label)
        text.update(
            f'{self._account_name} | '
            f'Total: {self._total} | Pending: {self._pending} | Categorized: {self._categorized}'
        )


class TransactionsScreen(Screen):
    """Main screen for reviewing and categorizing transactions."""

    DEFAULT_CSS = """
    TransactionsScreen {
        layout: grid;
        grid-size: 2;
        grid-columns: 4fr 1fr;
    }

    #main-panel {
        height: 100%;
    }

    #table-container {
        height: 1fr;
        border: solid $secondary;
        margin: 0 1 1 1;
    }

    #side-panel {
        height: 100%;
    }

    #actions {
        height: auto;
        padding: 1;
        margin: 1;
        background: $surface-darken-1;
        border: solid $secondary;
    }

    #actions Label {
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding('c', 'categorize', 'Categorize', show=True, priority=True),
        Binding('s', 'split', 'Split', show=True, priority=True),
        Binding('p', 'post', 'Post', show=True, priority=True),
        Binding('r', 'refresh', 'Refresh', show=True, priority=True),
        Binding('a', 'select_account', 'Account', show=True, priority=True),
        Binding('m', 'manage_categories', 'Categories', show=True, priority=True),
        Binding('l', 'login', 'Log in', show=True, priority=True),
        Binding('q', 'quit', 'Quit', show=True, priority=True),
        Binding('enter', 'categorize', 'Select', show=False, priority=True),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_transaction: Transaction | None = None
        self._all_transactions: list[Transaction] = []
        self._filtered_transactions: list[Transaction] = []
        self._categories: list[Category] = []
        self._category_map: dict[int, tuple[str, str | None]] = {}
        self._accounts: list[tuple[str, str]] = []
        self._current_account_index = 0

    def _build_category_map(self) -> dict[int, tuple[str, str | None]]:
        """Build category map with parent names.

        Returns a dict mapping category ID to (name, parent_name) tuple.
        Parent_id stores the parent's qbo_id (as int), so we look up by qbo_id.
        """
        qbo_id_to_name: dict[str, str] = {c.qbo_id: c.name for c in self._categories}

        result: dict[int, tuple[str, str | None]] = {}
        for c in self._categories:
            if c.id is not None:
                parent_name = None
                if c.parent_id is not None:
                    parent_name = qbo_id_to_name.get(str(c.parent_id))
                result[c.id] = (c.name, parent_name)
        return result

    def compose(self) -> ComposeResult:
        """Create screen layout."""
        with Vertical(id='main-panel'):
            with Container(id='table-container'):
                yield TransactionTable(id='transactions')
        with Vertical(id='side-panel'):
            with Container(id='actions'):
                yield ActionLink('[C]ategorize selected', 'categorize', markup=False)
                yield ActionLink('[S]plit transaction', 'split', markup=False)
                yield ActionLink('[P]ost to QuickBooks', 'post', markup=False)
                yield ActionLink('[R]efresh from QuickBooks', 'refresh', markup=False)
                yield ActionLink('Select [A]ccount', 'select_account', markup=False)
                yield ActionLink('[M]anage categories', 'manage_categories', markup=False)
                yield ActionLink('[L]og in', 'login', markup=False)
                yield ActionLink('[Q]uit', 'quit', markup=False)
        yield StatusBar()

    async def on_mount(self) -> None:
        """Handle screen mount."""
        await self._load_data()

    async def _load_data(self) -> None:
        """Load transactions and categories from database, syncing from QBO if needed."""
        repo = self.app.repository
        if repo is None:
            return

        token = await repo.get_latest_token()
        if token is None:
            self.notify('No authentication found. Starting OAuth flow...', severity='information')
            self.run_worker(self._login_async())
            return

        self._categories = await repo.get_all_categories()
        all_txns = await repo.search_transactions()

        if not self._categories or not all_txns:
            synced = await self._try_sync_from_qbo()
            if synced:
                self._categories = await repo.get_all_categories()
                all_txns = await repo.search_transactions()

        if not self._categories and not all_txns:
            return

        self._category_map = self._build_category_map()

        table = self.query_one('#transactions', TransactionTable)
        table.set_categories(self._category_map)

        if not all_txns:
            return

        self._all_transactions = all_txns
        self._build_account_list()
        await self._load_saved_account()
        self._apply_account_filter()

    async def _try_sync_from_qbo(self) -> bool:  # pragma: no cover
        """Try to sync from QuickBooks if we have valid credentials.

        Integration method composing auth, API, and sync modules.
        Component logic is tested in test_sync.py, test_auth.py, test_api.py.
        """
        repo = self.app.repository
        if repo is None:
            return False

        token = await repo.get_latest_token()
        if token is None:
            return False

        from easycat.api import QuickBooksClient
        from easycat.api.sync import sync_categories, sync_transactions
        from easycat.auth import OAuthClient

        try:
            oauth = OAuthClient(self.app.config.quickbooks, self.app.config.security)
            access_token = oauth.decrypt_token(token.access_token)

            if oauth.is_token_expired(token):
                result = await oauth.refresh_token(token.refresh_token)
                token.access_token = oauth.encrypt_token(result.access_token)
                token.refresh_token = oauth.encrypt_token(result.refresh_token)
                token.expires_at = result.expires_at
                await repo.save_token(token)
                access_token = result.access_token

            self.notify('Syncing with QuickBooks...', severity='information')

            async with QuickBooksClient(
                self.app.config.quickbooks, token.realm_id, access_token
            ) as client:
                await sync_categories(client, repo)
                await sync_transactions(client, repo)

            return True
        except Exception:
            return False

    def _build_account_list(self) -> None:
        """Build list of unique accounts from transactions."""
        seen: dict[str, str] = {}
        for txn in self._all_transactions:
            if txn.account_id not in seen:
                seen[txn.account_id] = txn.account_name
        self._accounts = list(seen.items())

    async def _load_saved_account(self) -> None:
        """Load saved account preference from database."""
        repo = self.app.repository
        if repo is None:
            return

        saved_account_id = await repo.get_setting(SELECTED_ACCOUNT_KEY)
        if saved_account_id is not None:
            for i, (account_id, _) in enumerate(self._accounts):
                if account_id == saved_account_id:
                    self._current_account_index = i
                    return

    def _apply_account_filter(self) -> None:
        """Show transactions for the selected account."""
        account_id, account_name = self._accounts[self._current_account_index]

        self._filtered_transactions = [
            t for t in self._all_transactions if t.account_id == account_id
        ]

        status_bar = self.query_one(StatusBar)
        status_bar.set_account(account_name)

        table = self.query_one('#transactions', TransactionTable)
        table.load_transactions(self._filtered_transactions)
        self._update_status_bar(self._filtered_transactions)

        if self._filtered_transactions:
            table.focus()
            first_pending = next(
                (i for i, t in enumerate(self._filtered_transactions)
                 if t.status == TransactionStatus.PENDING),
                0
            )
            table.move_cursor(row=first_pending)
            self._current_transaction = self._filtered_transactions[first_pending]

    def _update_status_bar(self, transactions: list[Transaction]) -> None:
        """Update the status bar with transaction counts."""
        total = len(transactions)
        pending = sum(1 for t in transactions if t.status == TransactionStatus.PENDING)
        categorized = sum(1 for t in transactions if t.status == TransactionStatus.CATEGORIZED)
        status_bar = self.query_one(StatusBar)
        status_bar.update_counts(total, pending, categorized)

    def on_transaction_table_transaction_highlighted(
        self, event: TransactionTable.TransactionHighlighted
    ) -> None:
        """Handle transaction highlight change."""
        self._current_transaction = event.transaction

    def on_transaction_table_transaction_selected(
        self, event: TransactionTable.TransactionSelected
    ) -> None:
        """Handle transaction selection (Enter key)."""
        self.action_categorize()

    def on_action_link_clicked(self, event: ActionLink.Clicked) -> None:
        """Handle action link click."""
        action_method = getattr(self, f'action_{event.action}', None)
        if action_method:
            action_method()

    def _get_selected_transaction(self) -> Transaction | None:
        """Get the currently selected transaction from the table."""
        table = self.query_one('#transactions', TransactionTable)
        txn = table.get_current_transaction()
        if txn:
            self._current_transaction = txn
        return self._current_transaction

    def _get_effectively_visible_categories(self) -> list[Category]:
        """Get categories that are visible, excluding children of hidden parents."""
        hidden_qbo_ids: set[str] = set()
        for c in self._categories:
            if not c.is_visible:
                hidden_qbo_ids.add(c.qbo_id)

        result = []
        for c in self._categories:
            if not c.is_visible:
                continue
            if c.parent_id is not None and str(c.parent_id) in hidden_qbo_ids:
                continue
            result.append(c)
        return result

    def action_categorize(self) -> None:
        """Open category selection for current transaction."""
        txn = self._get_selected_transaction()
        if txn is None:
            self.notify('No transaction selected', severity='warning')
            return

        visible_categories = self._get_effectively_visible_categories()
        self.app.push_screen(
            CategorySelectScreen(txn, visible_categories), self._handle_category_selected
        )

    def _handle_category_selected(self, category_id: int | None) -> None:
        """Callback for when a category is selected from the category screen."""
        if category_id is not None and self._current_transaction:
            self.run_worker(self._assign_category_async(category_id))

    async def _assign_category_async(self, category_id: int) -> None:
        """Assign a category to the current transaction (async)."""
        import logging
        log = logging.getLogger('easycat.categorize')

        if self._current_transaction is None:
            return
        txn = self._current_transaction
        log.info(f'Categorizing txn id={txn.id}, qbo_id={txn.qbo_id}, cat={category_id}')
        txn.assigned_category_id = category_id
        txn.status = TransactionStatus.CATEGORIZED

        repo = self.app.repository
        if repo and txn.id:
            log.info(f'Updating DB for txn.id={txn.id}')
            await repo.update_transaction_status(txn.id, txn.status, category_id)
        else:
            log.warning(f'Skipping DB update: repo={repo is not None}, txn.id={txn.id}')

        table = self.query_one('#transactions', TransactionTable)
        table.update_transaction(txn)
        self._update_status_bar(self._filtered_transactions)
        self.notify(f'Categorized: {txn.description[:30]}')

        matching = [
            t for t in self._all_transactions
            if t.status == TransactionStatus.PENDING
            and t.description == txn.description
            and t.id != txn.id
        ]
        if matching:
            category_name = self._category_map.get(category_id, f'#{category_id}')
            self.app.push_screen(
                ConfirmBatchScreen(len(matching), txn.description, category_name),
                lambda confirmed: self._handle_batch_confirmed(confirmed, matching, category_id)
            )

    def _handle_batch_confirmed(
        self, confirmed: bool, transactions: list[Transaction], category_id: int
    ) -> None:
        """Handle batch categorization confirmation."""
        if confirmed:
            self.run_worker(self._batch_categorize_async(transactions, category_id))

    async def _batch_categorize_async(
        self, transactions: list[Transaction], category_id: int
    ) -> None:
        """Batch categorize multiple transactions."""
        repo = self.app.repository
        table = self.query_one('#transactions', TransactionTable)

        for txn in transactions:
            txn.assigned_category_id = category_id
            txn.status = TransactionStatus.CATEGORIZED
            if repo and txn.id:
                await repo.update_transaction_status(txn.id, txn.status, category_id)
            table.update_transaction(txn)

        self._update_status_bar(self._filtered_transactions)
        self.notify(f'Categorized {len(transactions)} similar transaction(s)')

    def action_split(self) -> None:
        """Open split dialog for current transaction."""
        txn = self._get_selected_transaction()
        if txn is None:
            self.notify('No transaction selected', severity='warning')
            return
        self.notify('Split functionality coming soon', severity='information')

    def action_post(self) -> None:
        """Post categorized transactions to QuickBooks."""
        self.notify('Posting to QuickBooks...', severity='information')
        self.run_worker(self._post_transactions_async())

    async def _post_transactions_async(self) -> None:  # pragma: no cover
        """Post categorized transactions to QuickBooks (async).

        Integration method composing auth, API, and sync modules.
        Component logic is tested in test_sync.py, test_auth.py, test_api.py.
        """
        import logging
        logging.basicConfig(
            filename='easycat.log',
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)s: %(message)s'
        )
        log = logging.getLogger('easycat.post')
        log.info('Starting post_transactions')

        repo = self.app.repository
        if repo is None:
            self.notify('Database not connected', severity='error')
            return

        token = await repo.get_latest_token()
        if token is None:
            self.notify('Not authenticated. Run OAuth flow first.', severity='error')
            return

        from easycat.api import QuickBooksClient
        from easycat.api.sync import post_categorized_transactions
        from easycat.auth import OAuthClient

        oauth = OAuthClient(self.app.config.quickbooks, self.app.config.security)
        access_token = oauth.decrypt_token(token.access_token)

        if oauth.is_token_expired(token):
            try:
                result = await oauth.refresh_token(token.refresh_token)
                token.access_token = oauth.encrypt_token(result.access_token)
                token.refresh_token = oauth.encrypt_token(result.refresh_token)
                token.expires_at = result.expires_at
                await repo.save_token(token)
                access_token = result.access_token
            except Exception as e:
                self.notify(f'Token refresh failed: {e}', severity='error')
                return

        db_categorized = await repo.get_transactions_by_status(TransactionStatus.CATEGORIZED)
        log.info(f'DB has {len(db_categorized)} CATEGORIZED transactions')
        for t in db_categorized:
            log.info(f'  - id={t.id}, qbo={t.qbo_id}, cat={t.assigned_category_id}')

        async with QuickBooksClient(
            self.app.config.quickbooks, token.realm_id, access_token
        ) as client:
            posted = await post_categorized_transactions(client, repo)

        log.info(f'Posted {len(posted)} transactions')
        if posted:
            for txn in posted:
                for i, t in enumerate(self._all_transactions):
                    if t.qbo_id == txn.qbo_id:
                        self._all_transactions[i] = txn
                        break

            self._apply_account_filter()
            self.notify(f'Posted {len(posted)} transactions to QuickBooks')
        else:
            self.notify('No transactions to post', severity='information')

    def action_refresh(self) -> None:
        """Refresh transactions from QuickBooks."""
        self.notify('Refreshing from QuickBooks...', severity='information')
        self.run_worker(self._refresh_from_qbo_async())

    async def _refresh_from_qbo_async(self) -> None:  # pragma: no cover
        """Refresh transactions from QuickBooks (async).

        Integration method composing auth, API, and sync modules.
        Component logic is tested in test_sync.py, test_auth.py, test_api.py.
        """
        repo = self.app.repository
        if repo is None:
            self.notify('Database not connected', severity='error')
            return

        token = await repo.get_latest_token()
        if token is None:
            self.notify('Not authenticated. Run OAuth flow first.', severity='error')
            return

        from easycat.api import QuickBooksClient
        from easycat.api.sync import sync_categories, sync_transactions
        from easycat.auth import OAuthClient

        oauth = OAuthClient(self.app.config.quickbooks, self.app.config.security)
        access_token = oauth.decrypt_token(token.access_token)

        if oauth.is_token_expired(token):
            try:
                result = await oauth.refresh_token(token.refresh_token)
                token.access_token = oauth.encrypt_token(result.access_token)
                token.refresh_token = oauth.encrypt_token(result.refresh_token)
                token.expires_at = result.expires_at
                await repo.save_token(token)
                access_token = result.access_token
            except Exception as e:
                self.notify(f'Token refresh failed: {e}', severity='error')
                return

        self.notify('Syncing with QuickBooks...', severity='information')

        async with QuickBooksClient(
            self.app.config.quickbooks, token.realm_id, access_token
        ) as client:
            self._categories = await sync_categories(client, repo)
            self._category_map = self._build_category_map()
            self._all_transactions = await sync_transactions(client, repo)

        table = self.query_one('#transactions', TransactionTable)
        table.set_categories(self._category_map)

        self._build_account_list()
        self._current_account_index = 0
        self._apply_account_filter()

        self.notify(
            f'Synced {len(self._categories)} categories, '
            f'{len(self._all_transactions)} transactions'
        )

    def action_select_account(self) -> None:
        """Open account selection modal."""
        if not self._accounts:
            self.notify('No accounts available', severity='warning')
            return

        current_account_id = self._accounts[self._current_account_index][0]
        self.app.push_screen(
            AccountSelectScreen(self._accounts, current_account_id),
            self._handle_account_selected
        )

    def _handle_account_selected(self, account_id: str | None) -> None:
        """Handle account selection from modal."""
        if account_id is None:
            return

        for i, (aid, _) in enumerate(self._accounts):
            if aid == account_id:
                self._current_account_index = i
                break

        self._apply_account_filter()
        self.run_worker(self._save_account_preference(account_id))

    async def _save_account_preference(self, account_id: str) -> None:
        """Save selected account to database."""
        repo = self.app.repository
        if repo is None:
            return
        await repo.save_setting(SELECTED_ACCOUNT_KEY, account_id)

    def action_manage_categories(self) -> None:
        """Open category visibility management modal."""
        if not self._categories:
            self.notify('No categories available', severity='warning')
            return

        self.app.push_screen(
            ManageCategoriesScreen(self._categories, self._create_category_callback),
            self._handle_visibility_changes,
        )

    async def _create_category_callback(
        self, name: str, parent_qbo_id: str | None
    ) -> Category | None:  # pragma: no cover
        """Create a category in QuickBooks and save to local DB.

        Integration method composing auth, API, and repository modules.
        Component logic tested in test_api.py and test_repository.py.
        """
        from datetime import datetime

        from easycat.api import QuickBooksClient
        from easycat.auth import OAuthClient
        from easycat.db.models import Category

        repo = self.app.repository
        if repo is None:
            return None

        token = await repo.get_latest_token()
        if token is None:
            return None

        oauth = OAuthClient(self.app.config.quickbooks, self.app.config.security)
        access_token = oauth.decrypt_token(token.access_token)

        async with QuickBooksClient(
            self.app.config.quickbooks, token.realm_id, access_token
        ) as client:
            qbo_account = await client.create_account(name, 'Expense', parent_qbo_id)

        parent_id_int = int(parent_qbo_id) if parent_qbo_id else None
        full_name = name
        if parent_qbo_id:
            for cat in self._categories:
                if cat.qbo_id == parent_qbo_id:
                    full_name = f'{cat.full_name}:{name}'
                    break

        new_category = Category(
            id=None,
            qbo_id=qbo_account.id,
            name=qbo_account.name,
            full_name=full_name,
            parent_id=parent_id_int,
            account_type=qbo_account.account_type,
            is_visible=True,
            display_order=0,
            synced_at=datetime.now(),
        )
        saved_category = await repo.save_category(new_category)
        self._categories.append(saved_category)
        self._category_map = self._build_category_map()
        return saved_category

    def _handle_visibility_changes(self, changes: dict[int, bool] | None) -> None:
        """Handle visibility changes from the manage categories screen."""
        if changes is None:
            return
        self.run_worker(self._save_visibility_changes_async(changes))

    async def _save_visibility_changes_async(self, changes: dict[int, bool]) -> None:
        """Save category visibility changes to database."""
        repo = self.app.repository
        if repo is None:
            for cat in self._categories:
                if cat.id in changes:
                    cat.is_visible = changes[cat.id]
            self._category_map = self._build_category_map()
            self.notify(f'Updated {len(changes)} category visibility settings')
            return

        for cat_id, is_visible in changes.items():
            await repo.update_category_visibility(cat_id, is_visible)
            for cat in self._categories:
                if cat.id == cat_id:
                    cat.is_visible = is_visible
                    break

        self._category_map = self._build_category_map()
        self.notify(f'Updated {len(changes)} category visibility settings')

    def action_login(self) -> None:
        """Start OAuth authentication flow."""
        self.notify('Logging in...', severity='information')
        self.run_worker(self._login_async())

    async def _login_async(self) -> None:  # pragma: no cover
        """Run OAuth authentication flow.

        Integration method using auth module. Component logic tested in test_auth.py.
        """
        import logging
        import traceback

        logging.basicConfig(
            filename='easycat.log',
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)s: %(message)s'
        )
        log = logging.getLogger('easycat.auth')

        log.info('Starting OAuth authentication')

        repo = self.app.repository
        if repo is None:
            log.error('Database not connected')
            self.notify('Database not connected', severity='error')
            return

        from easycat.auth import OAuthClient, OAuthError
        from easycat.db.models import Token

        try:
            log.info('Creating OAuth client')
            oauth = OAuthClient(self.app.config.quickbooks, self.app.config.security)
            log.info(f'Redirect URI: {self.app.config.quickbooks.redirect_uri}')

            self.notify('Opening browser for QuickBooks authentication...', severity='information')

            log.info('Starting authorize flow')
            result = await oauth.authorize(open_browser=True)
            has_token = bool(result.access_token)
            log.info(f'OAuth result: realm={result.realm_id}, has_token={has_token}')

            if not result.realm_id:
                log.error('No realm ID received')
                self.notify('No realm ID received from QuickBooks', severity='error')
                return

            token = Token(
                id=None,
                realm_id=result.realm_id,
                access_token=oauth.encrypt_token(result.access_token),
                refresh_token=oauth.encrypt_token(result.refresh_token),
                expires_at=result.expires_at,
            )
            log.info(f'Saving token for realm {token.realm_id}')
            saved = await repo.save_token(token)
            log.info(f'Token saved: {saved is not None}')

            if saved:
                log.info(f'Authentication successful for realm {saved.realm_id}')
                self.notify(f'Logged in to realm {saved.realm_id}. Syncing...', severity='information')
                await self._sync_after_login(result.access_token, saved.realm_id)
            else:
                log.error('save_token returned None')
                self.notify('Failed to save token', severity='error')
        except OAuthError as e:
            log.error(f'OAuthError: {e}\n{traceback.format_exc()}')
            self.notify(f'Authentication failed: {e}', severity='error')
        except Exception as e:
            log.error(f'Exception: {e}\n{traceback.format_exc()}')
            self.notify(f'Authentication error: {e}', severity='error')

    async def _sync_after_login(self, access_token: str, realm_id: str) -> None:  # pragma: no cover
        """Sync data from QuickBooks after successful login.

        Integration method composing API and sync modules.
        Component logic is tested in test_sync.py, test_api.py.
        """
        from easycat.api import QuickBooksClient
        from easycat.api.sync import sync_categories, sync_transactions

        repo = self.app.repository
        if repo is None:
            return

        try:
            async with QuickBooksClient(
                self.app.config.quickbooks, realm_id, access_token
            ) as client:
                self._categories = await sync_categories(client, repo)
                self._category_map = self._build_category_map()
                self._all_transactions = await sync_transactions(client, repo)

            table = self.query_one('#transactions', TransactionTable)
            table.set_categories(self._category_map)

            self._build_account_list()
            self._current_account_index = 0
            self._apply_account_filter()

            self.notify(
                f'Synced {len(self._categories)} categories, '
                f'{len(self._all_transactions)} transactions'
            )
        except Exception as e:
            self.notify(f'Sync failed: {e}', severity='error')

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
