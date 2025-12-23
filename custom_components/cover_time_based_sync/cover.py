# custom_components/cover_time_based_sync/cover.py
"""Cover Time Based Sync — entidade Cover baseada em tempo, com scripts,
sensores de contacto e modo 'Controlo Único' (RF) nativo com próxima ação em atributo."""
from __future__ import annotations

import asyncio
import logging
# custom_components/cover_time_based_sync/cover.py
"""Cover Time Based Sync — entidade Cover baseada em tempo, com scripts,
sensores de contacto e modo 'Controlo Único' (RF) nativo com próxima ação em atributo."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    ATTR_POSITION,
)

from .const import (
    DOMAIN,
    CONF_TRAVELLING_TIME_UP,
    CONF_TRAVELLING_TIME_DOWN,
    CONF_OPEN_SCRIPT,
    CONF_CLOSE_SCRIPT,
    CONF_STOP_SCRIPT,
    CONF_SEND_STOP_AT_ENDS,
    CONF_ALWAYS_CONFIDENT,
    CONF_SMART_STOP,
    CONF_NAME as CONF_FRIENDLY_NAME,
    CONF_OPEN_CONTACT_SENSOR,
    CONF_CLOSE_CONTACT_SENSOR,
    CONF_SINGLE_CONTROL_ENABLED,
    CONF_SINGLE_CONTROL_PULSE_MS,
    ATTR_CONFIDENT,
    ATTR_POSITION_TYPE,
)
from .travelcalculator import TravelCalculator

_LOGGER = logging.getLogger(__name__)
SIGNAL_SET_KNOWN_POSITION = f"{DOMAIN}_set_known_position"
SIGNAL_SET_KNOWN_ACTION = f"{DOMAIN}_set_known_action"
SIGNAL_ACTIVATE_SCRIPT = f"{DOMAIN}_activate_script"

DEFAULT_TRAVEL_TIME = 25
MID_RANGE_LOW = 20
MID_RANGE_HIGH = 80
UPDATE_INTERVAL_SEC = 0.5  # já atualizado

NEXT_OPEN = "open"
NEXT_CLOSE = "close"
NEXT_STOP = "stop"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hass.data.setdefault(DOMAIN, {})
    entity = TimeBasedSyncCover(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = {"entity": entity}
    async_add_entities([entity], update_before_add=False)

    async def _async_update_listener(updated_entry: ConfigEntry) -> None:
        ent: TimeBasedSyncCover = hass.data[DOMAIN][updated_entry.entry_id]["entity"]
        ent.apply_entry(updated_entry)
        ent.async_write_ha_state()
        _LOGGER.debug("Entry %s updated; entity refreshed", updated_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities_cb: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    entry_like = type("EntryLike", (), {"data": config, "options": {}, "entry_id": "yaml"})()
    entity = TimeBasedSyncCover(hass, entry_like)
    async_add_entities_cb([entity], update_before_add=False)


class TimeBasedSyncCover(CoverEntity, RestoreEntity):
    _attr_assumed_state = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        self._position: int = 0
        self._moving_task: Optional[asyncio.Task] = None
        self._moving_direction: Optional[str] = None
        self._last_confident_state: Optional[bool] = None

        self._attr_unique_id = f"{DOMAIN}_{getattr(entry, 'entry_id', 'default')}"

        self._unsub_known_position = None
        self._unsub_known_action = None
        self._unsub_close_contact = None
        self._unsub_open_contact = None
        self._unsub_activate_script = None

        self._calc: Optional[TravelCalculator] = None

        self._close_contact_sensor_id: Optional[str] = None
        self._open_contact_sensor_id: Optional[str] = None

        # Controlo Único (RF)
        self._single_control_enabled: bool = False
        self._single_control_script_id: Optional[str] = None
        self._single_pulse_delay_ms: int = 400
        self._single_next_action: str = NEXT_OPEN

        self.apply_entry(entry)

    # -------- Utilitários --------
    def _opt_or_data(self, key: str, default: Any = None) -> Any:
        data = dict(getattr(self.entry, "data", {}) or {})
        options = dict(getattr(self.entry, "options", {}) or {})
        return options.get(key, data.get(key, default))

    def _first_script(self) -> Optional[str]:
        for key in (CONF_OPEN_SCRIPT, CONF_CLOSE_SCRIPT, CONF_STOP_SCRIPT):
            val = self._opt_or_data(key)
            if isinstance(val, str) and val:
                return val
        return None

    def apply_entry(self, entry: ConfigEntry) -> None:
        self.entry = entry
        name = self._opt_or_data(CONF_FRIENDLY_NAME, self._opt_or_data("name", "Time Based Cover"))
        self._attr_name = name

        self._travel_up: float = float(self._opt_or_data(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME))
        self._travel_down: float = float(self._opt_or_data(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME))

        self._open_script_id: Optional[str] = self._opt_or_data(CONF_OPEN_SCRIPT, None)
        self._close_script_id: Optional[str] = self._opt_or_data(CONF_CLOSE_SCRIPT, None)
        self._stop_script_id: Optional[str] = self._opt_or_data(CONF_STOP_SCRIPT, None)

        self._send_stop_at_ends: bool = bool(self._opt_or_data(CONF_SEND_STOP_AT_ENDS, False))
        self._always_confident: bool = bool(self._opt_or_data(CONF_ALWAYS_CONFIDENT, False))
        self._smart_stop_midrange: bool = bool(self._opt_or_data(CONF_SMART_STOP, False))

        self._close_contact_sensor_id = self._opt_or_data(CONF_CLOSE_CONTACT_SENSOR, None)
        self._open_contact_sensor_id = self._opt_or_data(CONF_OPEN_CONTACT_SENSOR, None)

        self._single_control_enabled = bool(self._opt_or_data(CONF_SINGLE_CONTROL_ENABLED, False))
        if self._single_control_enabled:
            self._single_control_script_id = self._opt_or_data(CONF_OPEN_SCRIPT, None) or self._first_script()
        else:
            self._single_control_script_id = None
        self._single_pulse_delay_ms = int(self._opt_or_data(CONF_SINGLE_CONTROL_PULSE_MS, 400))

        if self._calc is None:
            self._calc = TravelCalculator(self._travel_down, self._travel_up)
        self._calc.travel_time_down = self._travel_down
        self._calc.travel_time_up = self._travel_up
        self._calc.set_position(float(self._position))

        _LOGGER.debug(
            "Applied settings: up=%s, down=%s, open=%s, close=%s, stop=%s, "
            "stop_at_ends=%s, confident=%s, midrange=%s, close_contact=%s, open_contact=%s, "
            "single=%s, single_rf_script=%s, single_delay_ms=%s",
            self._travel_up,
            self._travel_down,
            self._open_script_id,
            self._close_script_id,
            self._stop_script_id,
            self._send_stop_at_ends,
            self._always_confident,
            self._smart_stop_midrange,
            self._close_contact_sensor_id,
            self._open_contact_sensor_id,
            self._single_control_enabled,
            self._single_control_script_id,
            self._single_pulse_delay_ms,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and (pos := last_state.attributes.get("current_position")) is not None:
            try:
                self._position = int(pos)
                _LOGGER.debug("Restored position to %s%%", self._position)
            except (TypeError, ValueError):
                _LOGGER.debug("Invalid restored position: %s", pos)

        if self._calc is None:
            self._calc = TravelCalculator(self._travel_down, self._travel_up)
        self._calc.set_position(float(self._position))

        await self._set_next_action(NEXT_OPEN if self._position == 0 else (NEXT_CLOSE if self._position == 100 else NEXT_STOP))
        self.async_write_ha_state()

        self._unsub_known_position = async_dispatcher_connect(
            self.hass, SIGNAL_SET_KNOWN_POSITION, self._dispatcher_set_known_position
        )
        self._unsub_known_action = async_dispatcher_connect(
            self.hass, SIGNAL_SET_KNOWN_ACTION, self._dispatcher_set_known_action
        )
        self._unsub_activate_script = async_dispatcher_connect(
            self.hass, SIGNAL_ACTIVATE_SCRIPT, self._dispatcher_activate_script
        )

        # Sensores de contacto (opcionais) — estado inicial (invertido)
        if self._close_contact_sensor_id:
            self._unsub_close_contact = async_track_state_change_event(
                self.hass, [self._close_contact_sensor_id], self._closed_contact_state_changed
            )
            st = self.hass.states.get(self._close_contact_sensor_id)
            if st and str(st.state).lower() == "off":
                await self._apply_contact_hit(0, source_entity=self._close_contact_sensor_id)

        if self._open_contact_sensor_id:
            self._unsub_open_contact = async_track_state_change_event(
                self.hass, [self._open_contact_sensor_id], self._open_contact_state_changed
            )
            st = self.hass.states.get(self._open_contact_sensor_id)
            if st and str(st.state).lower() == "off":
                await self._apply_contact_hit(100, source_entity=self._open_contact_sensor_id)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_known_position:
            self._unsub_known_position(); self._unsub_known_position = None
        if self._unsub_known_action:
            self._unsub_known_action(); self._unsub_known_action = None
        if self._unsub_close_contact:
            self._unsub_close_contact(); self._unsub_close_contact = None
        if self._unsub_open_contact:
            self._unsub_open_contact(); self._unsub_open_contact = None
