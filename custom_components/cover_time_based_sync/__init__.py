"""Cover Time Based Sync integration — encaminha config entries para a plataforma 'cover'
e regista serviços de domínio para atualização de posição/ação."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    # Serviços e atributos (definidos em const.py)
    SERVICE_SET_KNOWN_POSITION,
    SERVICE_SET_KNOWN_ACTION,
    ATTR_POSITION,
    ATTR_CONFIDENT,
    ATTR_POSITION_TYPE,
    ATTR_ACTION,
)

_LOGGER = logging.getLogger(__name__)

# Lista de plataformas suportadas por esta integração
PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Setup global (YAML legacy). Regista serviços de domínio."""
    _LOGGER.debug("Integração '%s' inicializada.", DOMAIN)

    # Dispatcher signals (opcional): nomes de sinais para comunicar com a plataforma/entidade
    # Se usares dispatcher no cover.py, importa e usa estes nomes lá.
    SIGNAL_SET_KNOWN_POSITION = f"{DOMAIN}_set_known_position"
    SIGNAL_SET_KNOWN_ACTION = f"{DOMAIN}_set_known_action"

    @callback
    def _handle_set_known_position(call: ServiceCall) -> None:
        """Handler para cover_time_based_sync.set_known_position."""
        # Campos do schema (services.yaml)
        position: Any = call.data.get(ATTR_POSITION)
        confident: bool = bool(call.data.get(ATTR_CONFIDENT, False))
        pos_type: str = str(call.data.get(ATTR_POSITION_TYPE, "target"))

        # entity_id(s) alvo
        target_entities = call.data.get("entity_id")
        _LOGGER.debug(
            "[%s] set_known_position: entity_id=%s, position=%s, confident=%s, type=%s",
            DOMAIN, target_entities, position, confident, pos_type
        )

        # (Opcional, recomendado) enviar para as entidades via dispatcher
        # from homeassistant.helpers.dispatcher import async_dispatcher_send
        try:
            from homeassistant.helpers.dispatcher import async_dispatcher_send
            async_dispatcher_send(
                hass,
                SIGNAL_SET_KNOWN_POSITION,
                target_entities,
                position,
                confident,
                pos_type,
            )
        except Exception as exc:
            _LOGGER.debug("Dispatcher não disponível ou erro ao enviar sinal: %s", exc)

    @callback
    def _handle_set_known_action(call: ServiceCall) -> None:
        """Handler para cover_time_based_sync.set_known_action."""
        action: str = str(call.data.get(ATTR_ACTION))
        target_entities = call.data.get("entity_id")
        _LOGGER.debug(
            "[%s] set_known_action: entity_id=%s, action=%s",
            DOMAIN, target_entities, action
        )

        # (Opcional, recomendado) enviar para as entidades via dispatcher
        try:
            from homeassistant.helpers.dispatcher import async_dispatcher_send
            async_dispatcher_send(
                hass,
                SIGNAL_SET_KNOWN_ACTION,
                target_entities,
                action,
            )
        except Exception as exc:
            _LOGGER.debug("Dispatcher não disponível ou erro ao enviar sinal: %s", exc)

    # Registo dos serviços (ficam visíveis e editáveis na UI graças ao services.yaml)
    hass.services.async_register(DOMAIN, SERVICE_SET_KNOWN_POSITION, _handle_set_known_position)
    hass.services.async_register(DOMAIN, SERVICE_SET_KNOWN_ACTION, _handle_set_known_action)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup a partir de uma Config Entry, encaminhando para as plataformas."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload da Config Entry (remove entidades e listeners)."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
