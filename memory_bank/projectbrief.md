# EasyCat Project Brief

## Overview
EasyCat is a TUI (Text User Interface) application built with Textual that helps QuickBooks Online users categorize and post pending bank and credit card transactions.

## Core Requirements
- Python 3.11+
- Textual for TUI framework
- httpx for async HTTP requests
- SQLite for local storage
- TOML configuration with environment variable fallbacks

## Implemented Features

### Authentication
- Browser-based OAuth flow with QuickBooks Online
- Secure token storage with optional encryption
- Automatic token refresh
- Sandbox and production environment support

### Transaction Management
- Fetch uncategorized transactions from QBO
- Filter by bank/credit card account
- Keyboard-driven categorization workflow
- Post categorized transactions back to QBO

### Category Management
- Sync Chart of Accounts from QBO
- Toggle category visibility (show/hide in selection list)
- Add new expense categories (created in QBO immediately)
- Add subcategories under existing categories
- Hierarchical category display with indentation

### Rules Engine
- Pattern-based auto-categorization:
  - Contains (case-insensitive substring match)
  - Regex (regular expression)
  - Exact (exact string match)
- Amount range filtering (min/max)
- Priority-based rule ordering
- Vendor-to-category default mappings

### User Interface
- TransactionsScreen: Main transaction list with details panel
- CategorySelectScreen: Filterable category picker
- ManageCategoriesScreen: Visibility toggles and category creation
- TextInputScreen: Modal text input dialog
- Vim-style navigation (j/k) alongside arrow keys

## Technical Constraints
- 100% test coverage required
- 100-character max line length
- No trailing whitespace
- Single quotes for strings
- snake_case naming (ALL_CAPS for module globals)
- Top-down call order in modules

## Architecture
```
easycat/
├── auth/           # OAuth flow and token management
├── api/            # QuickBooks API client and sync
├── db/             # SQLite models, migrations, repository
├── rules/          # Categorization rules engine
├── screens/        # Textual screens
│   ├── categories.py   # Category selection and management
│   └── transactions.py # Main transaction screen
├── widgets/        # Reusable Textual widgets
├── app.py          # Main application
└── config.py       # Configuration loading
```

## Key Technical Decisions
- Async/await throughout for non-blocking I/O
- Repository pattern for database access
- Modal screens for dialogs (category selection, input)
- UUID-based widget IDs to avoid Textual timing issues
- Shared category list between screens (pass by reference)
- Callback pattern for category creation (callback modifies list, screen refreshes)
