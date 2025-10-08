"""Cover RF Time Based integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import service as ha_service
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .cover import SERVICE_SET_KNOWN_POSITION, SERVICE_SET_KNOWN_ACTION

DOMAIN = "cover_rf_time_based"

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the cover_rf_time_based integration (config via YAML)."""

    # Registrar os serviços de entidade de forma global
    ha_service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_KNOWN_POSITION,
        entity_domain=COVER_DOMAIN,
        schema={
            vol.Required("position"): cv.positive_int,
            vol.Optional("confident", default=False): cv.boolean,
            vol.Optional("position_type", default="target"): cv.string,
        },
        func="set_known_position",
    )

    ha_service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_KNOWN_ACTION,
        entity_domain=COVER_DOMAIN,
        schema={
            vol.Required("action"): vol.In(["open", "close", "stop"]),
        },
        func="set_known_action",
    )

    return True
