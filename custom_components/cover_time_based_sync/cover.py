
"""Cover Time Based Sync — entidade Cover baseada em tempo, com scripts de abrir/fechar/parar e sincronização por cálculo temporal."""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import timedelta
from typing import Any, Callable, Optional

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
)
from homeassistant.const import (
    CONF_NAME,
    STATE_OPENING,
    STATE_CLOSING,
    STATE_CLOSED,
    STATE_OPEN,
)
from homeassistant.helpers import script

from .const import (
    DOMAIN,
    CONF_TRAVELLING_TIME_UP,
    CONF_TRAVELLING_TIME_DOWN,
    CONF_OPEN_SCRIPT,
    CONF_CLOSE_SCRIPT,
    CONF_STOP_SCRIPT,
    CONF_SEND_STOP_AT_ENDS,
    CONF_ALWAYS_CONFIDENT,
    CONF_SMART_STOP,
    CONF_ALIASES,
    CONF_NAME as CONF_FRIENDLY_NAME,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_TRAVEL_TIME = 25  # seconds
MID_RANGE_LOW = 20       # percent
MID_RANGE_HIGH = 80      # percent


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Setup via Config Entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "entry": entry,
    }

    async_add_entities = hass.data[DOMAIN].get("async_add_entities_cb")
    if async_add_entities is None:
        # Fallback when loaded via Config Entries (standard HA paths)
        async_add_entities = hass.helpers.entity_component.async_add_entities

    entity = TimeBasedSyncCover(hass, entry)
    await entity.async_added_to_hass()
    async_add_entities([entity])
    return True  # entity added

