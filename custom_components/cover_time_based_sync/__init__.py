"""Cover Time Based Sync integration — encaminha config entries para a plataforma 'cover'
e regista serviços de domínio para atualização de posição/ação e ativação de script."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    SERVICE_SET_KNOWN_POSITION,
    SERVICE_SET_KNOWN_ACTION,
    SERVICE_ACTIVATE_SCRIPT,
    ATTR_POSITION,
    ATTR_CONFIDENT,
    ATTR_POSITION_TYPE,
    ATTR_ACTION,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Setup global (YAML legacy). Regista serviços de domínio."""
    _LOGGER.debug("Integração '%s' inicializada.", DOMAIN)

    # Sinais para dispatcher
    SIGNAL_SET_KNOWN_POSITION = f"{DOMAIN}_set_known_position"
    SIGNAL_SET_KNOWN_ACTION = f"{DOMAIN}_set_known_action"
    SIGNAL_ACTIVATE_SCRIPT = f"{DOMAIN}_activate_script"

    @callback
    def _handle_set_known_position(call: ServiceCall) -> None:
        position: Any = call.data.get(ATTR_POSITION)
        confident: bool = bool(call.data.get(ATTR_CONFIDENT, False))
        pos_type: str = str(call.data.get(ATTR_POSITION_TYPE, "target"))
        target_entities = call.data.get("entity_id")

        _LOGGER.debug(
            "[%s] set_known_position: entity_id=%s, position=%s, confident=%s, type=%s",
            DOMAIN, target_entities, position, confident, pos_type
        )
        try:
            from homeassistant.helpers.dispatcher import async_dispatcher_send
            async_dispatcher_send(
                hass, SIGNAL_SET_KNOWN_POSITION, target_entities, position, confident, pos_type
            )
        except Exception as exc:
            _LOGGER.debug("Dispatcher não disponível ou erro ao enviar sinal: %s", exc)

    @callback
    def _handle_set_known_action(call: ServiceCall) -> None:
        action: str = str(call.data.get(ATTR_ACTION))
        target_entities = call.data.get("entity_id")
        _LOGGER.debug("[%s] set_known_action: entity_id=%s, action=%s", DOMAIN, target_entities, action)
        try:
            from homeassistant.helpers.dispatcher import async_dispatcher_send
            async_dispatcher_send(hass, SIGNAL_SET_KNOWN_ACTION, target_entities, action)
        except Exception as exc:
            _LOGGER.debug("Dispatcher não disponível ou erro ao enviar sinal: %s", exc)

    @callback
    def _handle_activate_script(call: ServiceCall) -> None:
        """Ativa o(s) script(s) e sincroniza a próxima ação com movimento simulado/paragem."""
        action: str | None = call.data.get(ATTR_ACTION)  # opcional (obrigatório no modo standard)
        target_entities = call.data.get("entity_id")
        _LOGGER.debug("[%s] activate_script: entity_id=%s, action=%s", DOMAIN, target_entities, action)
        try:
            from homeassistant.helpers.dispatcher import async_dispatcher_send
            async_dispatcher_send(hass, SIGNAL_ACTIVATE_SCRIPT, target_entities, action)
        except Exception as exc:
            _LOGGER.debug("Dispatcher não disponível ou erro ao enviar sinal: %s", exc)

    hass.services.async_register(DOMAIN, SERVICE_SET_KNOWN_POSITION, _handle_set_known_position)
    hass.services.async_register(DOMAIN, SERVICE_SET_KNOWN_ACTION, _handle_set_known_action)
    hass.services.async_register(DOMAIN, SERVICE_ACTIVATE_SCRIPT, _handle_activate_script)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
