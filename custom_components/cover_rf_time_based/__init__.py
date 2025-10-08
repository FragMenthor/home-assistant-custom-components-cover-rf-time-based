"""Cover RF Time Based integration."""

import logging
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Inicializa a integração cover_rf_time_based."""
    _LOGGER.debug("Integração cover_rf_time_based inicializada")
    return True
