"""Cover Time Based Sync - entidade cover compatível HA 2025.10+."""

import logging

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SERVICE_SET_KNOWN_POSITION,
    SERVICE_SET_KNOWN_ACTION,
    ATTR_POSITION,
    ATTR_CONFIDENT,
    ATTR_POSITION_TYPE,
    ATTR_POSITION_TYPE_TARGET,
    ATTR_POSITION_TYPE_CURRENT,
    ATTR_ACTION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configura entidade(s) a partir de uma config entry."""

    data = entry.data
    name = data.get("name", "Cover Time Based Sync")

    entity = CoverRFTimeBasedSync(
        name=name,
        entry_id=entry.entry_id,
    )

    async_add_entities([entity])


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Configuração legacy via YAML (não recomendado, mas mantido)."""
    devices_conf = config.get("devices", {})

    entities = []
    for device_key, device_config in devices_conf.items():
        name = device_config.get("name", device_key)
        entities.append(
            CoverRFTimeBasedSync(
                name=name,
                entry_id=device_key,
            )
        )

    async_add_entities(entities)


class CoverRFTimeBasedSync(RestoreEntity, CoverEntity):
    """Entidade cover RF Time Based compatível HA 2025.10+."""

    has_entity_name = True

    def __init__(self, name: str, entry_id: str) -> None:
        self._position = 0
        self._status = "stopped"

        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry_id}"
        self._attr_is_closed = True
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._attr_current_cover_position = self._position

    @property
    def supported_features(self) -> int:
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    @property
    def current_cover_position(self) -> int:
        return self._attr_current_cover_position

    def _update_state_attributes(self) -> None:
        """Atualiza atributos internos para HA."""
        self._attr_is_closed = self._position == 0
        self._attr_is_opening = self._status == "open"
        self._attr_is_closing = self._status == "close"
        self._attr_current_cover_position = self._position

    async def async_set_cover_position(self, **kwargs) -> None:
        """Implementa o set_cover_position padrão."""
        position = kwargs.get("position")
        if position is None:
            return
        await self.async_set_known_position(position=position)

    async def async_open_cover(self, **kwargs) -> None:
        await self.async_set_known_action(action="open")

    async def async_close_cover(self, **kwargs) -> None:
        await self.async_set_known_action(action="close")

    async def async_stop_cover(self, **kwargs) -> None:
        await self.async_set_known_action(action="stop")

    async def async_set_known_position(self, **kwargs) -> None:
        """Service: set_known_position."""
        self._position = kwargs.get(ATTR_POSITION, self._position)
        self._update_state_attributes()
        self.async_write_ha_state()

    async def async_set_known_action(self, **kwargs) -> None:
        """Service: set_known_action."""
        action = kwargs.get(ATTR_ACTION)
        if action in ["open", "close", "stop"]:
            self._status = action
            self._update_state_attributes()
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Ação desconhecida recebida: %s", action)        SERVICE_SET_KNOWN_POSITION,
        handle_set_known_position,
    )
    hass.services.async_register(
        "cover_rf_time_based",
        SERVICE_SET_KNOWN_ACTION,
        handle_set_known_action,
    )
    
    platform = entity_platform.async_get_current_platform()
    
    platform.async_register_entity_service(
        SERVICE_SET_KNOWN_POSITION,
        {
            vol.Required(ATTR_POSITION): cv.positive_int,
            vol.Optional(ATTR_CONFIDENT, default=False): cv.boolean,
            vol.Optional(ATTR_POSITION_TYPE, default=ATTR_POSITION_TYPE_TARGET): cv.string,
        },
        "set_known_position",
    )
    
    platform.async_register_entity_service(
        SERVICE_SET_KNOWN_ACTION,
        {
            vol.Required(ATTR_ACTION): vol.In(["open", "close", "stop"]),
        },
        "set_known_action",
    )

class CoverRFTimeBased(RestoreEntity, CoverEntity):
    """Entidade de cover RF Time Based compatível HA 2025.10+."""

    has_entity_name = True

    def __init__(self, name, unique_id):
        self._position = 0
        self._status = "stopped"

        # Atributos recomendados pelo HA 2025.10+
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{unique_id}"
        self._attr_is_closed = self._position == 0
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._attr_current_cover_position = self._position

    @property
    def supported_features(self):
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    @property
    def current_cover_position(self):
        return self._attr_current_cover_position

    def _update_state_attributes(self):
        """Atualiza os atributos internos _attr_* para HA 2025.10+."""
        self._attr_is_closed = self._position == 0
        self._attr_is_opening = self._status == "open"
        self._attr_is_closing = self._status == "close"
        self._attr_current_cover_position = self._position

    async def set_known_position(self, **kwargs):
        """Define a posição conhecida da cover."""
        self._position = kwargs.get(ATTR_POSITION, self._position)
        self._update_state_attributes()
        self.async_write_ha_state()

    async def set_known_action(self, **kwargs):
        """Define a ação conhecida da cover (open, close, stop)."""
        action = kwargs.get(ATTR_ACTION)
        if action in ["open", "close", "stop"]:
            self._status = action
            self._update_state_attributes()
            self.async_write_ha_state()
        else:
            _LOGGER.warning(f"Ação desconhecida recebida: {action}")
