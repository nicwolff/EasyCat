"""Synchronization service for QuickBooks Online data."""

from datetime import datetime

from easycat.api import QBOTransaction, QuickBooksClient
from easycat.db.models import Category, Transaction, TransactionStatus
from easycat.db.repository import Repository


async def sync_categories(client: QuickBooksClient, repo: Repository) -> list[Category]:
    """Fetch categories from QBO and save to database."""
    qbo_accounts = await client.get_all_categorization_accounts()
    categories = []
    for account in qbo_accounts:
        category = Category(
            id=None,
            qbo_id=account.id,
            name=account.name,
            full_name=account.full_name,
            parent_id=account.parent_id,
            account_type=account.account_type,
            is_visible=True,
            display_order=0,
            synced_at=datetime.now(),
        )
        saved = await repo.save_category(category)
        categories.append(saved)
    return categories


async def sync_transactions(
    client: QuickBooksClient,
    repo: Repository,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[Transaction]:
    """Fetch transactions from QBO and save to database.

    New transactions are created with PENDING status but with category
    pre-populated from QuickBooks. Existing transactions preserve their
    current status (the upsert doesn't overwrite status).
    """
    import logging
    log = logging.getLogger('easycat.sync')

    qbo_txns = await client.get_uncategorized_transactions(start_date, end_date)
    log.info(f'Received {len(qbo_txns)} transactions from QuickBooks')
    for qbo_txn in qbo_txns:
        log.debug(f'QBO Transaction: {qbo_txn}')

    categories = await repo.get_all_categories()
    qbo_id_to_category = {c.qbo_id: c for c in categories}
    transactions = []
    for qbo_txn in qbo_txns:
        txn = _qbo_transaction_to_model(qbo_txn, qbo_id_to_category)
        saved = await repo.save_transaction(txn)
        transactions.append(saved)
    return transactions


async def post_categorized_transactions(
    client: QuickBooksClient,
    repo: Repository,
) -> list[Transaction]:
    """Post categorized transactions back to QuickBooks."""
    import logging
    log = logging.getLogger('easycat.sync')

    categorized = await repo.get_transactions_by_status(TransactionStatus.CATEGORIZED)
    log.info(f'Found {len(categorized)} categorized transactions to post')
    posted = []
    for txn in categorized:
        if txn.assigned_category_id is None:
            log.warning(f'Skipping txn {txn.qbo_id}: no category_id')
            continue
        category = await repo.get_category_by_id(txn.assigned_category_id)
        if category is None:
            log.warning(f'Skipping txn {txn.qbo_id}: category {txn.assigned_category_id} not found')
            continue
        try:
            log.info(f'Posting txn {txn.qbo_id} with category {category.name} ({category.qbo_id})')
            purchase = await client.get_purchase_raw(txn.qbo_id)
            log.debug(f'Got purchase: {purchase}')
            line_items = _build_categorized_line_items(purchase, category)
            log.debug(f'Built line_items: {line_items}')
            await client.update_purchase(purchase, line_items)
            await repo.update_transaction_status(
                txn.id, TransactionStatus.POSTED, txn.assigned_category_id
            )
            txn.status = TransactionStatus.POSTED
            posted.append(txn)
            log.info(f'Successfully posted txn {txn.qbo_id}')
        except Exception as e:
            log.error(f'Failed to post txn {txn.qbo_id}: {e}')
            continue
    return posted


def _qbo_transaction_to_model(
    qbo_txn: QBOTransaction, qbo_id_to_category: dict[str, Category]
) -> Transaction:
    """Convert QBO transaction to database model.

    Pre-populates category from QuickBooks but always sets PENDING status.
    The database upsert preserves existing status for transactions we've
    already processed.
    """
    description = qbo_txn.memo or ''
    if qbo_txn.line_items:
        line_desc = qbo_txn.line_items[0].description
        if line_desc:
            description = line_desc
    if not description:
        description = f'Purchase {qbo_txn.doc_number or qbo_txn.id}'

    assigned_category_id = None
    if qbo_txn.line_items:
        line_account_id = qbo_txn.line_items[0].account_id
        if line_account_id and line_account_id in qbo_id_to_category:
            category = qbo_id_to_category[line_account_id]
            assigned_category_id = category.id

    return Transaction(
        id=None,
        qbo_id=qbo_txn.id,
        account_id=qbo_txn.account_id,
        account_name=qbo_txn.account_name,
        date=qbo_txn.txn_date,
        amount=-qbo_txn.total_amount,
        description=description,
        vendor_name=qbo_txn.entity_name,
        status=TransactionStatus.PENDING,
        assigned_category_id=assigned_category_id,
        fetched_at=datetime.now(),
    )


def _build_categorized_line_items(purchase: dict, category: Category) -> list[dict]:
    """Build line items with new category for QBO update."""
    import copy
    lines = purchase.get('Line', [])
    updated_lines = []
    for line in lines:
        if line.get('DetailType') == 'AccountBasedExpenseLineDetail':
            updated_line = copy.deepcopy(line)
            updated_line['AccountBasedExpenseLineDetail']['AccountRef'] = {
                'value': category.qbo_id,
                'name': category.full_name,
            }
            updated_lines.append(updated_line)
        else:
            updated_lines.append(copy.deepcopy(line))
    return updated_lines
