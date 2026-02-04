# Active Context

## Current Phase
Phase 3: Feature Complete

## Recently Completed
- Manage Categories screen enhancements:
  - Removed "n: None" option
  - Changed "a" to toggle all categories (instead of show all)
  - Added "n: Add category" to create new expense categories in QuickBooks
  - Added "s: Add subcategory" to create subcategories in QuickBooks
- Added `create_account` API method to QuickBooksClient
- Added TextInputScreen modal for text input
- 100% test coverage maintained

## Active Features
- OAuth authentication with QuickBooks Online
- Transaction sync from QuickBooks
- Category sync from QuickBooks Chart of Accounts
- Keyboard-driven transaction categorization
- Category visibility management
- Add new categories/subcategories (created in QuickBooks immediately)
- Post categorized transactions back to QuickBooks
- Rules engine for auto-categorization

## Technical Notes
- Widget IDs use UUID to avoid Textual's async clear() timing issues
- Categories list is shared between TransactionsScreen and ManageCategoriesScreen
- Category creation callback pattern: callback appends to shared list, screen refreshes display
