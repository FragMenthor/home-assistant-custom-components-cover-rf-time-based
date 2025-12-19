
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Final

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import STATE_OPEN, STATE_CLOSED

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
    CONF_ALIASES,
)
from .travelcalculator import TravelCalculator, TravelStatus

_LOGGER = logging.getLogger(__name__)

# Atualização de posição / verificação de alvo a cada 1s
TICK: Final = timedelta(seconds=1)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Cria entidade a partir da config entry."""
    async_add_entities([TimeBasedSyncCover(hass, entry)])


class TimeBasedSyncCover(CoverEntity, RestoreEntity):
    """Cover baseada em tempo com scripts de abrir/fechar/stop."""

    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._unsub_tick = None

        self._name = self._get_opt(CONF_NAME) or "Time Based Cover"
        self._aliases: list[str] = self._normalize_aliases(self._get_opt(CONF_ALIASES))

        # Carrega tempos e flags
        t_up = int(self._get_opt(CONF_TRAVELLING_TIME_UP) or 25)
        t_down = int(self._get_opt(CONF_TRAVELLING_TIME_DOWN) or 25)
        self._calc = TravelCalculator(travel_time_down=t_down, travel_time_up=t_up)

        self._open_script = self._get_opt(CONF_OPEN_SCRIPT)
        self._close_script = self._get_opt(CONF_CLOSE_SCRIPT)
        self._stop_script = self._get_opt(CONF_STOP_SCRIPT)

        self._send_stop_at_ends = bool(self._get_opt(CONF_SEND_STOP_AT_ENDS) or False)
        self._always_confident = bool(self._get_opt(CONF_ALWAYS_CONFIDENT) or False)
        self._smart_stop_midrange = bool(self._get_opt(CONF_SMART_STOP) or False)

        self._attr_name = self._name
        self._attr_unique_id = f"{DOMAIN}:{entry.entry_id}"

        # Suporte nativo a abrir/fechar/stop/posição
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    # ---------------- Lifecycle ----------------

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Restaura estado (se existir)
        last_state = await self.async_get_last_state()
        if last_state and (cp := last_state.attributes.get("current_position")) is not None:
            try:
                self._calc.set_position(float(cp))
            except Exception:  # defensivo
                _LOGGER.debug("Falha a restaurar posição: %s", cp)

        # Agenda *tick* periódico
        self._unsub_tick = async_track_time_interval(
            self.hass, self._async_on_tick, TICK
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_tick:
            self._unsub_tick()
            self._unsub_tick = None

    # ---------------- Helpers de config ----------------

    def _get_opt(self, key: str) -> Any:
        """Lê primeiro das options, senão dos data."""
        if key in self.entry.options:
            return self.entry.options[key]
        return self.entry.data.get(key)

    @staticmethod
    def _normalize_aliases(val: Any) -> list[str]:
        if not val:
            return []
        if isinstance(val, list):
            return [str(v).strip() for v in val if str(v).strip()]
        # string CSV
        return [s.strip() for s in str(val).split(",") if s.strip()]

    # ---------------- Propriedades de Cover ----------------

    @property
    def current_cover_position(self) -> int | None:
        return int(round(self._calc.current_position()))

    @property
    def is_closed(self) -> bool | None:
        return self.current_cover_position == 0

    @property
    def is_opening(self) -> bool | None:
        return self._calc.travel_direction is TravelStatus.DIRECTION_UP

    @property
    def is_closing(self) -> bool | None:
        return self._calc.travel_direction is TravelStatus.DIRECTION_DOWN

    @property
    def assumed_state(self) -> bool:
        # Se 'always_confident' está activo, não marcamos como assumido
        return not self._always_confident

    # ---------------- Operações ----------------

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._async_start_motion(target=100, script=self._open_script)

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._async_start_motion(target=0, script=self._close_script)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._async_run_script(self._stop_script)
        self._calc.stop()
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        target = int(kwargs.get("position", self.current_cover_position or 0))
        target = max(0, min(100, target))

        if target == self.current_cover_position:
            # Nada a fazer
            return

        # Decide direção e script
        if target > self.current_cover_position:
            await self._async_start_motion(target=target, script=self._open_script)
        else:
            await self._async_start_motion(target=target, script=self._close_script)

    # ---------------- Lógica de movimento ----------------

    async def _async_start_motion(self, target: int, script: str | None) -> None:
        """Inicia deslocação até 'target' (0–100), chamando script adequado."""
        if script:
            await self._async_run_script(script)

        self._calc.start_travel(float(target))
        self.async_write_ha_state()

    async def _async_run_script(self, entity_id: str | None) -> None:
        """Executa um script (se definido)."""
        if not entity_id:
            return
        try:
            await self.hass.services.async_call(
                "script", "turn_on", {"entity_id": entity_id}, blocking=False
            )
        except Exception as exc:  # robustez: não bloquear HA
            _LOGGER.warning("Falha ao executar script %s: %s", entity_id, exc)

    async def _async_on_tick(self, _now) -> None:
        """Tick periódico: atualiza posição e aplica paragens se necessário."""
        # Atualiza estado (posição calculada)
        pos = self._calc.current_position()
        target = self._calc.travel_to_position
        direction = self._calc.travel_direction

        reached = abs(pos - target) < 0.5  # tolerância

        # Se atingimos alvo, enviamos STOP consoante opções
        if reached and direction is not TravelStatus.STOPPED:
            midrange = 20 <= target <= 80
            send_stop = False

            if target in (0, 100):
                send_stop = self._send_stop_at_ends
            else:
                # Em alvos parciais, regra geral precisa de STOP
                send_stop = True
                # Se só queremos “inteligente” em gama média
                if self._smart_stop_midrange:
                    send_stop = midrange

            if send_stop:
                await self._async_run_script(self._stop_script)

            self._calc.stop()

        # Publica novo estado
        self.async_write_ha_state()

    # ---------------- Atributos extra ----------------

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "current_position": self.current_cover_position,
            "target_position": int(round(self._calc.travel_to_position)),
            "travel_direction": self._calc.travel_direction.name,
            "aliases": self._aliases,
        }
        return attrs
