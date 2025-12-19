"""Cover Time Based Sync integration — encaminha config entries para a plataforma 'cover'."""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN  # garante que tens o ficheiro const.py com DOMAIN definido

_LOGGER = logging.getLogger(__name__)

# Lista de plataformas suportadas por esta integração
PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Setup global (YAML legacy). Mantemos simples — sem registrar nada aqui."""
    _LOGGER.debug("Integração '%s' inicializada.", DOMAIN)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup a partir de uma Config Entry, encaminhando para as plataformas."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload da Config Entry (remove entidades e listeners)."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
