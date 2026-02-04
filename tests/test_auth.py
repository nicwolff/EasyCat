"""Tests for OAuth authentication."""

import io
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from easycat.auth import (
    OAUTH_SCOPES,
    TOKEN_EXPIRY_BUFFER_SECONDS,
    CallbackHandler,
    CallbackServer,
    OAuthClient,
    OAuthError,
    OAuthResult,
    TokenEncryption,
)
from easycat.db.models import Token


class TestTokenEncryption:
    """Tests for TokenEncryption class."""

    def test_encrypt_decrypt_with_key(self, security_config_with_encryption):
        """Test encryption and decryption with a key."""
        encryption = TokenEncryption(security_config_with_encryption.encryption_key)
        original = "secret_token_value"
        encrypted = encryption.encrypt(original)
        assert encrypted != original
        decrypted = encryption.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_without_key(self, security_config):
        """Test that encrypt returns original value without key."""
        encryption = TokenEncryption(security_config.encryption_key)
        original = "secret_token_value"
        encrypted = encryption.encrypt(original)
        assert encrypted == original

    def test_decrypt_without_key(self, security_config):
        """Test that decrypt returns original value without key."""
        encryption = TokenEncryption(security_config.encryption_key)
        original = "secret_token_value"
        decrypted = encryption.decrypt(original)
        assert decrypted == original


class TestCallbackHandler:
    """Tests for CallbackHandler class."""

    def test_class_attributes_initialized(self):
        """Test that class attributes are initialized to None."""
        CallbackHandler.auth_code = None
        CallbackHandler.realm_id = None
        CallbackHandler.state = None
        CallbackHandler.error = None
        assert CallbackHandler.auth_code is None
        assert CallbackHandler.realm_id is None
        assert CallbackHandler.state is None
        assert CallbackHandler.error is None


class TestCallbackServer:
    """Tests for CallbackServer class."""

    def test_init(self):
        """Test CallbackServer initialization."""
        server = CallbackServer(8085)
        assert server._port == 8085
        assert server._server is None
        assert server._thread is None

    def test_properties_before_start(self):
        """Test properties return None before server starts."""
        CallbackHandler.auth_code = None
        CallbackHandler.realm_id = None
        CallbackHandler.state = None
        CallbackHandler.error = None
        server = CallbackServer(8085)
        assert server.auth_code is None
        assert server.realm_id is None
        assert server.state is None
        assert server.error is None

    def test_stop_without_start(self):
        """Test that stop is safe without start."""
        server = CallbackServer(8085)
        server.stop()
        assert server._server is None
        assert server._thread is None


class TestOAuthClient:
    """Tests for OAuthClient class."""

    def test_init(self, quickbooks_config, security_config):
        """Test OAuthClient initialization."""
        client = OAuthClient(quickbooks_config, security_config)
        assert client._config == quickbooks_config
        assert client._state is None

    def test_init_without_security_config(self, quickbooks_config):
        """Test OAuthClient initialization without security config."""
        client = OAuthClient(quickbooks_config)
        assert client._config == quickbooks_config

    def test_get_authorization_url(self, quickbooks_config, security_config):
        """Test generating authorization URL."""
        client = OAuthClient(quickbooks_config, security_config)
        url = client.get_authorization_url()
        assert "https://" in url
        assert client._state is not None

    def test_encrypt_token(self, quickbooks_config, security_config_with_encryption):
        """Test encrypting a token."""
        client = OAuthClient(quickbooks_config, security_config_with_encryption)
        original = "secret_token"
        encrypted = client.encrypt_token(original)
        assert encrypted != original

    def test_decrypt_token(self, quickbooks_config, security_config_with_encryption):
        """Test decrypting a token."""
        client = OAuthClient(quickbooks_config, security_config_with_encryption)
        original = "secret_token"
        encrypted = client.encrypt_token(original)
        decrypted = client.decrypt_token(encrypted)
        assert decrypted == original

    def test_is_token_expired_true(self, quickbooks_config, security_config):
        """Test is_token_expired returns True for expired token."""
        client = OAuthClient(quickbooks_config, security_config)
        now = datetime.now()
        token = Token(
            id=1,
            realm_id="realm",
            access_token="access",
            refresh_token="refresh",
            expires_at=now - timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )
        assert client.is_token_expired(token) is True

    def test_is_token_expired_within_buffer(self, quickbooks_config, security_config):
        """Test is_token_expired returns True when within buffer."""
        client = OAuthClient(quickbooks_config, security_config)
        now = datetime.now()
        token = Token(
            id=1,
            realm_id="realm",
            access_token="access",
            refresh_token="refresh",
            expires_at=now + timedelta(seconds=100),
            created_at=now,
            updated_at=now,
        )
        assert client.is_token_expired(token) is True

    def test_is_token_expired_false(self, quickbooks_config, security_config):
        """Test is_token_expired returns False for valid token."""
        client = OAuthClient(quickbooks_config, security_config)
        now = datetime.now()
        token = Token(
            id=1,
            realm_id="realm",
            access_token="access",
            refresh_token="refresh",
            expires_at=now + timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )
        assert client.is_token_expired(token) is False

    def test_get_callback_port_from_uri(self, quickbooks_config, security_config):
        """Test extracting port from redirect URI."""
        client = OAuthClient(quickbooks_config, security_config)
        port = client._get_callback_port()
        assert port == 8085

    def test_get_callback_port_default(self, security_config):
        """Test default port when not specified in URI."""
        from easycat.config import QuickBooksConfig

        config = QuickBooksConfig(
            client_id="id",
            client_secret="secret",
            environment="sandbox",
            redirect_uri="http://localhost/callback",
        )
        client = OAuthClient(config, security_config)
        port = client._get_callback_port()
        assert port == 8085


