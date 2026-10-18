"""URL safety and stable media-key helpers."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


# Keep in sync with _SENSITIVE_QUERY_KEYS in the RelayTV server's
# public_media.py; both sides must redact the same credential parameters.
_SENSITIVE_QUERY_KEYS = {
    "access_token",
    "apikey",
    "api_key",
    "auth",
    "authorization",
    "auth_token",
    "cookie",
    "exp",
    "expires",
    "hdnea",
    "hdnts",
    "jwt",
    "key-pair-id",
    "policy",
    "sig",
    "signature",
    "token",
    "x-emby-token",
    "x-jellyfin-token",
    "x-plex-token",
}


def _is_sensitive_query_key(key: str) -> bool:
    normalized = str(key or "").strip().lower()
    return normalized in _SENSITIVE_QUERY_KEYS or normalized.startswith("x-amz-")


def _filtered_query(query: str) -> str:
    pairs = [
        (key, val)
        for key, val in parse_qsl(query, keep_blank_values=True)
        if not _is_sensitive_query_key(key)
    ]
    return urlencode(pairs, doseq=True)


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
        # Relative identifiers from older servers can still carry
        # credentials in their query string.
        return urlunsplit((parsed.scheme, "", parsed.path, _filtered_query(parsed.query), ""))

    hostname = (parsed.hostname or "").strip().rstrip(".").lower()
    if not hostname:
        return ""
    try:
        port = parsed.port
    except ValueError:
        return ""
    netloc = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path, _filtered_query(parsed.query), ""))


def normalize_base_url(value: object) -> str:
    """Normalize user input into a validated HTTP(S) base URL without credentials."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"http://{raw}"
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        return ""
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https") or not parsed.netloc:
        return ""
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return ""
    hostname = (parsed.hostname or "").strip().rstrip(".").lower()
    if not hostname:
        return ""
    host_part = f"[{hostname}]" if ":" in hostname else hostname
    netloc = f"{host_part}:{port}" if port is not None else host_part
    path = (parsed.path or "").rstrip("/")
    return f"{scheme}://{netloc}{path}"


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
