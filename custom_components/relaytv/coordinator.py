"""Coordinator for RelayTV polling."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .relaytv_api import RelayTVApi

_LOGGER = logging.getLogger(__name__)


class RelayTVCoordinator(DataUpdateCoordinator[dict]):
    """Poll RelayTV for its current status."""

    def __init__(self, hass: HomeAssistant, api: RelayTVApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="RelayTV status",
            update_interval=timedelta(seconds=3),
        )
        self.api = api

    async def _async_update_data(self) -> dict:
        data = await self.api.get_status()
        if data is None:
            raise UpdateFailed("Unable to fetch RelayTV status")
        return data
