# RelayTV HA 0.6.1

Tighten media URL credential redaction for shared RTSP/RTSPS IP camera and NVR
feeds and document temporary doorbell/camera playback interruptions. It requires
Home Assistant 2026.7 or newer.

## Highlights

- Sync `_SENSITIVE_QUERY_KEYS` in `url_utils.py` with RelayTV server's
  `public_media.py` by redacting `user`, `username`, `usr`, `pass`, `passwd`,
  `password`, and `pwd` query parameters alongside embedded userinfo on
  `rtsp://`, `rtsps://`, and `http(s)://` media URLs.
- Keep RelayTV server base URL normalization strictly restricted to `http` and
  `https`.
- Document a `relaytv.play_temporary` service example for 15-second RTSP
  camera/doorbell interruptions that automatically resume prior playback.

## Compatibility and deployment

- Existing configuration and optional API tokens are reused without migration.
- The minimum supported Home Assistant version remains 2026.7.
- Pair with RelayTV server `0.13.0` or newer to play `rtsp://` and `rtsps://`
  camera/NVR/restream links via `media_player.play_media` and
  `relaytv.play_temporary`.

Breaking changes: None.

## Verification

- Unit tests in `tests/test_url_utils.py` verify embedded userinfo and all
  seven camera auth query keys are stripped from `rtsp://` and `rtsps://` URLs
  while `normalize_base_url()` rejects non-HTTP(S) server URLs.
- GitHub Actions CI (`Tests`, `Hassfest`, and `HACS validation`) runs the full
  test suite and validates `manifest.json` before tagging.

## Upgrade

Install 0.6.1 through HACS when published and restart Home Assistant. Existing
entries and optional API tokens are reused without reconfiguration. The HACS
archive remains flat, with `manifest.json` directly at its root for installation
under `/config/custom_components/relaytv/`.
