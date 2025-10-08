"""Cover RF Time Based integration."""

from homeassistant.core import HomeAssistant
from .const import DOMAIN, SERVICE_SET_KNOWN_POSITION, SERVICE_SET_KNOWN_ACTION
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up cover_rf_time_based (config via YAML)."""
    _LOGGER.debug("Integração cover_rf_time_based inicializada.")
    return True
