"""Cover RF Time Based integration - versão compatível HA 2025.10+."""

import logging
import voluptuous as vol
from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.helpers.restore_state import RestoreEntity
from . import DOMAIN
from homeassistant.helpers import service as ha_service
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from .const import (
    SERVICE_SET_KNOWN_POSITION,
    SERVICE_SET_KNOWN_ACTION,
    ATTR_POSITION,
    ATTR_CONFIDENT,
    ATTR_POSITION_TYPE,
    ATTR_ACTION,
    ATTR_POSITION_TYPE_TARGET,
    ATTR_POSITION_TYPE_CURRENT,
)
import homeassistant.helpers.config_validation as cv
_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Configuração da plataforma cover_rf_time_based via YAML."""
    devices_conf = config.get("devices", {})
    
    devices = []
    for device_key, device_config in devices_conf.items():
        name = device_config.get("name", device_key)
        device = CoverRFTimeBased(name=name, unique_id=device_key)
        devices.append(device)

    async_add_entities(devices)

    hass.services.async_register(
        "cover_rf_time_based",
        SERVICE_SET_KNOWN_POSITION,
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
