import logging
import voluptuous as vol
from homeassistant.helpers import entity_platform
from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.helpers.restore_state import RestoreEntity
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

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Configuração da plataforma cover_rf_time_based via YAML."""
    devices_conf = config.get("devices", {})

    devices = []
    for device_key, device_config in devices_conf.items():
        name = device_config.get("name", device_key)
        # ... outros parâmetros omitidos para brevidade
        device = CoverRFTimeBased(name=name, unique_id=device_key)
        devices.append(device)

    async_add_entities(devices)

    platform = entity_platform.current_platform.get()

    # Registo dos entity services usando target
    await platform.async_register_entity_service(
        SERVICE_SET_KNOWN_POSITION,
        {
            vol.Required(ATTR_POSITION): vol.All(vol.Coerce(int)),
            vol.Optional(ATTR_CONFIDENT, default=False): vol.Boolean(),
            vol.Optional(ATTR_POSITION_TYPE, default=ATTR_POSITION_TYPE_TARGET): vol.In([ATTR_POSITION_TYPE_TARGET, ATTR_POSITION_TYPE_CURRENT])
        },
        "set_known_position"
    )

    await platform.async_register_entity_service(
        SERVICE_SET_KNOWN_ACTION,
        {
            vol.Required(ATTR_ACTION): vol.In(["open", "close", "stop"])
        },
        "set_known_action"
    )

class CoverRFTimeBased(RestoreEntity, CoverEntity):
    """Entidade de cover RF Time Based."""

    def __init__(self, name, unique_id=None):
        self._name = name
        self._unique_id = unique_id
        self._position = 0
        self._status = "stopped"

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def current_cover_position(self):
        return self._position

    @property
    def supported_features(self):
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    async def set_known_position(self, **kwargs):
        self._position = kwargs.get(ATTR_POSITION)
        self.async_write_ha_state()

    async def set_known_action(self, **kwargs):
        action = kwargs.get(ATTR_ACTION)
        if action in ["open", "close", "stop"]:
            self._status = action
            self.async_write_ha_state()
