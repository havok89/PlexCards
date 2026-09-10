import hmac
import hashlib
import json
import base64
import time
import logging
import secrets
import requests
from typing import Optional, Dict, Any, Tuple
from fastapi import Request, HTTPException, Depends
from backend import config
from backend.db import get_setting, set_setting

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "plexcards_session"
SESSION_DURATION_DAYS = 7

def get_app_secret() -> str:
    """Retrieve secret key from config or database, generating if needed."""
    if config.SECRET_KEY:
        return config.SECRET_KEY
    key = get_setting("auth_secret_key", "")
    if not key:
        key = secrets.token_hex(32)
        set_setting("auth_secret_key", key)
    return key

def get_client_id() -> str:
    """Get or generate persistent client identifier for Plex OAuth."""
    if config.PLEX_CLIENT_IDENTIFIER and config.PLEX_CLIENT_IDENTIFIER not in ("PlexPosters-App", "PlexCards-App"):
        return config.PLEX_CLIENT_IDENTIFIER
    client_id = get_setting("plex_client_identifier", "")
    if not client_id:
        client_id = f"PlexCards-{secrets.token_hex(8)}"
        set_setting("plex_client_identifier", client_id)
    return client_id

def create_session_token(user_data: Dict[str, Any], duration_days: int = SESSION_DURATION_DAYS) -> str:
    """Create a tamper-proof HMAC-SHA256 signed session token."""
    secret = get_app_secret()
    payload = {
        **user_data,
        "exp": int(time.time()) + (duration_days * 86400)
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"

def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate a session token and return user data if valid and unexpired."""
    if not token or "." not in token:
        return None
    try:
        payload_b64, sig = token.split(".", 1)
        secret = get_app_secret()
        expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        
        # Add back base64 padding if needed
        rem = len(payload_b64) % 4
        if rem > 0:
            payload_b64 += "=" * (4 - rem)
            
        data = json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
        if data.get("exp", 0) < time.time():
            return None  # Expired
        return data
    except Exception as e:
        logger.debug(f"Session token verification failed: {e}")
        return None

class PlexOAuth:
    BASE_URL = "https://plex.tv/api/v2"

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {
            "X-Plex-Product": "PlexCards",
            "X-Plex-Version": "1.0.0",
            "X-Plex-Client-Identifier": get_client_id(),
            "Accept": "application/json"
        }

    @classmethod
    def create_pin(cls) -> Dict[str, Any]:
        """Request a new PIN from Plex.tv for OAuth authorization."""
        url = f"{cls.BASE_URL}/pins?strong=true"
        r = requests.post(url, headers=cls.get_headers(), timeout=10)
        r.raise_for_status()
        data = r.json()
        client_id = get_client_id()
        code = data["code"]
        auth_url = (
            f"https://app.plex.tv/auth#?clientID={client_id}&code={code}"
            f"&context%5Bdevice%5D%5Bproduct%5D=PlexCards"
        )
        return {
            "pin_id": data["id"],
            "code": code,
            "auth_url": auth_url
        }

    @classmethod
    def poll_pin(cls, pin_id: int) -> Optional[str]:
        """Check if the user has completed Plex authorization."""
        url = f"{cls.BASE_URL}/pins/{pin_id}"
        r = requests.get(url, headers=cls.get_headers(), timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("authToken")
        return None

    @classmethod
    def get_user_profile(cls, auth_token: str) -> Optional[Dict[str, Any]]:
        """Fetch user profile from Plex.tv using auth token."""
        url = f"{cls.BASE_URL}/user"
        headers = {**cls.get_headers(), "X-Plex-Token": auth_token}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
        return None

    @classmethod
    def verify_access(cls, auth_token: str, server_machine_id: Optional[str] = None) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Verify user profile and ensure they own the server or are allowed."""
        user = cls.get_user_profile(auth_token)
        if not user:
            return False, None, "Could not fetch Plex user profile."

        username = user.get("username", "")
        email = user.get("email", "")

        # 1. Check explicit ALLOWED_USERS whitelist if configured
        if config.ALLOWED_USERS:
            if username.lower() in config.ALLOWED_USERS or (email and email.lower() in config.ALLOWED_USERS):
                return True, user, "Access granted via whitelist."
            return False, user, f"User '{username}' is not in the ALLOWED_USERS whitelist."

        # 2. Check if user owns the local Plex server
        url = f"{cls.BASE_URL}/resources?includeHttps=1"
        headers = {**cls.get_headers(), "X-Plex-Token": auth_token}
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                resources = r.json()
                for res in resources:
                    if res.get("provides") and "server" in res.get("provides").split(","):
                        if server_machine_id and res.get("clientIdentifier") == server_machine_id:
                            if res.get("owned"):
                                return True, user, "Access granted: Verified Plex Server Owner."
                            else:
                                return False, user, "Access denied: You do not own this Plex Media Server."
                        elif not server_machine_id and res.get("owned"):
                            return True, user, "Access granted: Verified Plex Server Owner."
        except Exception as e:
            logger.warning(f"Error checking Plex resources for {username}: {e}")

        # If not owned and no whitelist, deny
        return False, user, "Access denied: You must be the owner of this Plex Media Server."

def get_current_user(request: Request) -> Dict[str, Any]:
    """FastAPI dependency to protect endpoints when ENABLE_AUTH is true."""
    if not config.ENABLE_AUTH:
        return {"username": "admin", "is_admin": True, "auth_enabled": False}

    token = request.cookies.get(SESSION_COOKIE_NAME) or request.cookies.get("plexposters_session")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = verify_session_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session invalid or expired")

    return user
