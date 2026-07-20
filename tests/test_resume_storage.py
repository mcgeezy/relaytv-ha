"""Tests for RelayTV resume-storage migration."""

from custom_components.relaytv import MAX_RESUME_POSITIONS, _migrate_resume_positions


def test_resume_migration_removes_credentials_and_deduplicates() -> None:
    value = {
        "https://media.example/watch?v=123&api_key=first": 120.0,
        "https://MEDIA.example/watch?api_key=second&v=123": 150.0,
        "https://media.example/invalid": "not-a-position",
    }

    result = _migrate_resume_positions(value)

    assert result == {"https://media.example/watch?v=123": 150.0}
    assert "api_key" not in repr(result)


def test_resume_migration_caps_oldest_entries() -> None:
    value = {f"https://media.example/watch/{index}": index for index in range(MAX_RESUME_POSITIONS + 5)}

    result = _migrate_resume_positions(value)

    assert len(result) == MAX_RESUME_POSITIONS
    assert "https://media.example/watch/0" not in result
    assert f"https://media.example/watch/{MAX_RESUME_POSITIONS + 4}" in result
