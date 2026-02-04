# EasyCat

A terminal-based QuickBooks transaction categorization tool built with Textual.

## Features

### Authentication & Sync
- OAuth authentication with QuickBooks Online (sandbox and production)
- Sync expense categories from QuickBooks Chart of Accounts
- Fetch uncategorized transactions from connected bank/credit card accounts
- Push categorized transactions back to QuickBooks

### Transaction Management
- Keyboard-driven TUI for fast categorization
- Filter transactions by account
- Navigate with arrow keys or vim-style j/k bindings

### Category Management
- **Manage Categories** (press `m`):
  - Toggle individual category visibility with spacebar
  - Toggle all categories visible/hidden with `a`
  - Add new expense category with `n` (created in QuickBooks immediately)
  - Add subcategory of selected category with `s` (created in QuickBooks immediately)
- **Select Category** (press `c` or Enter on transaction):
  - Filter categories by typing
  - Only visible categories are shown

### Rules Engine
- Pattern-based auto-categorization (contains, regex, exact match)
- Amount range matching
- Priority-based rule ordering
- Vendor-to-category default mappings

## Installation

```bash
uv sync
```

## Configuration

Copy `config.example.toml` to `config.toml` and fill in your QuickBooks API credentials:

```toml
[quickbooks]
client_id = "your-client-id"
client_secret = "your-client-secret"
redirect_uri = "http://localhost:8080/callback"
environment = "sandbox"  # or "production"

[database]
path = "easycat.db"

[security]
encryption_key = ""  # optional, for token encryption
```

## Usage

```bash
uv run easycat
```

### Key Bindings

| Key | Action |
|-----|--------|
| `l` | Log in to QuickBooks |
| `r` | Refresh transactions from QuickBooks |
| `a` | Select account to filter |
| `c` / `Enter` | Categorize selected transaction |
| `m` | Manage category visibility |
| `p` | Post categorized transactions to QuickBooks |
| `j` / `Down` | Move down |
| `k` / `Up` | Move up |
| `q` | Quit |

## Development

Run tests:
```bash
uv run pytest
```

Run linter:
```bash
uv run ruff check .
```

## Architecture

- `easycat/auth/` - OAuth flow and token management
- `easycat/api/` - QuickBooks API client
- `easycat/db/` - SQLite models and repository
- `easycat/rules/` - Categorization rules engine
- `easycat/screens/` - Textual screens (transactions, categories)
- `easycat/widgets/` - Reusable Textual widgets
