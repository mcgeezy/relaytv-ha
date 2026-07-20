"""Tests for RelayTV URL safety helpers."""

from custom_components.relaytv.url_utils import canonical_media_key, sanitize_url


def test_sanitize_url_removes_credentials_and_signatures() -> None:
    value = (
        "HTTP://user:password@Media.Example/Videos/abc/stream"
        "?api_key=secret&static=true&X-Amz-Signature=signed#fragment"
    )

    assert sanitize_url(value) == "http://media.example/Videos/abc/stream?static=true"


def test_sanitize_url_strips_emby_jellyfin_and_jwt_auth_keys() -> None:
    value = (
        "https://media.example/watch"
        "?v=1&X-Emby-Token=secret&X-Jellyfin-Token=secret&jwt=secret&auth=secret&exp=99"
    )

    assert sanitize_url(value) == "https://media.example/watch?v=1"


def test_sanitize_url_filters_relative_url_queries() -> None:
    assert sanitize_url("/watch?token=secret&v=123") == "/watch?v=123"
    assert sanitize_url("/thumbs/abc.jpg") == "/thumbs/abc.jpg"


def test_sanitize_url_preserves_ipv6_hosts() -> None:
    value = "http://[2001:db8::1]:8787/watch?api_key=secret&v=1"

    assert sanitize_url(value) == "http://[2001:db8::1]:8787/watch?v=1"


def test_canonical_media_key_sorts_safe_query_parameters() -> None:
    first = "https://media.example/watch?v=123&lang=en&token=secret"
    second = "https://MEDIA.example/watch?lang=en&v=123&token=other"

    assert canonical_media_key(first) == canonical_media_key(second)
    assert canonical_media_key(first) == "https://media.example/watch?lang=en&v=123"
