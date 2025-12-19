"""Cover Time Based Sync - entidade cover compatível HA 2025.10+."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_TRAVELLING_TIME_UP,
    CONF_TRAVELLING_TIME_DOWN,
    CONF_OPEN_SCRIPT,
    CONF_CLOSE_SCRIPT,
    CONF_STOP_SCRIPT,
    CONF_SEND_STOP_AT_ENDS,
    CONF_ALWAYS_CONFIDENT,
    CONF_SMART_STOP,
)
from .travelcalculator import TravelCalculator, TravelStatus

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configura entidade(s) a partir de uma config entry."""
    # Junta dados iniciais com as opções mais recentes
    data: dict[str, Any] = {**entry.data, **entry.options}

    name = data.get(CONF_NAME, "Cover Time Based Sync")

    entity = CoverTimeBasedSyncCover(
        hass=hass,
        name=name,
        entry_id=entry.entry_id,
        cfg=data,
    )

    async_add_entities([entity])


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> None:
    """Configuração legacy via YAML (mantida para compatibilidade)."""
    devices_conf: dict[str, Any] = config.get("devices", {})
    entities: list[CoverTimeBasedSyncCover] = []

    for device_key, device_config in devices_conf.items():
        name = device_config.get(CONF_NAME, device_key)
        cfg = {
            CONF_TRAVELLING_TIME_UP: device_config.get(CONF_TRAVELLING_TIME_UP, 25),
            CONF_TRAVELLING_TIME_DOWN: device_config.get(CONF_TRAVELLING_TIME_DOWN, 25),
            CONF_OPEN_SCRIPT: device_config.get(CONF_OPEN_SCRIPT),
            CONF_CLOSE_SCRIPT: device_config.get(CONF_CLOSE_SCRIPT),
            CONF_STOP_SCRIPT: device_config.get(CONF_STOP_SCRIPT),
            CONF_SEND_STOP_AT_ENDS: device_config.get(CONF_SEND_STOP_AT_ENDS, False),
            CONF_ALWAYS_CONFIDENT: device_config.get(CONF_ALWAYS_CONFIDENT, False),
            CONF_SMART_STOP: device_config.get(CONF_SMART_STOP, False),
        }

        entities.append(
            CoverTimeBasedSyncCover(
                hass=hass,
                name=name,
                entry_id=device_key,
                cfg=cfg,
            )
        )

    if entities:
        async_add_entities(entities)