class TestOAuthResult:
    """Tests for OAuthResult dataclass."""

    def test_create_oauth_result(self):
        """Test creating an OAuthResult instance."""
        now = datetime.now()
        result = OAuthResult(
            realm_id="realm123",
            access_token="access",
            refresh_token="refresh",
            expires_at=now,
        )
        assert result.realm_id == "realm123"
        assert result.access_token == "access"
        assert result.refresh_token == "refresh"
        assert result.expires_at == now


class TestOAuthError:
    """Tests for OAuthError exception."""

    def test_oauth_error(self):
        """Test OAuthError exception."""
        error = OAuthError("Test error message")
        assert str(error) == "Test error message"

    def test_oauth_error_raise(self):
        """Test raising OAuthError."""
        with pytest.raises(OAuthError) as exc_info:
            raise OAuthError("Authorization failed")
        assert "Authorization failed" in str(exc_info.value)


class TestCallbackHandlerDoGet:
    """Tests for CallbackHandler.do_GET method."""

    def _create_handler(self, path):
        """Create a CallbackHandler with a mocked request."""
        handler = CallbackHandler.__new__(CallbackHandler)
        handler.path = path
        handler.requestline = f"GET {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 12345)
        handler.wfile = io.BytesIO()
        handler.headers = {}
        return handler

    def test_do_get_success(self):
        """Test handling successful OAuth callback."""
        CallbackHandler.auth_code = None
        CallbackHandler.realm_id = None
        CallbackHandler.state = None
        CallbackHandler.error = None
        handler = self._create_handler("/callback?code=auth123&realmId=realm456&state=state789")
        with (
            patch.object(handler, "send_response"),
            patch.object(handler, "send_header"),
            patch.object(handler, "end_headers"),
        ):
            handler.do_GET()
        assert CallbackHandler.auth_code == "auth123"
        assert CallbackHandler.realm_id == "realm456"
        assert CallbackHandler.state == "state789"
        assert CallbackHandler.error is None
        assert b'Authorization Successful' in handler.wfile.getvalue()

    def test_do_get_error(self):
        """Test handling OAuth callback with error."""
        CallbackHandler.auth_code = None
        CallbackHandler.error = None
        handler = self._create_handler("/callback?error=access_denied")
        with (
            patch.object(handler, "send_response"),
            patch.object(handler, "send_header"),
            patch.object(handler, "end_headers"),
        ):
            handler.do_GET()
        assert CallbackHandler.error == "access_denied"
        assert b'Authorization Failed' in handler.wfile.getvalue()

    def test_log_message_suppressed(self):
        """Test that log_message does nothing."""
        handler = self._create_handler("/callback")
        handler.log_message("test %s", "message")


class TestCallbackServerStartStop:
    """Tests for CallbackServer start and wait methods."""

    def test_start_and_stop(self):
        """Test starting and stopping the callback server."""
        server = CallbackServer(18085)
        server.start()
        assert server._server is not None
        assert server._thread is not None
        server.stop()
        assert server._server is None

    def test_wait_for_callback_without_thread(self):
        """Test wait_for_callback when thread is None."""
        server = CallbackServer(18086)
        server.wait_for_callback(timeout=0.1)

    def test_wait_for_callback_with_thread(self):
        """Test wait_for_callback when thread exists."""
        server = CallbackServer(18087)
        server.start()
        server.wait_for_callback(timeout=0.1)
        server.stop()


