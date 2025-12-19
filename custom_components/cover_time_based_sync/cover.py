
"""Cover Time Based Sync — entidade Cover baseada em tempo, com scripts de abrir/fechar/parar e sincronização por cálculo temporal."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    ATTR_POSITION,
    ATTR_CURRENT_POSITION,
)

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
MID_RANGE_LOW = 20        # percent
MID_RANGE_HIGH = 80       # percent


# --------- Setup via Config Entry (plataforma cover) ----------
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup via Config Entry."""
    hass.data.setdefault(DOMAIN, {})
    entity = TimeBasedSyncCover(hass, entry)

    # Guardar referência para update listener
    hass.data[DOMAIN][entry.entry_id] = {"entity": entity}

    async_add_entities([entity], update_before_add=False)

    # Listener para refletir alterações em entry.data / entry.options
    async def _async_update_listener(updated_entry: ConfigEntry) -> None:
        ent: TimeBasedSyncCover = hass.data[DOMAIN][updated_entry.entry_id]["entity"]
        ent.apply_entry(updated_entry)
        ent.async_write_ha_state()
        _LOGGER.debug("Entry %s updated; entity refreshed", updated_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))


# --------- YAML setup (legacy, opcional) ----------
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities_cb: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Setup via YAML (legacy)."""
    # Emular um "entry" simples para reutilizar a lógica:
    entry_like = type(
        "EntryLike",
        (),
        {"data": config, "options": {}, "entry_id": "yaml"},
    )()
    entity = TimeBasedSyncCover(hass, entry_like)  # type: ignore[arg-type]
    async_add_entities_cb([entity], update_before_add=False)


class TimeBasedSyncCover(CoverEntity, RestoreEntity):
    """Entidade Cover baseada em tempo, com sincronização por cálculo."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_assumed_state = True  # não há sensores de posição reais

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry  # ConfigEntry ou objeto semelhante (YAML legacy)

        # Estado interno
        self._position: int = 0  # 0-100
        self._moving_task: Optional[asyncio.Task] = None
        self._moving_direction: Optional[str] = None  # "up"/"down" ou None

        # unique_id baseado no entry_id
        self._attr_unique_id = f"{DOMAIN}_{getattr(entry, 'entry_id', 'default')}"

        # Carregar configuração inicial
        self.apply_entry(entry)

    # --------- leitura/atribuição de config ---------
    def _opt_or_data(self, key: str, default: Any = None) -> Any:
        data = dict(getattr(self.entry, "data", {}) or {})
        options = dict(getattr(self.entry, "options", {}) or {})
        return options.get(key, data.get(key, default))

    def apply_entry(self, entry: ConfigEntry) -> None:
        """Aplicar dados/opções do entry à entidade."""
        self.entry = entry  # manter referência atualizada

        name = self._opt_or_data(CONF_FRIENDLY_NAME, self._opt_or_data("name", "Time Based Cover"))
        self._attr_name = name

        # Aliases (texto) — apenas exposto em attributes
        self._aliases = self._opt_or_data(CONF_ALIASES, "")

        # Temporizações
        self._travel_up: int = int(self._opt_or_data(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME))
        self._travel_down: int = int(self._opt_or_data(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME))

        # Scripts (entity_id de script.*)
        self._open_script_id: Optional[str] = self._opt_or_data(CONF_OPEN_SCRIPT, None)
        self._close_script_id: Optional[str] = self._opt_or_data(CONF_CLOSE_SCRIPT, None)
        self._stop_script_id: Optional[str] = self._opt_or_data(CONF_STOP_SCRIPT, None)

        # Comportamentos
        self._send_stop_at_ends: bool = bool(self._opt_or_data(CONF_SEND_STOP_AT_ENDS, False))
        self._always_confident: bool = bool(self._opt_or_data(CONF_ALWAYS_CONFIDENT, False))
        self._smart_stop_midrange: bool = bool(self._opt_or_data(CONF_SMART_STOP, False))

        _LOGGER.debug(
            "Applied entry settings: up=%s, down=%s, open=%s, close=%s, stop=%s, stop_at_ends=%s, confident=%s, midrange=%s",
            self._travel_up,
            self._travel_down,
            self._open_script_id,
            self._close_script_id,
            self._stop_script_id,
            self._send_stop_at_ends,
            self._always_confident,
            self._smart_stop_midrange,
        )

    # --------- ciclo de vida ---------
    async def async_added_to_hass(self) -> None:
        """Restaurar último estado."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and (pos := last_state.attributes.get(ATTR_CURRENT_POSITION)) is not None:
            try:
                self._position = int(pos)
                _LOGGER.debug("Restored position to %s%%", self._position)
            except (TypeError, ValueError):
                _LOGGER.debug("Invalid restored position: %s", pos)
        self.async_write_ha_state()

    # --------- propriedades ---------
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

    # --------- helpers de script ---------
    async def _run_script(self, entity_id: Optional[str]) -> None:
        """Executa um script pelo entity_id usando script.turn_on."""
        if not entity_id:
            return
        try:
            await self.hass.services.async_call(
                domain="script",
                service="turn_on",
                service_data={"entity_id": entity_id},
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
        # descer (fechar)
        return max(0.0, delta * float(self._travel_down))

    # --------- comandos Cover ---------
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

    # --------- lógica de movimento ---------
    async def _stop_motion(self) -> None:
        """Para movimento atual e executa script de stop."""
        if self._moving_task:
            self._moving_task.cancel()
            self._moving_task = None
        self._moving_direction = None
        await self._start_stop()
        self.async_write_ha_state()

    async def _move_to_target(self, target: int) -> None:
        """Move proporcionalmente até a posição alvo (0-100) sem usar nonlocal."""
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

        total_seconds = self._movement_seconds(self._position, target)
        if total_seconds <= 0:
            await self._start_stop()
            self._moving_direction = None
            return

        # smart_stop_midrange: enviar stop se alvo estiver no intervalo 20-80%
        should_midrange_stop = (
            self._smart_stop_midrange and 20 <= target <= 80
        )

        start_pos = self._position
        end_pos = target
        start_time = time.monotonic()

        async def _run_move() -> None:
            try:
                # estratégia simples: só atualiza no fim; se quiseres updates “em progresso”,
                # descomenta o loop abaixo com pequenos sleeps.
                #
                # while True:
                #     elapsed = time.monotonic() - start_time
                #     if elapsed >= total_seconds:
                #         break
                #     await asyncio.sleep(0.1)
                #
                # No fim do período, fixa na posição alvo:
                await asyncio.sleep(total_seconds)
                self._position = end_pos

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

    # --------- estado e atributos ---------
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "aliases": self._aliases,
            "travelling_time_up": self._travel_up,
            "travelling_time_down": self._travel_down,
            "send_stop_at_ends": self._send_stop_at_ends,
            "always_confident": self._always_confident,
            "smart_stop_midrange": self._smart_stop_midrange,
            ATTR_CURRENT_POSITION: self._position,
        }
        if self._open_script_id:
            attrs["open_script_entity_id"] = self._open_script_id
        if self._close_script_id:
            attrs["close_script_entity_id"] = self._close_script_id
        if self._stop_script_id:
            attrs["stop_script_entity_id"] = self._stop_script_id
        return attrs
