"""Tests for RelayTV URL safety helpers."""

from custom_components.relaytv.url_utils import canonical_media_key, sanitize_url


def test_sanitize_url_removes_credentials_and_signatures() -> None:
    value = (
        "HTTP://user:password@Media.Example/Videos/abc/stream"
        "?api_key=secret&static=true&X-Amz-Signature=signed#fragment"
    )

    assert sanitize_url(value) == "http://media.example/Videos/abc/stream?static=true"


def test_canonical_media_key_sorts_safe_query_parameters() -> None:
    first = "https://media.example/watch?v=123&lang=en&token=secret"
    second = "https://MEDIA.example/watch?lang=en&v=123&token=other"

    assert canonical_media_key(first) == canonical_media_key(second)
    assert canonical_media_key(first) == "https://media.example/watch?lang=en&v=123"
