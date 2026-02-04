"""Authentication module for QuickBooks OAuth."""

import asyncio
import secrets
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes

from easycat.config import QuickBooksConfig, SecurityConfig
from easycat.db.models import Token

OAUTH_SCOPES = [Scopes.ACCOUNTING]
TOKEN_EXPIRY_BUFFER_SECONDS = 300


@dataclass
class OAuthResult:
    """Result of OAuth authorization flow."""

    realm_id: str
    access_token: str
    refresh_token: str
    expires_at: datetime


class TokenEncryption:
    """Handles encryption and decryption of OAuth tokens."""

    def __init__(self, encryption_key: str | None):
        self._fernet = Fernet(encryption_key.encode()) if encryption_key else None

    def encrypt(self, value: str) -> str:
        """Encrypt a value if encryption is configured."""
        if self._fernet:
            return self._fernet.encrypt(value.encode()).decode()
        return value

    def decrypt(self, value: str) -> str:
        """Decrypt a value if encryption is configured."""
        if self._fernet:
            return self._fernet.decrypt(value.encode()).decode()
        return value


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""

    auth_code: str | None = None
    realm_id: str | None = None
    state: str | None = None
    error: str | None = None

    def log_message(self, format: str, *args) -> None:
        """Suppress HTTP server logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET request from OAuth callback."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        CallbackHandler.auth_code = params.get("code", [None])[0]
        CallbackHandler.realm_id = params.get("realmId", [None])[0]
        CallbackHandler.state = params.get("state", [None])[0]
        CallbackHandler.error = params.get("error", [None])[0]
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        if CallbackHandler.error:
            title = 'Authorization Failed'
            message = f'Error: {CallbackHandler.error}'
            icon = '&#10060;'
            color = '#dc3545'
        else:
            title = 'Authorization Successful'
            message = 'You can close this window and return to EasyCat.'
            icon = '&#10004;'
            color = '#28a745'
        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>EasyCat - {title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
        }}
        .container {{
            text-align: center;
            padding: 3rem;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 1rem;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}
        .icon {{
            font-size: 4rem;
            color: {color};
            margin-bottom: 1rem;
        }}
        h1 {{
            margin: 0 0 1rem 0;
            font-size: 1.75rem;
            font-weight: 600;
        }}
        p {{
            margin: 0;
            opacity: 0.8;
            font-size: 1.1rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">{icon}</div>
        <h1>{title}</h1>
        <p>{message}</p>
    </div>
</body>
</html>'''
        self.wfile.write(html.encode())


class CallbackServer:
    """Local HTTP server to receive OAuth callbacks."""

    def __init__(self, port: int):
        self._port = port
        self._server: HTTPServer | None = None
        self._thread: Thread | None = None

    def start(self) -> None:
        """Start the callback server in a background thread."""
        CallbackHandler.auth_code = None
        CallbackHandler.realm_id = None
        CallbackHandler.state = None
        CallbackHandler.error = None
        self._server = HTTPServer(("localhost", self._port), CallbackHandler)
        self._thread = Thread(target=self._server.handle_request, daemon=True)
        self._thread.start()

    def wait_for_callback(self, timeout: float = 120.0) -> None:
        """Wait for the callback to be received."""
        if self._thread:
            self._thread.join(timeout=timeout)

    def stop(self) -> None:
        """Stop the callback server."""
        if self._server:
            self._server.server_close()
            self._server = None
        self._thread = None

    @property
    def auth_code(self) -> str | None:
        """Get the authorization code from the callback."""
        return CallbackHandler.auth_code

    @property
    def realm_id(self) -> str | None:
        """Get the realm ID from the callback."""
        return CallbackHandler.realm_id

    @property
    def state(self) -> str | None:
        """Get the state from the callback."""
        return CallbackHandler.state

    @property
    def error(self) -> str | None:
        """Get any error from the callback."""
        return CallbackHandler.error


class OAuthClient:
    """OAuth client for QuickBooks authentication."""

    def __init__(self, config: QuickBooksConfig, security_config: SecurityConfig | None = None):
        self._config = config
        self._encryption = TokenEncryption(
            security_config.encryption_key if security_config else None
        )
        self._auth_client = AuthClient(
            client_id=config.client_id,
            client_secret=config.client_secret,
            redirect_uri=config.redirect_uri,
            environment=config.environment,
        )
        self._state: str | None = None

    def get_authorization_url(self) -> str:
        """Generate the authorization URL for the OAuth flow."""
        self._state = secrets.token_urlsafe(32)
        return self._auth_client.get_authorization_url(OAUTH_SCOPES, state_token=self._state)

    async def authorize(self, open_browser: bool = True) -> OAuthResult:
        """Run the full OAuth authorization flow."""
        port = self._get_callback_port()
        server = CallbackServer(port)
        server.start()
        try:
            auth_url = self.get_authorization_url()
            if open_browser:
                webbrowser.open(auth_url)
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: server.wait_for_callback(timeout=120.0)
            )
            if server.error:
                raise OAuthError(f"Authorization failed: {server.error}")
            if not server.auth_code:
                raise OAuthError("No authorization code received")
            if server.state != self._state:
                raise OAuthError("State mismatch - possible CSRF attack")
            return await self._exchange_code(server.auth_code, server.realm_id)
        finally:
            server.stop()

    async def _exchange_code(self, auth_code: str, realm_id: str | None) -> OAuthResult:
        """Exchange authorization code for tokens."""
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._auth_client.get_bearer_token(auth_code, realm_id=realm_id)
        )
        expires_at = datetime.now() + timedelta(seconds=self._auth_client.expires_in)
        return OAuthResult(
            realm_id=realm_id or "",
            access_token=self._auth_client.access_token,
            refresh_token=self._auth_client.refresh_token,
            expires_at=expires_at,
        )

    async def refresh_token(self, refresh_token: str) -> OAuthResult:
        """Refresh an expired access token."""
        decrypted_refresh = self._encryption.decrypt(refresh_token)
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._auth_client.refresh(refresh_token=decrypted_refresh)
        )
        expires_at = datetime.now() + timedelta(seconds=self._auth_client.expires_in)
        return OAuthResult(
            realm_id=self._auth_client.realm_id or "",
            access_token=self._auth_client.access_token,
            refresh_token=self._auth_client.refresh_token,
            expires_at=expires_at,
        )

    def encrypt_token(self, token: str) -> str:
        """Encrypt a token for storage."""
        return self._encryption.encrypt(token)

    def decrypt_token(self, token: str) -> str:
        """Decrypt a token from storage."""
        return self._encryption.decrypt(token)

    def is_token_expired(self, token: Token) -> bool:
        """Check if a token is expired or about to expire."""
        buffer = timedelta(seconds=TOKEN_EXPIRY_BUFFER_SECONDS)
        return datetime.now() >= (token.expires_at - buffer)

    def _get_callback_port(self) -> int:
        """Extract the port from the redirect URI."""
        parsed = urlparse(self._config.redirect_uri)
        return parsed.port or 8085


class OAuthError(Exception):
    """Exception raised for OAuth-related errors."""

    pass