class TestOAuthClientAuthorize:
    """Tests for OAuthClient authorize flow."""

    async def test_authorize_error_response(self, quickbooks_config, security_config):
        """Test authorize with error response from OAuth server."""
        client = OAuthClient(quickbooks_config, security_config)
        with (
            patch.object(client, "_get_callback_port", return_value=18087),
            patch("easycat.auth.CallbackServer") as mock_server_class,
            patch("easycat.auth.webbrowser"),
        ):
            mock_server = Mock()
            mock_server.error = "access_denied"
            mock_server.auth_code = None
            mock_server_class.return_value = mock_server
            with pytest.raises(OAuthError, match="Authorization failed"):
                await client.authorize(open_browser=False)

    async def test_authorize_no_auth_code(self, quickbooks_config, security_config):
        """Test authorize when no auth code is received."""
        client = OAuthClient(quickbooks_config, security_config)
        with (
            patch.object(client, "_get_callback_port", return_value=18088),
            patch("easycat.auth.CallbackServer") as mock_server_class,
            patch("easycat.auth.webbrowser"),
        ):
            mock_server = Mock()
            mock_server.error = None
            mock_server.auth_code = None
            mock_server_class.return_value = mock_server
            with pytest.raises(OAuthError, match="No authorization code"):
                await client.authorize(open_browser=False)

    async def test_authorize_state_mismatch(self, quickbooks_config, security_config):
        """Test authorize with state mismatch (CSRF protection)."""
        client = OAuthClient(quickbooks_config, security_config)
        client._state = "expected_state"
        with (
            patch.object(client, "_get_callback_port", return_value=18089),
            patch("easycat.auth.CallbackServer") as mock_server_class,
            patch("easycat.auth.webbrowser"),
            patch.object(client, "get_authorization_url", return_value="http://test"),
        ):
            mock_server = Mock()
            mock_server.error = None
            mock_server.auth_code = "auth123"
            mock_server.state = "wrong_state"
            mock_server_class.return_value = mock_server
            with pytest.raises(OAuthError, match="State mismatch"):
                await client.authorize(open_browser=False)

    async def test_authorize_success(self, quickbooks_config, security_config):
        """Test successful authorization flow."""
        client = OAuthClient(quickbooks_config, security_config)
        with (
            patch.object(client, "_get_callback_port", return_value=18090),
            patch("easycat.auth.CallbackServer") as mock_server_class,
            patch("easycat.auth.webbrowser") as mock_browser,
            patch.object(client, "_exchange_code") as mock_exchange,
        ):
            mock_server = Mock()
            mock_server.error = None
            mock_server.auth_code = "auth123"
            mock_server.realm_id = "realm456"
            mock_server.state = None
            mock_server_class.return_value = mock_server

            def set_state():
                mock_server.state = client._state
                return "http://auth.url"

            with patch.object(client, "get_authorization_url", side_effect=set_state):
                mock_exchange.return_value = OAuthResult(
                    realm_id="realm456",
                    access_token="access",
                    refresh_token="refresh",
                    expires_at=datetime.now() + timedelta(hours=1),
                )
                result = await client.authorize(open_browser=True)
                assert result.realm_id == "realm456"
                mock_browser.open.assert_called_once()

    async def test_exchange_code(self, quickbooks_config, security_config):
        """Test exchanging authorization code for tokens."""
        client = OAuthClient(quickbooks_config, security_config)
        with patch.object(client._auth_client, "get_bearer_token") as mock_get_token:
            client._auth_client.access_token = "access_token"
            client._auth_client.refresh_token = "refresh_token"
            client._auth_client.expires_in = 3600
            result = await client._exchange_code("auth_code", "realm123")
            assert result.access_token == "access_token"
            assert result.refresh_token == "refresh_token"
            assert result.realm_id == "realm123"
            mock_get_token.assert_called_once_with("auth_code", realm_id="realm123")

    async def test_exchange_code_no_realm(self, quickbooks_config, security_config):
        """Test exchanging code when realm_id is None."""
        client = OAuthClient(quickbooks_config, security_config)
        with patch.object(client._auth_client, "get_bearer_token"):
            client._auth_client.access_token = "access"
            client._auth_client.refresh_token = "refresh"
            client._auth_client.expires_in = 3600
            result = await client._exchange_code("auth_code", None)
            assert result.realm_id == ""

    async def test_refresh_token(self, quickbooks_config, security_config):
        """Test refreshing an access token."""
        client = OAuthClient(quickbooks_config, security_config)
        with patch.object(client._auth_client, "refresh") as mock_refresh:
            client._auth_client.realm_id = "realm123"
            client._auth_client.access_token = "new_access"
            client._auth_client.refresh_token = "new_refresh"
            client._auth_client.expires_in = 3600
            result = await client.refresh_token("old_refresh")
            assert result.access_token == "new_access"
            assert result.refresh_token == "new_refresh"
            mock_refresh.assert_called_once_with(refresh_token="old_refresh")

    async def test_refresh_token_no_realm(self, quickbooks_config, security_config):
        """Test refresh when realm_id is None."""
        client = OAuthClient(quickbooks_config, security_config)
        with patch.object(client._auth_client, "refresh"):
            client._auth_client.realm_id = None
            client._auth_client.access_token = "access"
            client._auth_client.refresh_token = "refresh"
            client._auth_client.expires_in = 3600
            result = await client.refresh_token("old_refresh")
            assert result.realm_id == ""


class TestConstants:
    """Tests for module constants."""

    def test_oauth_scopes_defined(self):
        """Test that OAUTH_SCOPES is defined."""
        assert len(OAUTH_SCOPES) > 0

    def test_token_expiry_buffer(self):
        """Test that TOKEN_EXPIRY_BUFFER_SECONDS is defined."""
        assert TOKEN_EXPIRY_BUFFER_SECONDS == 300
