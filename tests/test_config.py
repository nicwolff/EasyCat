"""Tests for configuration loading."""

from pathlib import Path

from easycat.config import (
    DEFAULT_DB_PATH,
    DEFAULT_REDIRECT_URI,
    QuickBooksConfig,
    find_config_file,
    load_config,
)


class TestQuickBooksConfig:
    """Tests for QuickBooksConfig."""

    def test_is_sandbox_true(self):
        """Test is_sandbox returns True for sandbox environment."""
        config = QuickBooksConfig(
            client_id="id",
            client_secret="secret",
            environment="sandbox",
            redirect_uri="http://localhost:8085/callback",
        )
        assert config.is_sandbox is True

    def test_is_sandbox_false(self):
        """Test is_sandbox returns False for production environment."""
        config = QuickBooksConfig(
            client_id="id",
            client_secret="secret",
            environment="production",
            redirect_uri="http://localhost:8085/callback",
        )
        assert config.is_sandbox is False


class TestFindConfigFile:
    """Tests for find_config_file function."""

    def test_finds_existing_config(self, temp_dir, monkeypatch):
        """Test finding an existing config file."""
        config_path = temp_dir / "config.toml"
        config_path.write_text('[quickbooks]\nclient_id = "test"')
        monkeypatch.setattr("easycat.config.DEFAULT_CONFIG_PATHS", [config_path])
        result = find_config_file()
        assert result == config_path

    def test_returns_none_when_no_config(self, temp_dir, monkeypatch):
        """Test returning None when no config file exists."""
        nonexistent = temp_dir / "nonexistent.toml"
        monkeypatch.setattr("easycat.config.DEFAULT_CONFIG_PATHS", [nonexistent])
        result = find_config_file()
        assert result is None


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_from_toml_file(self, temp_dir):
        """Test loading config from a TOML file."""
        config_path = temp_dir / "config.toml"
        config_path.write_text("""
[quickbooks]
client_id = 'toml-client-id'
client_secret = 'toml-client-secret'
environment = 'production'
redirect_uri = 'http://localhost:9000/callback'

[database]
path = 'custom.db'

[security]
encryption_key = 'test-key'
""")
        config = load_config(config_path)
        assert config.quickbooks.client_id == "toml-client-id"
        assert config.quickbooks.client_secret == "toml-client-secret"
        assert config.quickbooks.environment == "production"
        assert config.quickbooks.redirect_uri == "http://localhost:9000/callback"
        assert config.database.path == temp_dir / "custom.db"
        assert config.security.encryption_key == "test-key"

    def test_load_with_env_vars(self, temp_dir, monkeypatch):
        """Test environment variables override TOML values."""
        config_path = temp_dir / "config.toml"
        config_path.write_text("""
[quickbooks]
client_id = 'toml-id'
client_secret = 'toml-secret'
""")
        monkeypatch.setenv("EASYCAT_CLIENT_ID", "env-client-id")
        monkeypatch.setenv("EASYCAT_CLIENT_SECRET", "env-client-secret")
        monkeypatch.setenv("EASYCAT_ENVIRONMENT", "production")
        monkeypatch.setenv("EASYCAT_REDIRECT_URI", "http://localhost:9999/cb")
        config = load_config(config_path)
        assert config.quickbooks.client_id == "env-client-id"
        assert config.quickbooks.client_secret == "env-client-secret"
        assert config.quickbooks.environment == "production"
        assert config.quickbooks.redirect_uri == "http://localhost:9999/cb"

    def test_load_with_defaults(self, temp_dir, monkeypatch):
        """Test loading config with default values."""
        config_path = temp_dir / "config.toml"
        config_path.write_text("""
[quickbooks]
client_id = 'id'
client_secret = 'secret'
""")
        for var in [
            "EASYCAT_CLIENT_ID",
            "EASYCAT_CLIENT_SECRET",
            "EASYCAT_ENVIRONMENT",
            "EASYCAT_REDIRECT_URI",
            "EASYCAT_DB_PATH",
            "EASYCAT_ENCRYPTION_KEY",
        ]:
            monkeypatch.delenv(var, raising=False)
        config = load_config(config_path)
        assert config.quickbooks.environment == "sandbox"
        assert config.quickbooks.redirect_uri == DEFAULT_REDIRECT_URI
        assert config.database.path == temp_dir / DEFAULT_DB_PATH
        assert config.security.encryption_key is None

    def test_load_without_config_file(self, temp_dir, monkeypatch):
        """Test loading config when no file exists."""
        monkeypatch.setattr("easycat.config.DEFAULT_CONFIG_PATHS", [])
        for var in [
            "EASYCAT_CLIENT_ID",
            "EASYCAT_CLIENT_SECRET",
            "EASYCAT_ENVIRONMENT",
            "EASYCAT_REDIRECT_URI",
            "EASYCAT_DB_PATH",
            "EASYCAT_ENCRYPTION_KEY",
        ]:
            monkeypatch.delenv(var, raising=False)
        config = load_config(None)
        assert config.quickbooks.client_id == ""
        assert config.quickbooks.client_secret == ""
        assert config.quickbooks.environment == "sandbox"

    def test_db_path_env_var(self, temp_dir, monkeypatch):
        """Test database path from environment variable."""
        config_path = temp_dir / "config.toml"
        config_path.write_text('[quickbooks]\nclient_id = "id"\nclient_secret = "secret"')
        monkeypatch.setenv("EASYCAT_DB_PATH", "/custom/path/db.sqlite")
        config = load_config(config_path)
        assert config.database.path == Path("/custom/path/db.sqlite")

    def test_encryption_key_env_var(self, temp_dir, monkeypatch):
        """Test encryption key from environment variable."""
        config_path = temp_dir / "config.toml"
        config_path.write_text('[quickbooks]\nclient_id = "id"\nclient_secret = "secret"')
        monkeypatch.setenv("EASYCAT_ENCRYPTION_KEY", "env-encryption-key")
        config = load_config(config_path)
        assert config.security.encryption_key == "env-encryption-key"

    def test_empty_encryption_key_becomes_none(self, temp_dir, monkeypatch):
        """Test that empty encryption key is treated as None."""
        config_path = temp_dir / "config.toml"
        config_path.write_text("""
[quickbooks]
client_id = 'id'
client_secret = 'secret'

[security]
encryption_key = ''
""")
        for var in ["EASYCAT_ENCRYPTION_KEY"]:
            monkeypatch.delenv(var, raising=False)
        config = load_config(config_path)
        assert config.security.encryption_key is None

    def test_absolute_db_path(self, temp_dir):
        """Test absolute database path is not modified."""
        config_path = temp_dir / "config.toml"
        config_path.write_text("""
[quickbooks]
client_id = 'id'
client_secret = 'secret'

[database]
path = '/absolute/path/db.sqlite'
""")
        config = load_config(config_path)
        assert config.database.path == Path("/absolute/path/db.sqlite")