class CoverTimeBasedSyncCover(RestoreEntity, CoverEntity):
    """Entidade cover RF Time Based compatível HA 2025.10+."""

    has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        entry_id: str,
        cfg: dict[str, Any],
    ) -> None:
        self.hass = hass
        self._cfg = cfg

        # Opções
        self._send_stop_at_ends = bool(cfg.get(CONF_SEND_STOP_AT_ENDS, False))
        self._smart_stop = bool(cfg.get(CONF_SMART_STOP, False))
        self._always_confident = bool(cfg.get(CONF_ALWAYS_CONFIDENT, False))

        self._open_script = cfg.get(CONF_OPEN_SCRIPT)
        self._close_script = cfg.get(CONF_CLOSE_SCRIPT)
        self._stop_script = cfg.get(CONF_STOP_SCRIPT)

        travel_up = int(cfg.get(CONF_TRAVELLING_TIME_UP, 25))
        travel_down = int(cfg.get(CONF_TRAVELLING_TIME_DOWN, 25))
        self._travel = TravelCalculator(
            travel_time_down=travel_down,
            travel_time_up=travel_up,
        )

        self._position: int = 0
        self._status: TravelStatus = TravelStatus.STOPPED

        self._unsub_update = None

        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry_id}"
        self._attr_is_closed = True
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._attr_current_cover_position = self._position

    @property
    def supported_features(self) -> int:
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    @property
    def current_cover_position(self) -> int:
        return self._attr_current_cover_position

    async def async_added_to_hass(self) -> None:
        """Restaura estado se existir."""
        await super().async_added_to_hass()

        if last_state := await self.async_get_last_state():
            try:
                self._position = int(last_state.attributes.get(
                    "current_position", last_state.attributes.get("current_cover_position", 0)
                ))
            except (TypeError, ValueError):
                self._position = 0

        self._update_state_attributes()
        self.async_write_ha_state()

    # ----------------- Controlo de scripts -----------------

    async def _call_script(self, entity_id: str | None) -> None:
        if not entity_id:
            return
        await self.hass.services.async_call(
            "script",
            "turn_on",
            {"entity_id": entity_id},
            blocking=False,
        )

    # ----------------- Atualização periódica -----------------

    async def _async_start_timer(self) -> None:
        if self._unsub_update is not None:
            return

        async def _update_time(now):
            self._position = self._travel.current_position()
            self._update_state_attributes()
            self.async_write_ha_state()

            if self._travel._direction == TravelStatus.STOPPED:
                # Movimento terminou
                target_pos = self._position
                await self._async_on_travel_finished(target_pos)
                self._async_stop_timer()

        self._unsub_update = async_track_time_interval(
            self.hass, _update_time, UPDATE_INTERVAL
        )

    def _async_stop_timer(self) -> None:
        if self._unsub_update:
            self._unsub_update()
            self._unsub_update = None

    async def _async_on_travel_finished(self, target_pos: int) -> None:
        """Chamada quando o cálculo de tempo indica que terminou o movimento."""
        at_ends = target_pos in (0, 100)
        midrange = 20 <= target_pos <= 80

        should_send_stop = (
            (self._send_stop_at_ends and at_ends)
            or (self._smart_stop and midrange)
        )

        if should_send_stop:
            await self._call_script(self._stop_script)

        self._status = TravelStatus.STOPPED
        self._update_state_attributes()
        self.async_write_ha_state()

    # ----------------- Atualização de atributos -----------------

    def _update_state_attributes(self) -> None:
        """Atualiza atributos internos para HA."""
        self._attr_is_closed = self._position == 0
        self._attr_is_opening = self._status == TravelStatus.OPENING
        self._attr_is_closing = self._status == TravelStatus.CLOSING
        self._attr_current_cover_position = int(self._position)

    # ----------------- Serviços padrão Cover -----------------

    async def async_set_cover_position(self, **kwargs) -> None:
        """Implementa set_cover_position."""
        position = kwargs.get("position")
        if position is None:
            return

        target = max(0, min(100, int(position)))
        await self._async_move_to_target(target)

    async def async_open_cover(self, **kwargs) -> None:
        await self._async_move_to_target(100)

    async def async_close_cover(self, **kwargs) -> None:
        await self._async_move_to_target(0)

    async def async_stop_cover(self, **kwargs) -> None:
        """Stop explícito do utilizador: deve sempre enviar STOP."""
        self._travel.stop()
        self._status = TravelStatus.STOPPED
        self._async_stop_timer()
        await self._call_script(self._stop_script)
        self._position = self._travel.current_position()
        self._update_state_attributes()
        self.async_write_ha_state()

    # ----------------- Lógica interna de movimento -----------------

    async def _async_move_to_target(self, target: int) -> None:
        """Inicia movimento para um alvo concreto usando o TravelCalculator."""
        current = self._travel.current_position()

        if target == current and not self._always_confident:
            # Sem confiança total, atualiza para o alvo mesmo assim
            self._position = target
            self._update_state_attributes()
            self.async_write_ha_state()
            return

        if target > current:
            direction = TravelStatus.OPENING
            await self._call_script(self._open_script)
        elif target < current:
            direction = TravelStatus.CLOSING
            await self._call_script(self._close_script)
        else:
            # Já está na posição
            return

        self._status = direction
        self._travel.start_moving(direction, target)
        await self._async_start_timer()
        self._update_state_attributes()
        self.async_write_ha_state()
