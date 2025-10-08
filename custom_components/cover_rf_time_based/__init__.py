"""Cover RF Time Based integration (minimal __init__)."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DOMAIN = "cover_rf_time_based"

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the cover_rf_time_based integration (YAML platform handled by cover.py)."""
    _LOGGER.debug("cover_rf_time_based: async_setup called")
    # Nothing special to do here for platform-based integration.
    return True
