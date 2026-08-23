from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import time
from email.utils import parsedate_to_datetime
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

GMAIL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_SCOPES = " ".join(
    [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/gmail.readonly",
    ]
)


def gmail_oauth_ready() -> bool:
    return get_settings().gmail_oauth_configured


def _sign_state(user_id: str) -> str:
    settings = get_settings()
    payload = {"uid": user_id, "ts": int(time.time())}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(settings.secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{raw}.{sig}"


def verify_state(state: str, max_age_seconds: int = 600) -> Optional[str]:
    try:
        raw, sig = state.rsplit(".", 1)
    except ValueError:
        return None
    settings = get_settings()
    expected = hmac.new(settings.secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(expected, sig):
        return None
    pad = "=" * (-len(raw) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw + pad).decode())
    except Exception:  # noqa: BLE001
        return None
    if int(time.time()) - int(payload.get("ts", 0)) > max_age_seconds:
        return None
    return str(payload.get("uid") or "") or None


def build_authorize_url(user_id: str) -> str:
    settings = get_settings()
    if not settings.gmail_oauth_configured:
        raise RuntimeError(
            "Gmail OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env"
        )
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": GMAIL_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": _sign_state(user_id),
    }
    return f"{GMAIL_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict[str, Any]:
    settings = get_settings()
    with httpx.Client(timeout=30.0) as client:
        token_resp = client.post(
            GMAIL_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()
        access = tokens.get("access_token")
        if not access:
            raise RuntimeError("Google did not return an access token")
        user_resp = client.get(
            GMAIL_USERINFO_URL,
            headers={"Authorization": f"Bearer {access}"},
        )
        user_resp.raise_for_status()
        info = user_resp.json()
    return {
        "access_token": access,
        "refresh_token": tokens.get("refresh_token"),
        "expires_in": int(tokens.get("expires_in") or 3600),
        "token_type": tokens.get("token_type") or "Bearer",
        "scope": tokens.get("scope") or GMAIL_SCOPES,
        "email": info.get("email"),
        "name": info.get("name"),
        "picture": info.get("picture"),
        "obtained_at": int(time.time()),
    }


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    settings = get_settings()
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            GMAIL_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {
        "access_token": data["access_token"],
        "expires_in": int(data.get("expires_in") or 3600),
        "token_type": data.get("token_type") or "Bearer",
        "scope": data.get("scope"),
        "obtained_at": int(time.time()),
    }


def ensure_access_token(tracking: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return a valid access token, refreshing when needed. May update tracking dict."""
    access = tracking.get("access_token")
    obtained = int(tracking.get("obtained_at") or 0)
    expires_in = int(tracking.get("expires_in") or 3600)
    if access and obtained and (time.time() < obtained + expires_in - 60):
        return access, tracking

    refresh = tracking.get("refresh_token")
    if not refresh:
        raise RuntimeError("Gmail session expired. Click Connect Gmail again.")

    refreshed = refresh_access_token(refresh)
    tracking["access_token"] = refreshed["access_token"]
    tracking["expires_in"] = refreshed["expires_in"]
    tracking["obtained_at"] = refreshed["obtained_at"]
    if refreshed.get("scope"):
        tracking["scope"] = refreshed["scope"]
    return tracking["access_token"], tracking


def _decode_body(payload: dict[str, Any]) -> str:
    data = payload.get("body", {}).get("data")
    if data:
        pad = "=" * (-len(data) % 4)
        try:
            return base64.urlsafe_b64decode(data + pad).decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            return ""
    parts = payload.get("parts") or []
    plain = ""
    html = ""
    for part in parts:
        mime = (part.get("mimeType") or "").lower()
        text = _decode_body(part)
        if mime == "text/plain" and text:
            plain = text
        elif mime == "text/html" and text and not html:
            html = text
        elif not plain and text:
            plain = text
    if plain:
        return plain
    if html:
        return re.sub(r"<[^>]+>", " ", html)
    return ""


def fetch_gmail_messages(
    access_token: str,
    *,
    watch_terms: list[str] | None = None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Fetch recent Gmail messages related to watched scholarship terms."""
    terms = [t for t in (watch_terms or []) if t][:8]
    query_bits = []
    for term in terms:
        safe = re.sub(r"[^\w\s\-]", "", term).strip()
        if safe:
            query_bits.append(f"subject:({safe})")
    query_bits.extend(
        [
            'subject:(scholarship OR fellowship OR NSP OR "under review")',
            "from:(scholarships.gov.in OR aicte OR ugc OR education)",
        ]
    )
    query = " OR ".join(query_bits) if query_bits else "newer_than:90d"
    headers = {"Authorization": f"Bearer {access_token}"}
    messages: list[dict[str, Any]] = []

    with httpx.Client(timeout=45.0) as client:
        list_resp = client.get(
            f"{GMAIL_API}/messages",
            headers=headers,
            params={"q": query, "maxResults": min(limit, 50)},
        )
        if list_resp.status_code == 401:
            raise RuntimeError("Gmail authorization expired. Connect Gmail again.")
        list_resp.raise_for_status()
        ids = [m["id"] for m in (list_resp.json().get("messages") or [])]

        if not ids:
            # Fallback: recent inbox mail; matching still happens later
            fallback = client.get(
                f"{GMAIL_API}/messages",
                headers=headers,
                params={"q": "newer_than:30d", "maxResults": min(limit, 30)},
            )
            fallback.raise_for_status()
            ids = [m["id"] for m in (fallback.json().get("messages") or [])]

        for msg_id in ids[:limit]:
            detail = client.get(
                f"{GMAIL_API}/messages/{msg_id}",
                headers=headers,
                params={"format": "full"},
            )
            if detail.status_code != 200:
                continue
            data = detail.json()
            headers_list = (data.get("payload") or {}).get("headers") or []
            header_map = {h.get("name", "").lower(): h.get("value", "") for h in headers_list}
            body = _decode_body(data.get("payload") or {})
            if not body:
                body = data.get("snippet") or ""
            messages.append(
                {
                    "message_id": data.get("id") or msg_id,
                    "subject": header_map.get("subject", ""),
                    "from_address": header_map.get("from", ""),
                    "body": body,
                    "date": header_map.get("date", ""),
                }
            )
    return messages
