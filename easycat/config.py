"""Configuration loading from TOML files with environment variable fallbacks."""

import os
from dataclasses import dataclass
from pathlib import Path

import tomli

DEFAULT_CONFIG_PATHS = [
    Path("config.toml"),
    Path.home() / ".config" / "easycat" / "config.toml",
]

DEFAULT_REDIRECT_URI = "http://localhost:8085/callback"
DEFAULT_DB_PATH = "easycat.db"


@dataclass(frozen=True)
class QuickBooksConfig:
    """QuickBooks API configuration."""

    client_id: str
    client_secret: str
    environment: str
    redirect_uri: str

    @property
    def is_sandbox(self) -> bool:
        """Check if using sandbox environment."""
        return self.environment == "sandbox"


@dataclass(frozen=True)
class DatabaseConfig:
    """Database configuration."""

    path: Path


@dataclass(frozen=True)
class SecurityConfig:
    """Security configuration."""

    encryption_key: str | None


@dataclass(frozen=True)
class Config:
    """Application configuration."""

    quickbooks: QuickBooksConfig
    database: DatabaseConfig
    security: SecurityConfig


def find_config_file() -> Path | None:
    """Find the first existing config file from default paths."""
    for path in DEFAULT_CONFIG_PATHS:
        if path.exists():
            return path
    return None


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from TOML file with environment variable fallbacks."""
    toml_data = _load_toml_data(config_path)
    return _build_config(toml_data, config_path)


def _load_toml_data(config_path: Path | None) -> dict:
    """Load TOML data from file if it exists."""
    path = config_path or find_config_file()
    if path and path.exists():
        with open(path, "rb") as f:
            return tomli.load(f)
    return {}


def _build_config(toml_data: dict, config_path: Path | None) -> Config:
    """Build Config object from TOML data and environment variables."""
    qb_config = _build_quickbooks_config(toml_data.get("quickbooks", {}))
    db_config = _build_database_config(toml_data.get("database", {}), config_path)
    security_config = _build_security_config(toml_data.get("security", {}))
    return Config(quickbooks=qb_config, database=db_config, security=security_config)


def _build_quickbooks_config(qb_data: dict) -> QuickBooksConfig:
    """Build QuickBooks config from TOML data and env vars."""
    client_id = os.environ.get("EASYCAT_CLIENT_ID", qb_data.get("client_id", ""))
    client_secret = os.environ.get("EASYCAT_CLIENT_SECRET", qb_data.get("client_secret", ""))
    environment = os.environ.get("EASYCAT_ENVIRONMENT", qb_data.get("environment", "sandbox"))
    redirect_uri = os.environ.get(
        "EASYCAT_REDIRECT_URI", qb_data.get("redirect_uri", DEFAULT_REDIRECT_URI)
    )
    return QuickBooksConfig(
        client_id=client_id,
        client_secret=client_secret,
        environment=environment,
        redirect_uri=redirect_uri,
    )


def _build_database_config(db_data: dict, config_path: Path | None) -> DatabaseConfig:
    """Build database config, resolving relative paths against config file location."""
    db_path_str = os.environ.get("EASYCAT_DB_PATH", db_data.get("path", DEFAULT_DB_PATH))
    db_path = Path(db_path_str)
    if not db_path.is_absolute() and config_path:
        db_path = config_path.parent / db_path
    return DatabaseConfig(path=db_path)


def _build_security_config(security_data: dict) -> SecurityConfig:
    """Build security config from TOML data and env vars."""
    encryption_key = os.environ.get(
        "EASYCAT_ENCRYPTION_KEY", security_data.get("encryption_key") or None
    )
    return SecurityConfig(encryption_key=encryption_key)
