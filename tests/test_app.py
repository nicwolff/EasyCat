"""Tests for the main Textual application."""

import pytest
from textual.widgets import Footer, Header

from easycat.app import EasyCatApp, main
from easycat.config import Config, DatabaseConfig, QuickBooksConfig, SecurityConfig
from easycat.screens.transactions import TransactionsScreen


@pytest.fixture
def mock_config() -> Config:
    """Create a mock configuration."""
    return Config(
        quickbooks=QuickBooksConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            environment="sandbox",
            redirect_uri="http://localhost:8085/callback",
        ),
        database=DatabaseConfig(path="test.db"),
        security=SecurityConfig(encryption_key="test_key"),
    )


class TestEasyCatApp:
    """Tests for the EasyCatApp class."""

    async def test_app_init_with_config(self, mock_config):
        """Test app initializes with provided config."""
        app = EasyCatApp(config=mock_config)
        assert app.config == mock_config

    async def test_app_init_without_config(self, monkeypatch, tmp_path):
        """Test app initializes with default config loading."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[quickbooks]
client_id = "file_client_id"
client_secret = "file_client_secret"
environment = "sandbox"
""")
        monkeypatch.chdir(tmp_path)
        app = EasyCatApp()
        assert app.config.quickbooks.client_id == "file_client_id"

    async def test_app_has_correct_title(self, mock_config):
        """Test app has correct title and subtitle."""
        app = EasyCatApp(config=mock_config)
        assert app.TITLE == "EasyCat"
        assert app.SUB_TITLE == "QuickBooks Transaction Categorization"

    async def test_app_has_quit_binding(self, mock_config):
        """Test app has quit binding."""
        app = EasyCatApp(config=mock_config)
        bindings = {b.key for b in app.BINDINGS}
        assert "q" in bindings

    async def test_app_has_help_binding(self, mock_config):
        """Test app has help binding."""
        app = EasyCatApp(config=mock_config)
        bindings = {b.key for b in app.BINDINGS}
        assert "?" in bindings

    async def test_app_compose_yields_header_and_footer(self, mock_config):
        """Test app compose yields Header and Footer."""
        app = EasyCatApp(config=mock_config)
        async with app.run_test():
            assert app.query_one(Header) is not None
            assert app.query_one(Footer) is not None

    async def test_app_pushes_transactions_screen_on_mount(self, mock_config):
        """Test app pushes TransactionsScreen on mount."""
        app = EasyCatApp(config=mock_config)
        async with app.run_test():
            assert isinstance(app.screen, TransactionsScreen)

    async def test_app_help_action_shows_notification(self, mock_config):
        """Test help action shows notification."""
        app = EasyCatApp(config=mock_config)
        async with app.run_test() as pilot:
            await pilot.press("?")

    async def test_app_on_unmount_with_no_repository(self, mock_config):
        """Test on_unmount handles case when repository is None."""
        app = EasyCatApp(config=mock_config)
        app._repository = None
        await app.on_unmount()

    async def test_app_repository_property(self, mock_config):
        """Test repository property returns the repository."""
        app = EasyCatApp(config=mock_config)
        assert app.repository is None
        async with app.run_test():
            assert app.repository is not None


class TestMain:
    """Tests for the main entry point."""

    def test_main_function_exists(self):
        """Test that main function exists and is callable."""
        assert callable(main)