# YAML setup (legacy) is optional; kept minimal to avoid breaking old configs.
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities_cb: Callable[[list[CoverEntity]], None],
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Setup via YAML (legacy)."""
    entry_like = type("EntryLike", (), {"data": config, "options": {}, "entry_id": "yaml"})()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["async_add_entities_cb"] = async_add_entities_cb
    entity = TimeBasedSyncCover(hass, entry_like)
    async_add_entities_cb([entity])


class TimeBasedSyncCover(CoverEntity, RestoreEntity):
    """Entidade Cover baseada em tempo, com sincronização por cálculo."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_assumed_state = True  # sem sensores de posição reais (UX adequada). [4](https://esphome.io/components/cover/time_based/)

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry  # ConfigEntry ou objeto semelhante (YAML legacy)
        data = dict(entry.data)
        options = dict(getattr(entry, "options", {}) or {})

        # Preferir opções sobre dados quando existirem
        def opt_or_data(key: str, default: Any = None) -> Any:
            return options.get(key, data.get(key, default))

        name = opt_or_data(CONF_FRIENDLY_NAME, opt_or_data(CONF_NAME, "Time Based Cover"))
        self._attr_name = name

        # Aliases (texto) — não altera entity_id por si só; serve para exposição opcional
        self._aliases = opt_or_data(CONF_ALIASES, "")

        # Temporizações
        self._travel_up: int = int(opt_or_data(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME))
        self._travel_down: int = int(opt_or_data(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME))

        # Scripts (entity_id de script.*)
        self._open_script_id: Optional[str] = opt_or_data(CONF_OPEN_SCRIPT, None)
        self._close_script_id: Optional[str] = opt_or_data(CONF_CLOSE_SCRIPT, None)
        self._stop_script_id: Optional[str] = opt_or_data(CONF_STOP_SCRIPT, None)

        # Comportamentos
        self._send_stop_at_ends: bool = bool(opt_or_data(CONF_SEND_STOP_AT_ENDS, False))
        self._always_confident: bool = bool(opt_or_data(CONF_ALWAYS_CONFIDENT, False))
        self._smart_stop_midrange: bool = bool(opt_or_data(CONF_SMART_STOP, False))

        # Estado interno
        self._position: int = 0  # 0-100
        self._moving_task: Optional[asyncio.Task] = None
        self._moving_direction: Optional[str] = None  # "up"/"down" ou None

        # IDs e unique_id (opcional se tiveres algo único)
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}"

    # ------------- ciclo de vida -------------

    async def async_added_to_hass(self) -> None:
        """Recupera estado anterior."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and ATTR_CURRENT_POSITION in last_state.attributes:
            self._position = int(last_state.attributes.get(ATTR_CURRENT_POSITION, 0))
            _LOGGER.debug("Restored position to %s%%", self._position)  # [1](https://community.home-assistant.io/t/custom-component-cover-time-based/187654)
        self.async_write_ha_state()

    # ------------- propriedades -------------

    @property
    def current_cover_position(self) -> int | None:
        return self._position

    @property
    def is_opening(self) -> bool:
        return self._moving_direction == "up"

    @property
    def is_closing(self) -> bool:
        return self._moving_direction == "down"

    @property
    def is_closed(self) -> bool:
        return self._position == 0

    # ------------- helpers de script -------------

    async def _run_script(self, entity_id: Optional[str]) -> None:
        """Executa um script pelo entity_id."""
        if not entity_id:
            return
        try:
            await self.hass.services.async_call(
                domain="script",
                service=entity_id.split(".", 1)[1],  # script.nome
                service_data={},
                blocking=False,
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Falha ao executar script %s: %s", entity_id, exc)

    async def _start_open(self) -> None:
        await self._run_script(self._open_script_id)

    async def _start_close(self) -> None:
        await self._run_script(self._close_script_id)

    async def _start_stop(self) -> None:
        await self._run_script(self._stop_script_id)

    def _movement_seconds(self, from_pos: int, to_pos: int) -> float:
        """Calcula segundos necessários com base na direção."""
        delta = abs(to_pos - from_pos) / 100.0
        if to_pos > from_pos:
            # subir (abrir)
            return max(0.0, delta * float(self._travel_up))
        else:
            # descer (fechar)
            return max(0.0, delta * float(self._travel_down))

    # ------------- comandos Cover -------------

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._move_to_target(100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._move_to_target(0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        target = kwargs.get(ATTR_POSITION)
        if target is None:
            return
        target = max(0, min(100, int(target)))
        await self._move_to_target(target)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._stop_motion()

    # ------------- lógica de movimento -------------

    async def _stop_motion(self) -> None:
        """Para movimento atual e executa script de stop."""
        if self._moving_task:
            self._moving_task.cancel()
            self._moving_task = None
        self._moving_direction = None
        await self._start_stop()
        self.async_write_ha_state()

    async def _move_to_target(self, target: int) -> None:
        """Move proporcionalmente até a posição alvo (0-100)."""
        # Cancelar movimento anterior
        if self._moving_task:
            self._moving_task.cancel()
            self._moving_task = None

        # Sem diferença => apenas garantir stop
        if target == self._position:
            await self._start_stop()
            return

        # Determinar direção e acionar script
        direction = "up" if target > self._position else "down"
        self._moving_direction = direction

        if direction == "up":
            await self._start_open()
        else:
            await self._start_close()

        self.async_write_ha_state()

        seconds = self._movement_seconds(self._position, target)
        if seconds <= 0:
            await self._start_stop()
            self._moving_direction = None
            return

        # smart_stop_midrange: enviar stop entre 20-80% quando alvo está nesse intervalo
        should_midrange_stop = (
            self._smart_stop_midrange
            and MID_RANGE_LOW <= target <= MID_RANGE_HIGH
        )

        async def _run_move():
            try:
                # Atualiza posição “em tempo real” no fim (simple approach)
                await asyncio.sleep(seconds)
                self._position = target

                # Stop automático ao atingir extremos
                if self._send_stop_at_ends and (self._position in (0, 100)):
                    await self._start_stop()
                elif should_midrange_stop:
                    # Enviar stop ao atingir alvo intermediário
                    await self._start_stop()

            except asyncio.CancelledError:
                # Cancelado por novo comando
                pass
            finally:
                self._moving_direction = None
                self.async_write_ha_state()

        self._moving_task = asyncio.create_task(_run_move())

    # ------------- estado e atributos -------------

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "aliases": self._aliases,
            "travelling_time_up": self._travel_up,
            "travelling_time_down": self._travel_down,
            "send_stop_at_ends": self._send_stop_at_ends,
            "always_confident": self._always_confident,
            "smart_stop_midrange": self._smart_stop_midrange,
        }
        if self._open_script_id:
            attrs["open_script_entity_id"] = self._open_script_id
        if self._close_script_id:
            attrs["close_script_entity_id"] = self._close_script_id
        if self._stop_script_id:
            attrs["stop_script_entity_id"] = self._stop_script_id
        return attrs
