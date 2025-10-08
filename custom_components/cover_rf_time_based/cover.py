"""Cover Time based, RF version (updated for HA >= 2025.10)."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    PLATFORM_SCHEMA,
    DEVICE_CLASSES_SCHEMA,
    CoverEntity,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_DEVICE_CLASS,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.exceptions import HomeAssistantError

from .travelcalculator import TravelCalculator
from .travelcalculator import TravelStatus

_LOGGER = logging.getLogger(__name__)

CONF_DEVICES = "devices"
CONF_ALIASES = "aliases"
CONF_TRAVELLING_TIME_DOWN = "travelling_time_down"
CONF_TRAVELLING_TIME_UP = "travelling_time_up"
CONF_SEND_STOP_AT_ENDS = "send_stop_at_ends"
CONF_ALWAYS_CONFIDENT = "always_confident"
DEFAULT_TRAVEL_TIME = 25
DEFAULT_SEND_STOP_AT_ENDS = False
DEFAULT_ALWAYS_CONFIDENT = False
DEFAULT_DEVICE_CLASS = "shutter"

CONF_OPEN_SCRIPT_ENTITY_ID = "open_script_entity_id"
CONF_CLOSE_SCRIPT_ENTITY_ID = "close_script_entity_id"
CONF_STOP_SCRIPT_ENTITY_ID = "stop_script_entity_id"
CONF_COVER_ENTITY_ID = "cover_entity_id"
CONF_AVAILABILITY_TPL = "availability_template"
ATTR_CONFIDENT = "confident"
ATTR_ACTION = "action"
ATTR_POSITION_TYPE = "position_type"
ATTR_POSITION_TYPE_CURRENT = "current"
ATTR_POSITION_TYPE_TARGET = "target"
ATTR_UNCONFIRMED_STATE = "unconfirmed_state"
SERVICE_SET_KNOWN_POSITION = "set_known_position"
SERVICE_SET_KNOWN_ACTION = "set_known_action"

BASE_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_ALIASES, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME): cv.positive_int,
        vol.Optional(CONF_TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME): cv.positive_int,
        vol.Optional(CONF_SEND_STOP_AT_ENDS, default=DEFAULT_SEND_STOP_AT_ENDS): cv.boolean,
        vol.Optional(CONF_ALWAYS_CONFIDENT, default=DEFAULT_ALWAYS_CONFIDENT): cv.boolean,
        vol.Optional(CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_AVAILABILITY_TPL): cv.template,
    }
)

SCRIPT_DEVICE_SCHEMA = BASE_DEVICE_SCHEMA.extend(
    {
        vol.Required(CONF_OPEN_SCRIPT_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_CLOSE_SCRIPT_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_STOP_SCRIPT_ENTITY_ID): cv.entity_id,
    }
)

COVER_DEVICE_SCHEMA = BASE_DEVICE_SCHEMA.extend(
    {
        vol.Required(CONF_COVER_ENTITY_ID): cv.entity_id,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): vol.Schema(
            {
                cv.string: vol.Any(SCRIPT_DEVICE_SCHEMA, COVER_DEVICE_SCHEMA)
            }
        ),
    }
)

POSITION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_POSITION): cv.positive_int,
        vol.Optional(ATTR_CONFIDENT, default=False): cv.boolean,
        vol.Optional(ATTR_POSITION_TYPE, default=ATTR_POSITION_TYPE_TARGET): cv.string,
    }
)

ACTION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_ACTION): cv.string,
    }
)

DOMAIN = "cover_rf_time_based"


def devices_from_config(domain_config: dict):
    """Parse configuration and add cover devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        name = config.pop(CONF_NAME)
        travel_time_down = config.pop(CONF_TRAVELLING_TIME_DOWN)
        travel_time_up = config.pop(CONF_TRAVELLING_TIME_UP)
        open_script_entity_id = config.pop(CONF_OPEN_SCRIPT_ENTITY_ID, None)
        close_script_entity_id = config.pop(CONF_CLOSE_SCRIPT_ENTITY_ID, None)
        stop_script_entity_id = config.pop(CONF_STOP_SCRIPT_ENTITY_ID, None)
        cover_entity_id = config.pop(CONF_COVER_ENTITY_ID, None)
        send_stop_at_ends = config.pop(CONF_SEND_STOP_AT_ENDS)
        always_confident = config.pop(CONF_ALWAYS_CONFIDENT)
        device_class = config.pop(CONF_DEVICE_CLASS)
        availability_template = config.pop(CONF_AVAILABILITY_TPL, None)
        device = CoverTimeBased(
            device_id,
            name,
            travel_time_down,
            travel_time_up,
            open_script_entity_id,
            close_script_entity_id,
            stop_script_entity_id,
            cover_entity_id,
            send_stop_at_ends,
            always_confident,
            device_class,
            availability_template,
        )
        devices.append(device)
    return devices


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the cover platform."""
    _LOGGER.debug("cover_rf_time_based: async_setup_platform")
    async_add_entities(devices_from_config(config))

    # Use modern API to register entity services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_KNOWN_POSITION, POSITION_SCHEMA, "set_known_position"
    )
    platform.async_register_entity_service(
        SERVICE_SET_KNOWN_ACTION, ACTION_SCHEMA, "set_known_action"
    )


class CoverTimeBased(CoverEntity, RestoreEntity):
    def __init__(
        self,
        device_id: str,
        name: str,
        travel_time_down: int,
        travel_time_up: int,
        open_script_entity_id: str | None,
        close_script_entity_id: str | None,
        stop_script_entity_id: str | None,
        cover_entity_id: str | None,
        send_stop_at_ends: bool = False,
        always_confident: bool = False,
        device_class: str | None = None,
        availability_template=None,
    ) -> None:
        """Initialize the cover."""
        self._travel_time_down = travel_time_down
        self._travel_time_up = travel_time_up
        self._open_script_entity_id = open_script_entity_id
        self._close_script_entity_id = close_script_entity_id
        self._stop_script_entity_id = stop_script_entity_id
        self._cover_entity_id = cover_entity_id
        self._send_stop_at_ends = send_stop_at_ends
        self._always_confident = always_confident
        self._device_class = device_class
        self._assume_uncertain_position = not self._always_confident
        self._target_position = 0
        self._processing_known_position = False
        self._unique_id = device_id
        self._availability_template = availability_template

        self._name = name or device_id

        self._unsubscribe_auto_updater = None

        self.tc = TravelCalculator(self._travel_time_down, self._travel_time_up)

        # internal state used for HA attributes
        self._state = None

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass (restore state)."""
        await super().async_added_to_hass()
        old_state = await self.async_get_last_state()
        _LOGGER.debug("%s: async_added_to_hass :: oldState %s", self._name, old_state)
        if old_state is not None and self.tc is not None and old_state.attributes.get(
            ATTR_CURRENT_POSITION
        ) is not None:
            try:
                pos = int(old_state.attributes.get(ATTR_CURRENT_POSITION))
                self.tc.set_position(pos)
            except (ValueError, TypeError):
                _LOGGER.exception("Failed to restore position for %s", self._name)

        if old_state is not None and old_state.attributes.get(ATTR_UNCONFIRMED_STATE) is not None and not self._always_confident:
            value = old_state.attributes.get(ATTR_UNCONFIRMED_STATE)
            if isinstance(value, bool):
                self._assume_uncertain_position = value
            else:
                self._assume_uncertain_position = str(value).lower() in ("true", "1", "yes")

    def _handle_stop(self) -> None:
        """Handle stop button press"""
        if self.tc.is_traveling():
            _LOGGER.debug("%s: _handle_stop :: button stops cover", self._name)
            self.tc.stop()
            self.stop_auto_updater()

    @property
    def unconfirmed_state(self) -> str:
        """Return the assume state as a string to persist through restarts."""
        return str(self._assume_uncertain_position)

    @property
    def available(self) -> bool:
        """Return availability based on external template. Always available if no template specified."""
        if self._availability_template is None:
            return True
        try:
            # template.async_render() may return string; convert sensibly to bool
            self._availability_template.hass = self.hass
            rendered = self._availability_template.async_render()
            # treat common falsey strings as False
            if isinstance(rendered, str):
                return rendered.lower() not in ("false", "0", "none", "")
            return bool(rendered)
        except Exception:  # pragma: no cover - template errors should not break entity
            _LOGGER.exception("Error rendering availability template for %s", self._name)
            return True

    @property
    def name(self) -> str:
        """Return the name of the cover."""
        return self._name

    @property
    def unique_id(self) -> str | None:
        """Return the unique id."""
        return "cover_rf_timebased_" + self._unique_id

    @property
    def device_class(self) -> str | None:
        """Return the device class of the cover."""
        return self._device_class

    @property
    def extra_state_attributes(self) -> dict:
        """Return the device state attributes."""
        attr: dict[str, Any] = {}
        if self._travel_time_down is not None:
            attr[CONF_TRAVELLING_TIME_DOWN] = self._travel_time_down
        if self._travel_time_up is not None:
            attr[CONF_TRAVELLING_TIME_UP] = self._travel_time_up
        attr[ATTR_UNCONFIRMED_STATE] = str(self._assume_uncertain_position)
        return attr

    @property
    def current_cover_position(self) -> int:
        """Return the current position of the cover (0..100)."""
        return self.tc.current_position()

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self.tc.is_traveling() and self.tc.travel_direction == TravelStatus.DIRECTION_UP

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self.tc.is_traveling() and self.tc.travel_direction == TravelStatus.DIRECTION_DOWN

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return self.tc.is_closed()

    @property
    def assumed_state(self) -> bool:
        """Return True unless we have set position with confidence through set_known_position service."""
        return self._assume_uncertain_position

    async def async_set_cover_position(self, **kwargs) -> None:
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            self._target_position = int(kwargs[ATTR_POSITION])
            _LOGGER.debug("%s: async_set_cover_position -> %d", self._name, self._target_position)
            await self.set_position(self._target_position)

    async def async_close_cover(self, **kwargs) -> None:
        """Close the cover."""
        _LOGGER.debug("%s: async_close_cover", self._name)
        self.tc.start_travel_down()
        self._target_position = 0
        self.start_auto_updater()
        await self._async_handle_command(SERVICE_CLOSE_COVER)

    async def async_open_cover(self, **kwargs) -> None:
        """Open the cover."""
        _LOGGER.debug("%s: async_open_cover", self._name)
        self.tc.start_travel_up()
        self._target_position = 100
        self.start_auto_updater()
        await self._async_handle_command(SERVICE_OPEN_COVER)

    async def async_stop_cover(self, **kwargs) -> None:
        """Stop the cover."""
        _LOGGER.debug("%s: async_stop_cover", self._name)
        self._handle_stop()
        await self._async_handle_command(SERVICE_STOP_COVER)

    async def set_position(self, position: int) -> None:
        """Move cover to a designated position (0..100)."""
        _LOGGER.debug("%s: set_position requested -> %d", self._name, position)
        current_position = self.tc.current_position()
        _LOGGER.debug(
            "%s: set_position :: current_position: %d, new_position: %d",
            self._name,
            current_position,
            position,
        )
        command = None
        if position < current_position:
            command = SERVICE_CLOSE_COVER
        elif position > current_position:
            command = SERVICE_OPEN_COVER

        if command is not None:
            self.start_auto_updater()
            self.tc.start_travel(position)
            _LOGGER.debug("%s: set_position :: command %s", self._name, command)
            await self._async_handle_command(command)

    def start_auto_updater(self) -> None:
        """Start the autoupdater to update HASS while cover is moving."""
        _LOGGER.debug("%s: start_auto_updater", self._name)
        if self._unsubscribe_auto_updater is None:
            interval = timedelta(seconds=0.1)
            self._unsubscribe_auto_updater = async_track_time_interval(
                self.hass, self.auto_updater_hook, interval
            )

    @callback
    def auto_updater_hook(self, now) -> None:
        """Call for the autoupdater (scheduled)."""
        _LOGGER.debug("%s: auto_updater_hook", self._name)
        # This schedules an update of HA state
        self.async_schedule_update_ha_state()
        if self.position_reached():
            _LOGGER.debug("%s: auto_updater_hook :: position_reached", self._name)
            self.stop_auto_updater()
        # create a task for any extra async processing
        self.hass.async_create_task(self.auto_stop_if_necessary())

    def stop_auto_updater(self) -> None:
        """Stop the autoupdater."""
        _LOGGER.debug("%s: stop_auto_updater", self._name)
        if self._unsubscribe_auto_updater is not None:
            try:
                self._unsubscribe_auto_updater()
            finally:
                self._unsubscribe_auto_updater = None

    def position_reached(self) -> bool:
        """Return if cover has reached its final position."""
        return self.tc.position_reached()

    async def set_known_action(self, **kwargs) -> None:
        """Entity service to indicate a known action (open/close/stop)."""
        action = kwargs.get(ATTR_ACTION)
        if action not in ("open", "close", "stop"):
            raise HomeAssistantError("action must be one of open, close or stop")
        if action == "stop":
            self._handle_stop()
            return
        if action == "open":
            self.tc.start_travel_up()
            self._target_position = 100
        if action == "close":
            self.tc.start_travel_down()
            self._target_position = 0
        self.start_auto_updater()

    async def set_known_position(self, **kwargs) -> None:
        """Entity service to inform the entity of a known position."""
        position = int(kwargs[ATTR_POSITION])
        confident = kwargs.get(ATTR_CONFIDENT, False)
        position_type = kwargs.get(ATTR_POSITION_TYPE, ATTR_POSITION_TYPE_TARGET)
        if position_type not in (ATTR_POSITION_TYPE_TARGET, ATTR_POSITION_TYPE_CURRENT):
            raise HomeAssistantError(f"{ATTR_POSITION_TYPE} must be one of {ATTR_POSITION_TYPE_TARGET}, {ATTR_POSITION_TYPE_CURRENT}")

        _LOGGER.debug(
            "%s: set_known_position :: position %d, confident %s, position_type %s, tc.is_traveling=%s",
            self._name,
            position,
            str(confident),
            position_type,
            str(self.tc.is_traveling()),
        )

        self._assume_uncertain_position = not confident if not self._always_confident else False
        self._processing_known_position = True

        if position_type == ATTR_POSITION_TYPE_TARGET:
            # treat provided number as target, and ask current position from travel calculator
            self._target_position = position
            position = self.current_cover_position

        if self.tc.is_traveling():
            # update known position and continue travel toward target
            self.tc.set_position(position)
            self.tc.start_travel(self._target_position)
            self.start_auto_updater()
        else:
            if position_type == ATTR_POSITION_TYPE_TARGET:
                self.tc.start_travel(self._target_position)
                self.start_auto_updater()
            else:
                _LOGGER.debug(
                    "%s: set_known_position :: non_traveling position %d, confident %s, position_type %s",
                    self._name,
                    position,
                    str(confident),
                    position_type,
                )
                self.tc.set_position(position)

    async def auto_stop_if_necessary(self) -> None:
        """Do auto stop if necessary."""
        current_position = self.tc.current_position()
        if self.position_reached() and not self._processing_known_position:
            self.tc.stop()
            # between ends -> send stop command to hardware (so motor stops)
            if 0 < current_position < 100:
                _LOGGER.debug(
                    "%s: auto_stop_if_necessary :: current_position between 1 and 99 :: calling stop command",
                    self._name,
                )
                await self._async_handle_command(SERVICE_STOP_COVER)
            else:
                if self._send_stop_at_ends:
                    _LOGGER.debug("%s: auto_stop_if_necessary :: send_stop_at_ends :: calling stop command", self._name)
                    await self._async_handle_command(SERVICE_STOP_COVER)

    async def _async_handle_command(self, command: str, *args) -> None:
        """We have cover.* triggered command. Reset assumed state and known_position processing and execute."""
        self._assume_uncertain_position = not self._always_confident
        self._processing_known_position = False
        cmd = "UNKNOWN"
        if command == SERVICE_CLOSE_COVER:
            cmd = "DOWN"
            self._state = False
            if self._cover_entity_id is not None:
                await self.hass.services.async_call("cover", "close_cover", {"entity_id": self._cover_entity_id}, False)
            else:
                await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._close_script_entity_id}, False)

        elif command == SERVICE_OPEN_COVER:
            cmd = "UP"
            self._state = True
            if self._cover_entity_id is not None:
                await self.hass.services.async_call("cover", "open_cover", {"entity_id": self._cover_entity_id}, False)
            else:
                await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._open_script_entity_id}, False)

        elif command == SERVICE_STOP_COVER:
            cmd = "STOP"
            # do not assume True/False for state; keep internal state logic consistent
            if self._cover_entity_id is not None:
                await self.hass.services.async_call("cover", "stop_cover", {"entity_id": self._cover_entity_id}, False)
            else:
                await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._stop_script_entity_id}, False)

        _LOGGER.debug("%s: _async_handle_command :: %s", self._name, cmd)

        # Update state of entity in HA
        self.async_write_ha_state()
