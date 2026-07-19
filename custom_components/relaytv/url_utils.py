"""URL safety and stable media-key helpers."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_SENSITIVE_QUERY_KEYS = {
    "access_token",
    "apikey",
    "api_key",
    "authorization",
    "auth_token",
    "cookie",
    "expires",
    "hdnea",
    "hdnts",
    "key-pair-id",
    "policy",
    "sig",
    "signature",
    "token",
}


def _is_sensitive_query_key(key: str) -> bool:
    normalized = str(key or "").strip().lower()
    return normalized in _SENSITIVE_QUERY_KEYS or normalized.startswith("x-amz-")


def sanitize_url(value: object) -> str:
    """Remove credentials, fragments, and transient signing parameters."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except Exception:
        return ""
    if not parsed.scheme or not parsed.netloc:
        return raw

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return ""
    netloc = hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    query = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_sensitive_query_key(key)
    ]
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path, urlencode(query, doseq=True), ""))


def canonical_media_key(value: object) -> str:
    """Return a deterministic, credential-free key for resume state."""
    safe = sanitize_url(value)
    if not safe:
        return ""
    try:
        parsed = urlsplit(safe)
    except Exception:
        return safe
    if not parsed.scheme or not parsed.netloc:
        return safe
    query = sorted(parse_qsl(parsed.query, keep_blank_values=True))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query, doseq=True), ""))
