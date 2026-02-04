"""Category selection screen and widgets."""

import uuid
from collections.abc import Awaitable, Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Checkbox, Input, Label, ListItem, ListView, Static

from easycat.db.models import Category, Transaction

CategoryCreator = Callable[[str, str | None], Awaitable[Category | None]]


class TextInputScreen(ModalScreen[str | None]):
    """Modal screen for text input."""

    DEFAULT_CSS = """
    TextInputScreen {
        align: center middle;
    }

    #input-dialog {
        width: 50;
        height: 9;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #input-dialog #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #input-dialog #text-input {
        margin-bottom: 1;
    }

    #input-dialog #hint {
        text-align: center;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding('escape', 'cancel', 'Cancel', show=True),
        Binding('enter', 'submit', 'Submit', show=True, priority=True),
    ]

    def __init__(self, title: str, placeholder: str = '', **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        """Create dialog layout."""
        with Container(id='input-dialog'):
            yield Static(self._title, id='title')
            yield Input(placeholder=self._placeholder, id='text-input')
            yield Static('Enter: Submit | Esc: Cancel', id='hint')

    def on_mount(self) -> None:
        """Focus the input on mount."""
        self.query_one('#text-input', Input).focus()

    def action_cancel(self) -> None:
        """Cancel and dismiss without value."""
        self.dismiss(None)

    def action_submit(self) -> None:
        """Submit the input value."""
        text_input = self.query_one('#text-input', Input)
        value = text_input.value.strip()
        if value:
            self.dismiss(value)
        else:
            self.notify('Please enter a value', severity='warning')


class ManageCategoriesScreen(ModalScreen[dict[int, bool] | None]):
    """Modal screen for managing category visibility."""

    DEFAULT_CSS = """
    ManageCategoriesScreen {
        align: center middle;
    }

    #manage-dialog {
        width: 60;
        height: 30;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #manage-dialog #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #manage-dialog #manage-list {
        height: 1fr;
        border: solid $secondary;
    }

    #manage-dialog #hint {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding('escape', 'cancel', 'Cancel', show=True),
        Binding('enter', 'save', 'Save', show=True, priority=True),
        Binding('space', 'toggle', 'Toggle', show=True, priority=True),
        Binding('a', 'toggle_all', 'ToggleAll', show=True, priority=True),
        Binding('n', 'add_category', 'New', show=True, priority=True),
        Binding('s', 'add_subcategory', 'SubCat', show=True, priority=True),
        Binding('up', 'cursor_up', 'Up', show=False, priority=True),
        Binding('down', 'cursor_down', 'Down', show=False, priority=True),
        Binding('j', 'cursor_down', 'Down', show=False, priority=True),
        Binding('k', 'cursor_up', 'Up', show=False, priority=True),
    ]

    def __init__(
        self,
        categories: list[Category],
        category_creator: CategoryCreator | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._categories = categories
        self._category_creator = category_creator

    def compose(self) -> ComposeResult:
        """Create dialog layout."""
        with Container(id='manage-dialog'):
            yield Static('Manage Categories', id='title')
            yield ManageCategoryList(self._categories, id='manage-list')
            yield Static(
                'a: Toggle all | n: Add | s: SubCat | Enter: Save | Esc: Cancel', id='hint'
            )

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox state changes."""
        manage_list = self.query_one('#manage-list', ManageCategoryList)
        manage_list.record_checkbox_change(event.checkbox, event.value)

    def action_cancel(self) -> None:
        """Cancel and dismiss without saving."""
        self.dismiss(None)

    def action_save(self) -> None:
        """Save visibility changes and dismiss."""
        manage_list = self.query_one('#manage-list', ManageCategoryList)
        changes = manage_list.get_visibility_changes()
        self.dismiss(changes if changes else None)

    def action_toggle(self) -> None:
        """Toggle visibility of the selected category."""
        manage_list = self.query_one('#manage-list', ManageCategoryList)
        manage_list.action_toggle_selected()

    def action_toggle_all(self) -> None:
        """Toggle visibility of all categories."""
        manage_list = self.query_one('#manage-list', ManageCategoryList)
        manage_list.toggle_all()

    def action_add_category(self) -> None:
        """Add a new top-level expense category."""
        if self._category_creator is None:
            self.notify('Category creation not available', severity='warning')
            return
        self.app.push_screen(
            TextInputScreen('New Category', placeholder='Category name'),
            self._handle_new_category,
        )

    def _handle_new_category(self, name: str | None) -> None:
        """Handle the new category name from input dialog."""
        if name is None:
            return
        self.run_worker(self._create_category_async(name, None))

    def action_add_subcategory(self) -> None:
        """Add a subcategory of the selected category."""
        if self._category_creator is None:
            self.notify('Category creation not available', severity='warning')
            return
        manage_list = self.query_one('#manage-list', ManageCategoryList)
        parent = manage_list.get_selected_category()
        if parent is None:
            self.notify('Select a parent category first', severity='warning')
            return
        self.app.push_screen(
            TextInputScreen(f'New Subcategory of {parent.name}', placeholder='Subcategory name'),
            lambda name: self._handle_new_subcategory(name, parent.qbo_id),
        )

    def _handle_new_subcategory(self, name: str | None, parent_qbo_id: str) -> None:
        """Handle the new subcategory name from input dialog."""
        if name is None:
            return
        self.run_worker(self._create_category_async(name, parent_qbo_id))

    async def _create_category_async(self, name: str, parent_qbo_id: str | None) -> None:
        """Create a category asynchronously."""
        try:
            new_category = await self._category_creator(name, parent_qbo_id)
            if new_category is not None:
                manage_list = self.query_one('#manage-list', ManageCategoryList)
                manage_list.refresh_categories()
                self.notify(f'Created category: {new_category.name}')
        except Exception as e:
            self.notify(f'Failed to create category: {e}', severity='error')

    def action_cursor_up(self) -> None:
        """Move cursor up in the list."""
        manage_list = self.query_one('#manage-list', ManageCategoryList)
        manage_list.action_cursor_up()

    def action_cursor_down(self) -> None:
        """Move cursor down in the list."""
        manage_list = self.query_one('#manage-list', ManageCategoryList)
        manage_list.action_cursor_down()


class ManageCategoryList(ListView):
    """List of categories with visibility toggles."""

    BINDINGS = [
        ('j', 'cursor_down', 'Down'),
        ('k', 'cursor_up', 'Up'),
    ]

    def __init__(self, categories: list[Category], **kwargs) -> None:
        super().__init__(**kwargs)
        self._all_categories = categories
        self._tree = build_category_tree(categories)
        self._visibility_changes: dict[int, bool] = {}

    def on_mount(self) -> None:
        """Populate list on mount."""
        self._refresh_list()

    def record_checkbox_change(self, checkbox: Checkbox, value: bool) -> None:
        """Record a visibility change from a checkbox."""
        category_id = getattr(checkbox, 'category_id', None)
        if category_id is not None:
            self._visibility_changes[category_id] = value

    def action_toggle_selected(self) -> None:
        """Toggle visibility of the currently selected category."""
        if self.highlighted_child is None:
            return
        if isinstance(self.highlighted_child, ManageCategoryListItem):  # pragma: no branch
            item = self.highlighted_child
            item.toggle()

    def set_all_visible(self, visible: bool) -> None:
        """Set all categories to the same visibility state."""
        for child in self.children:
            if isinstance(child, ManageCategoryListItem):  # pragma: no branch
                item = child
                if item.is_visible != visible:
                    item.set_visible(visible)

    def toggle_all(self) -> None:
        """Toggle visibility of all categories based on majority state."""
        visible_count = sum(
            1 for child in self.children
            if isinstance(child, ManageCategoryListItem) and child.is_visible
        )
        total = len([c for c in self.children if isinstance(c, ManageCategoryListItem)])
        new_visible = visible_count <= total // 2
        self.set_all_visible(new_visible)

    def refresh_categories(self) -> None:
        """Rebuild tree from categories and refresh display."""
        self._tree = build_category_tree(self._all_categories)
        self._refresh_list()

    def get_visibility_changes(self) -> dict[int, bool]:
        """Get the dictionary of visibility changes."""
        return self._visibility_changes.copy()

    def get_selected_category(self) -> Category | None:
        """Get the currently selected category."""
        if self.highlighted_child is None:
            return None
        if isinstance(self.highlighted_child, ManageCategoryListItem):
            return self.highlighted_child.category
        return None  # pragma: no cover - defensive

    def _refresh_list(self) -> None:
        """Refresh the list with categories."""
        self.clear()
        for category, depth in self._tree:
            is_visible = category.is_visible
            if category.id in self._visibility_changes:
                is_visible = self._visibility_changes[category.id]
            self.append(
                ManageCategoryListItem(
                    category, depth, is_visible,
                    id=f'mcat-{uuid.uuid4().hex}'
                )
            )


class ManageCategoryListItem(ListItem):
    """List item for a category with visibility checkbox."""

    DEFAULT_CSS = """
    ManageCategoryListItem {
        height: 1;
        padding: 0;
    }

    ManageCategoryListItem Horizontal {
        height: 1;
    }

    ManageCategoryListItem Checkbox {
        min-width: 0;
        width: auto;
        padding: 0;
        border: none;
        background: transparent;
    }

    ManageCategoryListItem Label {
        padding: 0;
    }
    """

    def __init__(
        self, category: Category, depth: int = 0, is_visible: bool = True, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.category = category
        self.depth = depth
        self.is_visible = is_visible

    def compose(self) -> ComposeResult:
        """Create list item content with checkbox."""
        indent = '  ' * self.depth
        with Horizontal():
            yield Label(indent)
            checkbox = Checkbox('', value=self.is_visible, id='checkbox')
            checkbox.category_id = self.category.id
            yield checkbox
            yield Label(f' {self.category.name}', id='name-label')

    def toggle(self) -> None:
        """Toggle visibility state."""
        self.set_visible(not self.is_visible)

    def set_visible(self, visible: bool) -> None:
        """Set the visibility state."""
        self.is_visible = visible
        checkbox = self.query_one('#checkbox', Checkbox)
        checkbox.value = visible


def build_category_tree(categories: list[Category]) -> list[tuple[Category, int]]:
    """Build a sorted tree structure from flat category list.

    Returns list of (category, depth) tuples in tree order.
    Parent_id contains QBO IDs (strings), so we group by that and look up by qbo_id.
    """
    by_parent: dict[str | None, list[Category]] = {}
    for cat in categories:
        parent_key = str(cat.parent_id) if cat.parent_id is not None else None
        if parent_key not in by_parent:
            by_parent[parent_key] = []
        by_parent[parent_key].append(cat)

    for children in by_parent.values():
        children.sort(key=lambda c: c.name.lower())

    result: list[tuple[Category, int]] = []

    def add_children(parent_qbo_id: str | None, depth: int) -> None:
        children = by_parent.get(parent_qbo_id, [])
        for child in children:
            result.append((child, depth))
            add_children(child.qbo_id, depth + 1)

    add_children(None, 0)
    return result


class CategoryListItem(ListItem):
    """List item for a category."""

    def __init__(self, category: Category, depth: int = 0, **kwargs) -> None:
        super().__init__(**kwargs)
        self.category = category
        self.depth = depth

    def compose(self) -> ComposeResult:
        """Create list item content."""
        indent = '  ' * self.depth
        yield Label(f'{indent}{self.category.name}')


class CategoryList(ListView):
    """Filterable list of categories."""

    BINDINGS = [
        ('j', 'cursor_down', 'Down'),
        ('k', 'cursor_up', 'Up'),
    ]

    def __init__(self, categories: list[Category], **kwargs) -> None:
        super().__init__(**kwargs)
        self._all_categories = categories
        self._tree = build_category_tree(categories)
        self._filtered_tree: list[tuple[Category, int]] = self._tree.copy()

    def on_mount(self) -> None:
        """Populate list on mount."""
        self._refresh_list()

    def filter(self, query: str) -> None:
        """Filter categories by query string."""
        query = query.lower().strip()
        if not query:
            self._filtered_tree = self._tree.copy()
        else:
            self._filtered_tree = [
                (c, d)
                for c, d in self._tree
                if query in c.full_name.lower() or query in c.name.lower()
            ]
        self._refresh_list()

    def get_selected_category(self) -> Category | None:
        """Get the currently selected category."""
        if self.highlighted_child is None:
            return None
        if isinstance(self.highlighted_child, CategoryListItem):
            return self.highlighted_child.category
        return None  # pragma: no cover - defensive, ListView only contains CategoryListItems

    def _refresh_list(self) -> None:
        """Refresh the list with filtered categories."""
        self.clear()
        for category, depth in self._filtered_tree:
            self.append(
                CategoryListItem(
                    category, depth, id=f'cat-{uuid.uuid4().hex}'
                )
            )


class CategorySelectScreen(ModalScreen[int | None]):
    """Modal screen for selecting a category."""

    DEFAULT_CSS = """
    CategorySelectScreen {
        align: center middle;
    }

    #category-dialog {
        width: 60;
        height: 30;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #category-dialog #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #category-dialog #search {
        margin-bottom: 1;
    }

    #category-dialog #category-list {
        height: 1fr;
        border: solid $secondary;
    }

    #category-dialog #hint {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("enter", "select", "Select", show=True, priority=True),
        Binding("up", "cursor_up", "Up", show=False, priority=True),
        Binding("down", "cursor_down", "Down", show=False, priority=True),
        Binding("j", "cursor_down", "Down", show=False, priority=True),
        Binding("k", "cursor_up", "Up", show=False, priority=True),
    ]

    def __init__(
        self, transaction: Transaction, categories: list[Category] | None = None, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._transaction = transaction
        self._categories = categories if categories else self._get_sample_categories()

    def compose(self) -> ComposeResult:
        """Create dialog layout."""
        with Container(id="category-dialog"):
            yield Static(
                f"Select category for:\n[dim]{self._transaction.description[:50]}[/dim]", id="title"
            )
            yield Input(placeholder="Type to filter...", id="search")
            yield CategoryList(self._categories, id="category-list")
            yield Static("↑↓/jk: Navigate | Enter: Select | Esc: Cancel", id="hint")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        category_list = self.query_one("#category-list", CategoryList)
        category_list.filter(event.value)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle category selection from list."""
        self.action_select()

    def action_cancel(self) -> None:
        """Cancel category selection."""
        self.dismiss(None)

    def action_cursor_up(self) -> None:
        """Move cursor up in the category list."""
        category_list = self.query_one("#category-list", CategoryList)
        category_list.action_cursor_up()

    def action_cursor_down(self) -> None:
        """Move cursor down in the category list."""
        category_list = self.query_one("#category-list", CategoryList)
        category_list.action_cursor_down()

    def action_select(self) -> None:
        """Confirm category selection."""
        category_list = self.query_one("#category-list", CategoryList)
        category = category_list.get_selected_category()
        if category:
            self.dismiss(category.id)
        else:
            self.notify("No category selected", severity="warning")

    def _get_sample_categories(self) -> list[Category]:
        """Get sample categories for development."""
        return [
            Category(
                id=1,
                qbo_id="1",
                name="Advertising",
                full_name="Expenses:Advertising",
                parent_id=None,
                account_type="Expense",
            ),
            Category(
                id=2,
                qbo_id="2",
                name="Office Supplies",
                full_name="Expenses:Office Supplies",
                parent_id=None,
                account_type="Expense",
            ),
            Category(
                id=3,
                qbo_id="3",
                name="Travel",
                full_name="Expenses:Travel",
                parent_id=None,
                account_type="Expense",
            ),
            Category(
                id=4,
                qbo_id="4",
                name="Meals",
                full_name="Expenses:Meals & Entertainment",
                parent_id=None,
                account_type="Expense",
            ),
            Category(
                id=5,
                qbo_id="5",
                name="Software",
                full_name="Expenses:Software & Subscriptions",
                parent_id=None,
                account_type="Expense",
            ),
            Category(
                id=6,
                qbo_id="6",
                name="Professional Services",
                full_name="Expenses:Professional Services",
                parent_id=None,
                account_type="Expense",
            ),
            Category(
                id=7,
                qbo_id="7",
                name="Utilities",
                full_name="Expenses:Utilities",
                parent_id=None,
                account_type="Expense",
            ),
            Category(
                id=8,
                qbo_id="8",
                name="Insurance",
                full_name="Expenses:Insurance",
                parent_id=None,
                account_type="Expense",
            ),
        ]
