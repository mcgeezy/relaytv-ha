"""Shared Home Assistant test fixtures."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow loading RelayTV from custom_components in tests."""
    yield
