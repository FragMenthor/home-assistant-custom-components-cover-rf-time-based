"""Entidade Cover RF Time Based."""
import logging
from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta
from .travelcalculator import TravelCalculator, TravelStatus
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    data = {**config_entry.data, **config_entry.options}
    name = data["name"]

    entity = CoverRFTimeBased(
        name=name,
        travelling_time_up=data.get("travelling_time_up", 25),
        travelling_time_down=data.get("travelling_time_down", 25),
        open_script=data.get("open_script_entity_id"),
        close_script=data.get("close_script_entity_id"),
        stop_script=data.get("stop_script_entity_id"),
        send_stop_at_ends=data.get("send_stop_at_ends", False),
    )

    async_add_entities([entity])


class CoverRFTimeBased(CoverEntity):
    has_entity_name = True
    def __init__(self, name, travelling_time_up, travelling_time_down, open_script, close_script, stop_script, send_stop_at_ends):
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{device_id}"
        self._travel = TravelCalculator(travelling_time_down, travelling_time_up)
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP | CoverEntityFeature.SET_POSITION
        )
        self._open_script = open_script
        self._close_script = close_script
        self._stop_script = stop_script
        self._send_stop_at_ends = send_stop_at_ends
        self._attr_is_closed = None

    async def async_added_to_hass(self):
        async_track_time_interval(self.hass, self._update_travel, timedelta(seconds=1))

    async def _update_travel(self, _now):
        self._attr_current_cover_position = self._travel.current_position()
        self._attr_is_closed = self._attr_current_cover_position == 0
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        self._travel.start_moving(TravelStatus.OPENING, 100)
        if self._open_script:
            await self.hass.services.async_call("script", "turn_on", {"entity_id": self._open_script})
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        self._travel.start_moving(TravelStatus.CLOSING, 0)
        if self._close_script:
            await self.hass.services.async_call("script", "turn_on", {"entity_id": self._close_script})
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        self._travel.stop()
        if self._stop_script:
            await self.hass.services.async_call("script", "turn_on", {"entity_id": self._stop_script})
        self.async_write_ha_state()
