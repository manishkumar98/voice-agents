"""
src/booking/secure_url_generator.py

Generates and verifies HMAC-signed secure URLs for post-call PII submission.

After booking, the agent reads a URL to the user. The user visits the URL
to submit contact details (phone, email) — keeping PII off the voice channel.

URL Format:
    https://{domain}/book/{signed_token}

Token Payload (signed with HMAC-SHA256, expires in TTL seconds):
    {
        "booking_code": "NL-A742",
        "topic": "kyc_onboarding",
        "slot_ist": "2024-02-15T14:00:00+05:30"
    }

Uses itsdangerous.URLSafeTimedSerializer — no external APIs needed.
"""

import os
from datetime import datetime

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_DEFAULT_SALT = "voice-agent-booking-v1"


def _get_serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt=_DEFAULT_SALT)


def generate_secure_url(
    booking_code: str,
    topic: str,
    slot_ist: str | datetime,
    secret: str | None = None,
    domain: str | None = None,
) -> str:
    """
    Generate a signed secure URL for post-call contact detail submission.

    Args:
        booking_code: e.g. "NL-A742"
        topic:        Canonical topic key, e.g. "kyc_onboarding"
        slot_ist:     ISO 8601 string or datetime of the booked slot (IST)
        secret:       HMAC secret key. Reads SECURE_URL_SECRET from env if not given.
        domain:       Base domain. Reads SECURE_URL_DOMAIN from env if not given.

    Returns:
        A full URL string, e.g.
        "http://localhost:8501/book/InNMLUE3NDIi.abc123..."
    """
    if secret is None:
        secret = os.environ.get("SECURE_URL_SECRET", "dev_secret_change_in_production_minimum32chars")
    if domain is None:
        domain = os.environ.get("SECURE_URL_DOMAIN", "http://localhost:8501")

    if isinstance(slot_ist, datetime):
        slot_ist_str = slot_ist.isoformat()
    else:
        slot_ist_str = slot_ist

    payload = {
        "booking_code": booking_code,
        "topic": topic,
        "slot_ist": slot_ist_str,
    }

    serializer = _get_serializer(secret)
    token = serializer.dumps(payload)
    domain = domain.rstrip("/")
    return f"{domain}/?booking_token={token}"


def verify_secure_url(
    token: str,
    secret: str | None = None,
    max_age_seconds: int | None = None,
) -> dict:
    """
    Verify and decode a secure URL token.

    Args:
        token:           The signed token from the URL path.
        secret:          HMAC secret. Reads SECURE_URL_SECRET from env if not given.
        max_age_seconds: Token TTL. Reads SECURE_URL_TTL_SECONDS from env if not given.

    Returns:
        The decoded payload dict: {"booking_code": ..., "topic": ..., "slot_ist": ...}

    Raises:
        SignatureExpired: Token has expired.
        BadSignature:     Token is invalid or tampered.
    """
    if secret is None:
        secret = os.environ.get("SECURE_URL_SECRET", "dev_secret_change_in_production_minimum32chars")
    if max_age_seconds is None:
        try:
            max_age_seconds = int(os.environ.get("SECURE_URL_TTL_SECONDS", "86400"))
        except ValueError:
            max_age_seconds = 86400

    serializer = _get_serializer(secret)
    # Raises SignatureExpired or BadSignature on failure
    payload = serializer.loads(token, max_age=max_age_seconds)
    return payload


def extract_token_from_url(url: str) -> str:
    """Extract the token portion from a full secure URL."""
    # Support query-param format: ?booking_token=TOKEN
    if "booking_token=" in url:
        return url.split("booking_token=", 1)[1].split("&")[0]
    # Legacy path format: /book/TOKEN
    parts = url.rstrip("/").split("/book/")
    if len(parts) != 2:
        raise ValueError(f"URL does not contain booking_token param or '/book/' path: {url}")
    return parts[1]
