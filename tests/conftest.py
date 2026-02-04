"""Shared test fixtures."""

import tempfile
from pathlib import Path

import pytest

from easycat.config import (
    Config,
    DatabaseConfig,
    QuickBooksConfig,
    SecurityConfig,
)
from easycat.db.repository import Repository


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db_path(temp_dir):
    """Create a temporary database path."""
    return temp_dir / "test.db"


@pytest.fixture
def quickbooks_config():
    """Create a test QuickBooks config."""
    return QuickBooksConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        environment="sandbox",
        redirect_uri="http://localhost:8085/callback",
    )


@pytest.fixture
def database_config(temp_db_path):
    """Create a test database config."""
    return DatabaseConfig(path=temp_db_path)


@pytest.fixture
def security_config():
    """Create a test security config without encryption."""
    return SecurityConfig(encryption_key=None)


@pytest.fixture
def security_config_with_encryption():
    """Create a test security config with encryption."""
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    return SecurityConfig(encryption_key=key)


@pytest.fixture
def config(quickbooks_config, database_config, security_config):
    """Create a test config."""
    return Config(
        quickbooks=quickbooks_config,
        database=database_config,
        security=security_config,
    )


@pytest.fixture
async def repository(temp_db_path):
    """Create a repository with a temporary database."""
    repo = Repository(temp_db_path)
    await repo.connect()
    yield repo
    await repo.close()
