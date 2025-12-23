# custom_components/cover_time_based_sync/cover.py
"""Cover Time Based Sync — entidade Cover baseada em tempo, com scripts,
sensores de contacto e modo 'Controlo Único' (RF) nativo com próxima ação em atributo."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    ATTR_POSITION,
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
    CONF_NAME as CONF_FRIENDLY_NAME,
    CONF_OPEN_CONTACT_SENSOR,
    CONF_CLOSE_CONTACT_SENSOR,
    CONF_SINGLE_CONTROL_ENABLED,
    CONF_SINGLE_CONTROL_PULSE_MS,
    ATTR_CONFIDENT,
    ATTR_POSITION_TYPE,
)
from .travelcalculator import TravelCalculator

_LOGGER = logging.getLogger(__name__)
SIGNAL_SET_KNOWN_POSITION = f"{DOMAIN}_set_known_position"
SIGNAL_SET_KNOWN_ACTION = f"{DOMAIN}_set_known_action"
SIGNAL_ACTIVATE_SCRIPT = f"{DOMAIN}_activate_script"

DEFAULT_TRAVEL_TIME = 25
MID_RANGE_LOW = 20
MID_RANGE_HIGH = 80
UPDATE_INTERVAL_SEC = 0.5  # solicitado

# Direções
DIR_UP = "up"
DIR_DOWN = "down"

NEXT_OPEN = "open"
NEXT_CLOSE = "close"
NEXT_STOP = "stop"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hass.data.setdefault(DOMAIN, {})
    entity = TimeBasedSyncCover(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = {"entity": entity}
    async_add_entities([entity], update_before_add=False)

    async def _async_update_listener(updated_entry: ConfigEntry) -> None:
        ent: TimeBasedSyncCover = hass.data[DOMAIN][updated_entry.entry_id]["entity"]
        ent.apply_entry(updated_entry)
        ent._publish_state()  # publicar estado coerente após update
        _LOGGER.debug("Entry %s updated; entity refreshed", updated_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities_cb: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    entry_like = type("EntryLike", (), {"data": config, "options": {}, "entry_id": "yaml"})()
    entity = TimeBasedSyncCover(hass, entry_like)
    async_add_entities_cb([entity], update_before_add=False)


class TimeBasedSyncCover(CoverEntity, RestoreEntity):
    """Entidade cover baseada em tempo com modo RF (single control)."""

    _attr_assumed_state = True  # dinâmica: False enquanto está em movimento

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        # Estado principal
        self._position: int = 0
        self._moving_task: Optional[asyncio.Task] = None
        self._moving_direction: Optional[str] = None
        self._last_confident_state: Optional[bool] = None
        self._attr_unique_id = f"{DOMAIN}_{getattr(entry, 'entry_id', 'default')}"
        self._attr_supported_features = CoverEntityFeature.SET_POSITION

        # Subscrições
        self._unsub_known_position = None
        self._unsub_known_action = None
        self._unsub_close_contact = None
        self._unsub_open_contact = None
        self._unsub_activate_script = None

        # Cálculo e sincronização
        self._calc: TravelCalculator | None = None
        self._op_lock = asyncio.Lock()  # serializa comandos de alto nível

        # Sensores opcionais
        self._close_contact_sensor_id: Optional[str] = None
        self._open_contact_sensor_id: Optional[str] = None

        # Modo RF (single button)
        self._single_control_enabled: bool = False
        self._single_control_script_id: Optional[str] = None
        self._single_pulse_delay_ms: int = 400
        self._single_next_action: str = NEXT_OPEN

        self.apply_entry(entry)

    # ------------------------------
    # Utilitários & publicação estado
    # ------------------------------
    def _opt_or_data(self, key: str, default: Any = None) -> Any:
        data = dict(getattr(self.entry, "data", {}) or {})
        options = dict(getattr(self.entry, "options", {}) or {})
        return options.get(key, data.get(key, default))

    def _first_script(self) -> Optional[str]:
        for key in (CONF_OPEN_SCRIPT, CONF_CLOSE_SCRIPT, CONF_STOP_SCRIPT):
            val = self._opt_or_data(key)
            if isinstance(val, str) and val:
                return val
        return None

    def _update_supported_features(self) -> None:
        """Atualiza _attr_supported_features (apenas próxima ação em RF; todos em Standard)."""
        base = CoverEntityFeature.SET_POSITION
        if not self._single_control_enabled:
            self._attr_supported_features = base | CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
            return
        # Modo RF: apenas o botão da próxima ação (evitar match/case para compat. Python 3.13)
        if self._single_next_action == NEXT_OPEN:
            self._attr_supported_features = base | CoverEntityFeature.OPEN
        elif self._single_next_action == NEXT_CLOSE:
            self._attr_supported_features = base | CoverEntityFeature.CLOSE
        else:
            # NEXT_STOP (ou qualquer outro valor cai aqui por segurança)
            self._attr_supported_features = base | CoverEntityFeature.STOP

    def _publish_state(self, *, recompute_features: bool = True) -> None:
        if recompute_features:
            self._update_supported_features()
        self.async_write_ha_state()

    async def _set_next_action(self, next_action: str) -> None:
        self._single_next_action = next_action
        self._publish_state()

    def _log_state(self, event: str, extra: dict | None = None) -> None:
        _LOGGER.debug(
            "%s: pos=%s dir=%s next=%s moving=%s features=%s %s",
            event,
            self._position,
            self._moving_direction,
            self._single_next_action,
            bool(self._moving_task),
            int(self._attr_supported_features),
            extra or {},
        )

    # ------------------------------
    # Propriedades (contrato de UI)
    # ------------------------------
    @property
    def current_cover_position(self) -> int | None:
        return self._position

    @property
    def is_opening(self) -> bool:
        return self._moving_direction == DIR_UP

    @property
    def is_closing(self) -> bool:
        return self._moving_direction == DIR_DOWN

    @property
    def is_closed(self) -> bool:
        return self._position == 0

    @property
    def supported_features(self) -> int:
        return self._attr_supported_features

    # ------------------------------
    # Config / apply
    # ------------------------------
    def apply_entry(self, entry: ConfigEntry) -> None:
        self.entry = entry
        self._attr_name = self._opt_or_data(CONF_FRIENDLY_NAME, self._opt_or_data("name", "Time Based Cover"))

        self._travel_up: float = float(self._opt_or_data(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME))
        self._travel_down: float = float(self._opt_or_data(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME))

        self._open_script_id: Optional[str] = self._opt_or_data(CONF_OPEN_SCRIPT)
        self._close_script_id: Optional[str] = self._opt_or_data(CONF_CLOSE_SCRIPT)
        self._stop_script_id: Optional[str] = self._opt_or_data(CONF_STOP_SCRIPT)

        self._send_stop_at_ends: bool = bool(self._opt_or_data(CONF_SEND_STOP_AT_ENDS, False))
        self._always_confident: bool = bool(self._opt_or_data(CONF_ALWAYS_CONFIDENT, False))
        self._smart_stop_midrange: bool = bool(self._opt_or_data(CONF_SMART_STOP, False))

        self._close_contact_sensor_id = self._opt_or_data(CONF_CLOSE_CONTACT_SENSOR)
        self._open_contact_sensor_id = self._opt_or_data(CONF_OPEN_CONTACT_SENSOR)

        self._single_control_enabled = bool(self._opt_or_data(CONF_SINGLE_CONTROL_ENABLED, False))
        self._single_control_script_id = (
            self._opt_or_data(CONF_OPEN_SCRIPT) or self._first_script()
            if self._single_control_enabled
            else None
        )
        self._single_pulse_delay_ms = int(self._opt_or_data(CONF_SINGLE_CONTROL_PULSE_MS, 400))

        if self._calc is None:
            self._calc = TravelCalculator(self._travel_down, self._travel_up)
        else:
            self._calc.travel_time_down = self._travel_down
            self._calc.travel_time_up = self._travel_up
        self._calc.set_position(float(self._position))

        self._update_supported_features()
        self._log_state("apply_entry")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and (pos := last.attributes.get("current_position")) is not None:
            try:
                self._position = int(pos)
            except (TypeError, ValueError):
                pass

        if self._calc is None:
            self._calc = TravelCalculator(self._travel_down, self._travel_up)
        self._calc.set_position(float(self._position))

        await self._set_next_action(NEXT_OPEN if self._position == 0 else NEXT_CLOSE if self._position == 100 else NEXT_STOP)
        self._publish_state()
        self._log_state("added_to_hass")

        self._unsub_known_position = async_dispatcher_connect(
            self.hass, SIGNAL_SET_KNOWN_POSITION, self._dispatcher_set_known_position
        )
        self._unsub_known_action = async_dispatcher_connect(
            self.hass, SIGNAL_SET_KNOWN_ACTION, self._dispatcher_set_known_action
        )
        self._unsub_activate_script = async_dispatcher_connect(
            self.hass, SIGNAL_ACTIVATE_SCRIPT, self._dispatcher_activate_script
        )

        # Sensores de contacto (opcionais)
        if self._close_contact_sensor_id:
            self._unsub_close_contact = async_track_state_change_event(
                self.hass, [self._close_contact_sensor_id], self._closed_contact_state_changed
            )
            st = self.hass.states.get(self._close_contact_sensor_id)
            if st and str(st.state).lower() == "off":
                await self._apply_contact_hit(0, source_entity=self._close_contact_sensor_id)

        if self._open_contact_sensor_id:
            self._unsub_open_contact = async_track_state_change_event(
                self.hass, [self._open_contact_sensor_id], self._open_contact_state_changed
            )
            st = self.hass.states.get(self._open_contact_sensor_id)
            if st and str(st.state).lower() == "off":
                await self._apply_contact_hit(100, source_entity=self._open_contact_sensor_id)

    async def async_will_remove_from_hass(self) -> None:
        for unsub in (
            "_unsub_known_position",
            "_unsub_known_action",
            "_unsub_close_contact",
            "_unsub_open_contact",
            "_unsub_activate_script",
        ):
            func = getattr(self, unsub)
            if func:
                func()
                setattr(self, unsub, None)

    # ------------------------------
    # RF helpers (pulsos) & scripts
    # ------------------------------
    async def _single_pulse(self) -> None:
        if not self._single_control_enabled or not self._single_control_script_id:
            return
        try:
            await self.hass.services.async_call(
                "script", "turn_on", {"entity_id": self._single_control_script_id}, blocking=False
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Falha ao executar script (single RF) %s: %s", self._single_control_script_id, exc)

    async def _single_pulses(self, count: int) -> None:
        delay = max(0.05, self._single_pulse_delay_ms / 1000.0)
        for _ in range(max(0, count)):
            await self._single_pulse()
            await asyncio.sleep(delay)

    async def _ensure_action_single(self, target_action: str) -> None:
        """Decide o número de pulsos com base no estado e atualiza next_action. Não publica estado."""
        opening = self.is_opening
        closing = self.is_closing

        if target_action == NEXT_STOP:
            if opening or closing:  # STOP só em movimento
                await self._single_pulses(1)
                # Próxima ação alterna consoante sentido anterior
                self._single_next_action = NEXT_CLOSE if opening else NEXT_OPEN
            return

        if target_action == NEXT_OPEN:
            if opening:
                await self._single_pulses(1)
            elif closing:
                await self._single_pulses(2)  # parar + abrir
            else:
                await self._single_pulses(1)
            self._single_next_action = NEXT_STOP
            return

        if target_action == NEXT_CLOSE:
            if closing:
                await self._single_pulses(1)
            elif opening:
                await self._single_pulses(2)  # parar + fechar
            else:
                await self._single_pulses(1)
            self._single_next_action = NEXT_STOP
            return

    async def _run_script(self, entity_id: Optional[str]) -> None:
        if self._single_control_enabled or not entity_id:
            return
        try:
            await self.hass.services.async_call("script", "turn_on", {"entity_id": entity_id}, blocking=False)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Falha ao executar script %s: %s", entity_id, exc)

    async def _start_action(self, action: str) -> None:
        """Executa a ação física (pulsos ou script) e atualiza next_action internamente."""
        if self._single_control_enabled:
            await self._ensure_action_single(action)
        else:
            if action == NEXT_OPEN:
                await self._run_script(self._open_script_id)
            elif action == NEXT_CLOSE:
                await self._run_script(self._close_script_id)
            elif action == NEXT_STOP:
                await self._run_script(self._stop_script_id)

    # ------------------------------
    # Movimento (máquina de estados)
    # ------------------------------
    async def _cancel_move_task(self) -> None:
        if self._moving_task:
            self._moving_task.cancel()
            try:
                await self._moving_task
            except asyncio.CancelledError:
                pass
            self._moving_task = None

    def _begin_motion(self, direction: str) -> None:
        """Marca início de movimento: direção, assumed_state, next_action=STOP e publica estado coerente."""
        self._moving_direction = direction
        self._attr_assumed_state = False
        self._single_next_action = NEXT_STOP
        self._publish_state()
        self._log_state("begin_motion", {"direction": direction})

    def _finish_motion(self) -> None:
        """Marca fim de movimento: limpa direção, ajusta próxima ação conforme posição e publica."""
        self._moving_direction = None
        self._attr_assumed_state = True
        # Próxima ação pós-paragem
        self._single_next_action = NEXT_OPEN if self._position == 0 else NEXT_CLOSE if self._position == 100 else NEXT_STOP
        self._publish_state()
        self._log_state("finish_motion")

    async def _move_to_target(self, target: int, *, drive_scripts: bool) -> None:
        """Motor de movimento. Assume _op_lock adquirido por caller."""
        # 1) short-circuits
        await self._cancel_move_task()
        if target == self._position:
            if target in (0, 100) and self._send_stop_at_ends:
                await self._start_action(NEXT_STOP) if drive_scripts else None
            elif self._smart_stop_midrange and target not in (0, 100):
                await self._start_action(NEXT_STOP) if drive_scripts else None
            return

        # 2) direção e arranque físico
        direction = DIR_UP if target > self._position else DIR_DOWN
        self._begin_motion(direction)

        if drive_scripts:
            await self._start_action(NEXT_OPEN if direction == DIR_UP else NEXT_CLOSE)

        # 3) preparar TravelCalculator
        calc = self._calc or TravelCalculator(self._travel_down, self._travel_up)
        self._calc = calc
        calc.travel_time_down = self._travel_down
        calc.travel_time_up = self._travel_up
        calc.set_position(float(self._position))
        calc.start_travel(float(target))

        # 4) loop de movimento
        should_mid_stop = self._smart_stop_midrange and MID_RANGE_LOW <= target <= MID_RANGE_HIGH

        async def _runner() -> None:
            try:
                while True:
                    await asyncio.sleep(UPDATE_INTERVAL_SEC)
                    current = int(round(calc.current_position()))
                    self._position = min(current, target) if direction == DIR_UP else max(current, target)
                    self._publish_state(recompute_features=False)

                    # Fim de curso
                    if self._position in (0, 100):
                        if self._send_stop_at_ends:
                            if drive_scripts:
                                await self._start_action(NEXT_STOP)
                            elif self._single_control_enabled and (self.is_opening or self.is_closing):
                                await self._ensure_action_single(NEXT_STOP)
                        calc.stop()
                        break

                    # Paragem a meio (smart stop)
                    if should_mid_stop and self._position == target:
                        if drive_scripts:
                            await self._start_action(NEXT_STOP)
                        elif self._single_control_enabled and (self.is_opening or self.is_closing):
                            await self._ensure_action_single(NEXT_STOP)
                        calc.stop()
                        break

                    # Alvo sem smart stop
                    if self._position == target:
                        calc.stop()
                        break
            except asyncio.CancelledError:
                pass
            finally:
                # Fixar posição final e publicar
                self._position = int(round(calc.current_position()))
                self._finish_motion()

        self._moving_task = asyncio.create_task(_runner())

    # ------------------------------
    # Comandos de alto nível (bloqueados por _op_lock)
    # ------------------------------
    async def async_open_cover(self, **kwargs: Any) -> None:
        async with self._op_lock:
            if self._single_control_enabled:
                await self._start_action(NEXT_OPEN)
            await self._move_to_target(100, drive_scripts=not self._single_control_enabled)

    async def async_close_cover(self, **kwargs: Any) -> None:
        async with self._op_lock:
            if self._single_control_enabled:
                await self._start_action(NEXT_CLOSE)
            await self._move_to_target(0, drive_scripts=not self._single_control_enabled)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        target = kwargs.get(ATTR_POSITION)
        if target is None:
            return
        target = max(0, min(100, int(target)))
        async with self._op_lock:
            if self._single_control_enabled:
                if target > self._position:
                    await self._start_action(NEXT_OPEN)
                elif target < self._position:
                    await self._start_action(NEXT_CLOSE)
                else:
                    return
                await self._move_to_target(target, drive_scripts=False)
            else:
                await self._move_to_target(target, drive_scripts=True)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        async with self._op_lock:
            if self._single_control_enabled:
                await self._start_action(NEXT_STOP)
            await self._cancel_move_task()
            # travão virtual & publicar
            if self._calc:
                self._calc.stop()
                self._position = int(round(self._calc.current_position()))
            self._finish_motion()

    # ------------------------------
    # Atributos extra
    # ------------------------------
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "travelling_time_up": getattr(self, "_travel_up", DEFAULT_TRAVEL_TIME),
            "travelling_time_down": getattr(self, "_travel_down", DEFAULT_TRAVEL_TIME),
            "send_stop_at_ends": getattr(self, "_send_stop_at_ends", False),
            "always_confident": getattr(self, "_always_confident", False),
            "smart_stop_midrange": getattr(self, "_smart_stop_midrange", False),
            "current_position": self._position,
            "single_control_enabled": self._single_control_enabled,
            "single_control_rf_script_entity_id": self._single_control_script_id,
            "single_control_pulse_delay_ms": self._single_pulse_delay_ms,
            "single_control_next_action": self._single_next_action,
        }
        if hasattr(self, "_open_script_id") and self._open_script_id:
            attrs["open_script_entity_id"] = self._open_script_id
        if hasattr(self, "_close_script_id") and self._close_script_id:
            attrs["close_script_entity_id"] = self._close_script_id
        if hasattr(self, "_stop_script_id") and self._stop_script_id:
            attrs["stop_script_entity_id"] = self._stop_script_id
        if self._close_contact_sensor_id:
            attrs["close_contact_sensor_entity_id"] = self._close_contact_sensor_id
        if self._open_contact_sensor_id:
            attrs["open_contact_sensor_entity_id"] = self._open_contact_sensor_id
        if self._last_confident_state is not None:
            attrs["position_confident"] = self._last_confident_state
        return attrs

    # ------------------------------
    # Dispatcher (serviços) — assíncronos
    # ------------------------------
    async def _dispatcher_set_known_position(
        self,
        target_entities: str | list[str] | None,
        position: int | float | None,
        confident: bool,
        position_type: str,
    ) -> None:
        if not self._matches_target_entities(target_entities):
            return
        if position is None:
            return

        try:
            pos_int = max(0, min(100, int(round(float(position)))))
        except (TypeError, ValueError):
            return

        self._last_confident_state = confident
        if self._calc is None:
            self._calc = TravelCalculator(self._travel_down, self._travel_up)

        async with self._op_lock:
            if position_type == "current":
                self._calc.set_position(float(pos_int))
                self._position = int(round(self._calc.current_position()))
                await self._set_next_action(NEXT_OPEN if self._position == 0 else NEXT_CLOSE if self._position == 100 else NEXT_STOP)
                self._publish_state()
            else:
                if self._single_control_enabled:
                    if pos_int > self._position:
                        await self._start_action(NEXT_OPEN)
                    elif pos_int < self._position:
                        await self._start_action(NEXT_CLOSE)
                await self._move_to_target(pos_int, drive_scripts=not self._single_control_enabled)

    async def _dispatcher_set_known_action(
        self,
        target_entities: str | list[str] | None,
        action: str | None,
    ) -> None:
        if not self._matches_target_entities(target_entities) or not action:
            return
        act = str(action).lower().strip()
        if act not in (NEXT_OPEN, NEXT_CLOSE, NEXT_STOP):
            return
        if act == NEXT_OPEN:
            await self.async_open_cover()
        elif act == NEXT_CLOSE:
            await self.async_close_cover()
        else:
            await self.async_stop_cover()

    async def _dispatcher_activate_script(
        self,
        target_entities: str | list[str] | None,
        action: str | None,
    ) -> None:
        if not self._matches_target_entities(target_entities):
            return
        async with self._op_lock:
            if self._single_control_enabled:
                # Usa a próxima ação — evitar pulso duplicado no STOP
                if self._single_next_action == NEXT_OPEN:
                    await self._start_action(NEXT_OPEN)
                    await self._move_to_target(100, drive_scripts=False)
                elif self._single_next_action == NEXT_CLOSE:
                    await self._start_action(NEXT_CLOSE)
                    await self._move_to_target(0, drive_scripts=False)
                else:
                    # Apenas parar (um pulso se estiver em movimento)
                    await self.async_stop_cover()
                return

            # Standard
            if not action:
                return
            act = str(action).lower().strip()
            if act == NEXT_OPEN:
                await self._run_script(self._open_script_id)
                await self._move_to_target(100, drive_scripts=False)
            elif act == NEXT_CLOSE:
                await self._run_script(self._close_script_id)
                await self._move_to_target(0, drive_scripts=False)
            elif act == NEXT_STOP:
                await self._run_script(self._stop_script_id)
                await self.async_stop_cover()

    # ------------------------------
    # Utilitário de filtro de alvos
    # ------------------------------
    def _matches_target_entities(self, target_entities: str | list[str] | None) -> bool:
        if not target_entities:
            return True
        if isinstance(target_entities, str):
            targets = [t.strip() for t in target_entities.split(",") if t.strip()]
        else:
            targets = [t.strip() for t in target_entities if t and isinstance(t, str)]
        return self.entity_id in targets

    # ------------------------------
    # Sensores binários (INVERTIDOS)
    # ------------------------------
    async def _apply_contact_hit(self, forced_position: int, *, source_entity: Optional[str] = None) -> None:
        await self._cancel_move_task()
        if self._calc is None:
            self._calc = TravelCalculator(self._travel_down, self._travel_up)
        self._calc.set_position(float(forced_position))
        self._position = forced_position
        self._attr_assumed_state = True
        self._last_confident_state = True

        if self._send_stop_at_ends and forced_position in (0, 100) and not self._single_control_enabled:
            await self._start_action(NEXT_STOP)

        await self._set_next_action(NEXT_OPEN if forced_position == 0 else NEXT_CLOSE)
        self._publish_state()
        self._log_state("contact_hit", {"source": source_entity})

    async def _closed_contact_state_changed(self, event) -> None:
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if not new_state:
            return
        ns = str(new_state.state).lower()
        os = str(old_state.state).lower() if old_state else None

        if ns == "off":
            await self._apply_contact_hit(0, source_entity=self._close_contact_sensor_id)
            return
        if ns == "on" and os == "off":
            if not self._moving_task:
                await self._move_to_target(100, drive_scripts=False)

    async def _open_contact_state_changed(self, event) -> None:
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if not new_state:
            return
        ns = str(new_state.state).lower()
        os = str(old_state.state).lower() if old_state else None

        if ns == "off":
            await self._apply_contact_hit(100, source_entity=self._open_contact_sensor_id)
            return
        if ns == "on" and os == "off":
            if not self._moving_task:
                await self._move_to_target(0, drive_scripts=False)
