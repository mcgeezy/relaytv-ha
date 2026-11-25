"""Tests for RelayTV URL safety helpers."""

from custom_components.relaytv.url_utils import canonical_media_key, normalize_base_url, sanitize_url


def test_sanitize_url_removes_credentials_and_signatures() -> None:
    value = (
        "HTTP://user:password@Media.Example/Videos/abc/stream"
        "?api_key=secret&static=true&X-Amz-Signature=signed#fragment"
    )

    assert sanitize_url(value) == "http://media.example/Videos/abc/stream?static=true"


def test_sanitize_url_strips_emby_jellyfin_plex_and_jwt_auth_keys() -> None:
    value = (
        "https://media.example/watch"
        "?v=1&X-Emby-Token=secret&X-Jellyfin-Token=secret&X-Plex-Token=secret&jwt=secret&auth=secret&exp=99"
    )

    assert sanitize_url(value) == "https://media.example/watch?v=1"


def test_sanitize_url_redacts_rtsp_userinfo_and_camera_auth_query_keys() -> None:
    rtsp_url = (
        "RTSP://admin:s3cr3t@Cam.Local.:554/h264Preview_01_main"
        "?channel=1&user=admin&username=admin&usr=admin"
        "&pass=s3cr3t&passwd=s3cr3t&password=s3cr3t&pwd=s3cr3t&subtype=0#live"
    )
    rtsps_url = "rtsps://viewer:topsecret@nvr.local:7441/front_door?USER=viewer&PASSWORD=topsecret&stream=main"

    assert sanitize_url(rtsp_url) == "rtsp://cam.local:554/h264Preview_01_main?channel=1&subtype=0"
    assert sanitize_url(rtsps_url) == "rtsps://nvr.local:7441/front_door?stream=main"
    assert (
        canonical_media_key(rtsp_url)
        == "rtsp://cam.local:554/h264Preview_01_main?channel=1&subtype=0"
    )
    assert normalize_base_url("rtsp://cam.local:554") == ""
    assert normalize_base_url("rtsps://nvr.local:7441") == ""


def test_sanitize_url_filters_relative_url_queries() -> None:
    assert sanitize_url("/watch?token=secret&X-Plex-Token=secret&v=123") == "/watch?v=123"
    assert sanitize_url("/thumbs/abc.jpg") == "/thumbs/abc.jpg"


def test_sanitize_url_preserves_ipv6_hosts() -> None:
    value = "http://[2001:db8::1]:8787/watch?api_key=secret&v=1"

    assert sanitize_url(value) == "http://[2001:db8::1]:8787/watch?v=1"


def test_sanitize_url_handles_malformed_ports_and_trailing_dots_safely() -> None:
    assert sanitize_url("http://media.example.:8787/watch?v=1") == "http://media.example:8787/watch?v=1"
    assert sanitize_url("http://media.example:99999/watch?v=1") == ""
    assert sanitize_url("http://media.example:abc/watch?v=1") == ""
    assert sanitize_url("http://user@:9/watch?v=1") == ""


def test_normalize_base_url_validates_host_and_port() -> None:
    assert normalize_base_url("RelayTV.local.:8787/") == "http://relaytv.local:8787"
    assert normalize_base_url("https://[2001:db8::1]:8787/relaytv/") == "https://[2001:db8::1]:8787/relaytv"
    assert normalize_base_url("http://relaytv.local:99999") == ""
    assert normalize_base_url("http://relaytv.local:8O87") == ""
    assert normalize_base_url("http://:8787") == ""
    assert normalize_base_url("[relaytv.local]:8787") == ""


def test_canonical_media_key_sorts_safe_query_parameters() -> None:
    first = "https://media.example/watch?v=123&lang=en&token=secret"
    second = "https://MEDIA.example/watch?lang=en&v=123&token=other"

    assert canonical_media_key(first) == canonical_media_key(second)
    assert canonical_media_key(first) == "https://media.example/watch?lang=en&v=123"
