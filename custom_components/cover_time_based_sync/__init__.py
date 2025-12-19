
"""Cover Time Based Sync integration."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import service as ha_service
from homeassistant.const import Platform

from .const import (
    DOMAIN,
    SERVICE_SET_KNOWN_POSITION,
    SERVICE_SET_KNOWN_ACTION,
    ATTR_POSITION,
    ATTR_CONFIDENT,
    ATTR_POSITION_TYPE,
    ATTR_POSITION_TYPE_TARGET,
    ATTR_ACTION,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.COVER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Setup via YAML (legacy) e registar serviços de domínio."""
    _LOGGER.debug("Integração %s inicializada via YAML", DOMAIN)

    # Schemas dos serviços (requerem entity_id para encaminhamento correto)
    position_schema = vol.Schema(
        {
            vol.Required("entity_id"): str,
            vol.Required(ATTR_POSITION): vol.All(int, vol.Range(min=0, max=100)),
            vol.Optional(ATTR_CONFIDENT, default=False): bool,
            vol.Optional(ATTR_POSITION_TYPE, default=ATTR_POSITION_TYPE_TARGET): str,
        }
    )

    action_schema = vol.Schema(
        {
            vol.Required("entity_id"): str,
            vol.Required(ATTR_ACTION): vol.In(["open", "close", "stop"]),
        }
    )

    @callback
    async def _handle_set_known_position(call: ServiceCall) -> None:
        await ha_service.entity_service_call(
            hass,
            [call.data.get("entity_id")],
            DOMAIN,
            SERVICE_SET_KNOWN_POSITION,
            call.data,
        )

    @callback
    async def _handle_set_known_action(call: ServiceCall) -> None:
        await ha_service.entity_service_call(
            hass,
            [call.data.get("entity_id")],
            DOMAIN,
            SERVICE_SET_KNOWN_ACTION,
            call.data,
        )

    # Registar serviços de domínio
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_KNOWN_POSITION,
        _handle_set_known_position,
        schema=position_schema,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_KNOWN_ACTION,
        _handle_set_known_action,
        schema=action_schema,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup a partir de config entry."""
    _LOGGER.debug("Config entry %s inicializada", entry.entry_id)

    # Encaminhar setup para plataformas e aguardar — método plural recomendado (2024+)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)  # ✅ novo
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok
