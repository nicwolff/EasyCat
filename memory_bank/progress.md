# Progress Tracker

## Completed
- [x] Project planning and requirements gathering
- [x] Directory structure created
- [x] pyproject.toml configured
- [x] Config module with TOML and env var support
- [x] Database models and migrations
- [x] SQLite repository with async operations
- [x] OAuth authentication (browser-based flow)
- [x] Token encryption and secure storage
- [x] QuickBooks API client
  - [x] Fetch expense/income accounts
  - [x] Fetch uncategorized transactions
  - [x] Update purchase transactions
  - [x] Create new accounts (categories)
- [x] Sync module (categories, transactions, post back)
- [x] TUI screens
  - [x] TransactionsScreen (main screen)
  - [x] CategorySelectScreen (filterable category picker)
  - [x] ManageCategoriesScreen (visibility, add category/subcategory)
  - [x] TextInputScreen (modal text input)
  - [x] ConfirmBatchScreen (batch categorization confirmation)
- [x] TransactionTable widget
- [x] Rules engine (pattern matching, amount ranges, priorities)
- [x] Account filtering
- [x] Tests with 100% coverage

## Key Bindings Implemented
- `l` - Login to QuickBooks
- `r` - Refresh from QuickBooks
- `a` - Select account filter
- `c` / `Enter` - Categorize transaction
- `m` - Manage categories
- `p` - Post to QuickBooks
- `j/k` - Vim-style navigation
- `q` - Quit

## Manage Categories Screen
- `Space` - Toggle selected category visibility
- `a` - Toggle all categories
- `n` - Add new category
- `s` - Add subcategory of selected
- `Enter` - Save changes
- `Escape` - Cancel
