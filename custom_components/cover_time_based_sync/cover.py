
# custom_components/cover_time_based_sync/cover.py
"""Cover Time Based Sync — entidade Cover baseada em tempo, com scripts de abrir/fechar/parar,
sincronização por cálculo temporal (TravelCalculator), integração com dispatcher e
sensores binários opcionais de contacto para tornar a posição 'conhecida'."""

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
    CONF_ALIASES,
    CONF_NAME as CONF_FRIENDLY_NAME,
    # novos:
    CONF_OPEN_CONTACT_SENSOR,
    CONF_CLOSE_CONTACT_SENSOR,
    # atributos (para serviços)
    ATTR_CONFIDENT,
    ATTR_POSITION_TYPE,
)
from .travelcalculator import TravelCalculator

_LOGGER = logging.getLogger(__name__)

SIGNAL_SET_KNOWN_POSITION = f"{DOMAIN}_set_known_position"
SIGNAL_SET_KNOWN_ACTION = f"{DOMAIN}_set_known_action"

DEFAULT_TRAVEL_TIME = 25
MID_RANGE_LOW = 20
MID_RANGE_HIGH = 80
UPDATE_INTERVAL_SEC = 1.0


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
        ent.async_write_ha_state()
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
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_assumed_state = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        self._position: int = 0
        self._moving_task: Optional[asyncio.Task] = None
        self._moving_direction: Optional[str] = None
        self._last_confident_state: Optional[bool] = None

        self._attr_unique_id = f"{DOMAIN}_{getattr(entry, 'entry_id', 'default')}"

        self._unsub_known_position = None
        self._unsub_known_action = None

        # novos: unsubs dos sensores de contacto
        self._unsub_close_contact = None
        self._unsub_open_contact = None

        self._calc: Optional[TravelCalculator] = None

        # ids dos sensores (opcionais)
        self._close_contact_sensor_id: Optional[str] = None
        self._open_contact_sensor_id: Optional[str] = None

        self.apply_entry(entry)

    def _opt_or_data(self, key: str, default: Any = None) -> Any:
        data = dict(getattr(self.entry, "data", {}) or {})
        options = dict(getattr(self.entry, "options", {}) or {})
        return options.get(key, data.get(key, default))

    def apply_entry(self, entry: ConfigEntry) -> None:
        self.entry = entry

        name = self._opt_or_data(CONF_FRIENDLY_NAME, self._opt_or_data("name", "Time Based Cover"))
        self._attr_name = name

        self._aliases = self._opt_or_data(CONF_ALIASES, "")

        self._travel_up: float = float(self._opt_or_data(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME))
        self._travel_down: float = float(self._opt_or_data(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME))

        self._open_script_id: Optional[str] = self._opt_or_data(CONF_OPEN_SCRIPT, None)
        self._close_script_id: Optional[str] = self._opt_or_data(CONF_CLOSE_SCRIPT, None)
        self._stop_script_id: Optional[str] = self._opt_or_data(CONF_STOP_SCRIPT, None)

        self._send_stop_at_ends: bool = bool(self._opt_or_data(CONF_SEND_STOP_AT_ENDS, False))
        self._always_confident: bool = bool(self._opt_or_data(CONF_ALWAYS_CONFIDENT, False))
        self._smart_stop_midrange: bool = bool(self._opt_or_data(CONF_SMART_STOP, False))

        # novos: sensores binários
        self._close_contact_sensor_id = self._opt_or_data(CONF_CLOSE_CONTACT_SENSOR, None)
        self._open_contact_sensor_id = self._opt_or_data(CONF_OPEN_CONTACT_SENSOR, None)

        # recalc
        if self._calc is None:
            self._calc = TravelCalculator(self._travel_down, self._travel_up)
        self._calc.travel_time_down = self._travel_down
        self._calc.travel_time_up = self._travel_up
        self._calc.set_position(float(self._position))

        _LOGGER.debug(
            "Applied entry settings: up=%s, down=%s, open=%s, close=%s, stop=%s, "
            "stop_at_ends=%s, confident=%s, midrange=%s, close_contact=%s, open_contact=%s",
            self._travel_up,
            self._travel_down,
            self._open_script_id,
            self._close_script_id,
            self._stop_script_id,
            self._send_stop_at_ends,
            self._always_confident,
            self._smart_stop_midrange,
            self._close_contact_sensor_id,
            self._open_contact_sensor_id,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state and (pos := last_state.attributes.get("current_position")) is not None:
            try:
                self._position = int(pos)
                _LOGGER.debug("Restored position to %s%%", self._position)
            except (TypeError, ValueError):
                _LOGGER.debug("Invalid restored position: %s", pos)

        if self._calc is None:
            self._calc = TravelCalculator(self._travel_down, self._travel_up)
        self._calc.set_position(float(self._position))

        self.async_write_ha_state()

        # Dispatcher signals (serviços)
        self._unsub_known_position = async_dispatcher_connect(
            self.hass, SIGNAL_SET_KNOWN_POSITION, self._dispatcher_set_known_position
        )
        self._unsub_known_action = async_dispatcher_connect(
            self.hass, SIGNAL_SET_KNOWN_ACTION, self._dispatcher_set_known_action
        )

        # -------- Sensores binários de contacto (opcionais) ----------
        # Regista listeners e faz avaliação inicial
        if self._close_contact_sensor_id:
            self._unsub_close_contact = async_track_state_change_event(
                self.hass, [self._close_contact_sensor_id], self._closed_contact_state_changed
            )
            st = self.hass.states.get(self._close_contact_sensor_id)
            if st and str(st.state).lower() == "on":
                await self._apply_contact_hit(0, source_entity=self._close_contact_sensor_id)

        if self._open_contact_sensor_id:
            self._unsub_open_contact = async_track_state_change_event(
                self.hass, [self._open_contact_sensor_id], self._open_contact_state_changed
            )
            st = self.hass.states.get(self._open_contact_sensor_id)
            if st and str(st.state).lower() == "on":
                await self._apply_contact_hit(100, source_entity=self._open_contact_sensor_id)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_known_position:
            self._unsub_known_position()
            self._unsub_known_position = None
        if self._unsub_known_action:
            self._unsub_known_action()
            self._unsub_known_action = None

        # novos: remove listeners dos sensores
        if self._unsub_close_contact:
            self._unsub_close_contact()
            self._unsub_close_contact = None
        if self._unsub_open_contact:
            self._unsub_open_contact()
            self._unsub_open_contact = None

    # ------------------ Propriedades ------------------
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

    # ------------------ Scripts ------------------
    async def _run_script(self, entity_id: Optional[str]) -> None:
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

    # ------------------ Comandos Cover ------------------
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

    async def _stop_motion(self) -> None:
        if self._moving_task:
            self._moving_task.cancel()
            self._moving_task = None
        self._moving_direction = None

        if self._calc:
            self._calc.stop()
            self._position = int(round(self._calc.current_position()))

        # STOP explícito do utilizador → chama SEMPRE o script de stop
        await self._start_stop()
        self.async_write_ha_state()

    async def _move_to_target(self, target: int) -> None:
        if self._moving_task:
            self._moving_task.cancel()
            self._moving_task = None

        # Se o alvo já é a posição atual, respeitar opções para STOP
        if target == self._position:
            if target in (0, 100):
                if self._send_stop_at_ends:
                    await self._start_stop()
            else:
                if self._smart_stop_midrange:
                    await self._start_stop()
            return

        direction = "up" if target > self._position else "down"
        self._moving_direction = direction

        if direction == "up":
            await self._start_open()
        else:
            await self._start_close()

        if self._calc is None:
            self._calc = TravelCalculator(self._travel_down, self._travel_up)
        self._calc.set_position(float(self._position))
        self._calc.start_travel(float(target))

        self.async_write_ha_state()

        should_midrange_stop = self._smart_stop_midrange and MID_RANGE_LOW <= target <= MID_RANGE_HIGH

        async def _run_move() -> None:
            try:
                while True:
                    await asyncio.sleep(UPDATE_INTERVAL_SEC)
                    current = int(round(self._calc.current_position()))
                    if direction == "up":
                        current = min(current, target)
                    else:
                        current = max(current, target)
                    self._position = current
                    self.async_write_ha_state()

                    # ----- Paragens automáticas -----
                    # 1) Extremos (0/100): só chama stop se 'send_stop_at_ends' estiver ativo
                    if self._position in (0, 100):
                        if self._send_stop_at_ends:
                            await self._start_stop()
                        self._calc.stop()
                        break

                    # 2) Alvo intermédio com 'smart_stop_midrange' ativo → chama stop
                    if should_midrange_stop and self._position == target:
                        await self._start_stop()
                        self._calc.stop()
                        break

                    # 3) Alvo intermédio com 'smart_stop_midrange' DESATIVADO → não chama stop
                    if self._position == target:
                        self._calc.stop()
                        break
            except asyncio.CancelledError:
                pass
            finally:
                self._moving_direction = None
                if self._calc:
                    self._position = int(round(self._calc.current_position()))
                self.async_write_ha_state()

        self._moving_task = asyncio.create_task(_run_move())

    # ------------------ Atributos Extra ------------------
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "aliases": self._aliases,
            "travelling_time_up": self._travel_up,
            "travelling_time_down": self._travel_down,
            "send_stop_at_ends": self._send_stop_at_ends,
            "always_confident": self._always_confident,
            "smart_stop_midrange": self._smart_stop_midrange,
            "current_position": self._position,
        }

        if self._open_script_id:
            attrs["open_script_entity_id"] = self._open_script_id
        if self._close_script_id:
            attrs["close_script_entity_id"] = self._close_script_id
        if self._stop_script_id:
            attrs["stop_script_entity_id"] = self._stop_script_id

        # sensores binários de contacto
        if self._close_contact_sensor_id:
            attrs["close_contact_sensor_entity_id"] = self._close_contact_sensor_id
        if self._open_contact_sensor_id:
            attrs["open_contact_sensor_entity_id"] = self._open_contact_sensor_id

        if self._last_confident_state is not None:
            attrs["position_confident"] = self._last_confident_state

        return attrs

    # ------------------ Dispatcher (serviços) ------------------
    def _matches_target_entities(self, target_entities: str | list[str] | None) -> bool:
        if not target_entities:
            return True
        if isinstance(target_entities, str):
            targets = [t.strip() for t in target_entities.split(",") if t.strip()]
        else:
            targets = [t.strip() for t in target_entities if t and isinstance(t, str)]
        return self.entity_id in targets

    def _dispatcher_set_known_position(
        self,
        target_entities: str | list[str] | None,
        position: int | float | None,
        confident: bool,
        position_type: str,
    ) -> None:
        if not self._matches_target_entities(target_entities):
            return
        if position is None:
            _LOGGER.debug("%s: posição não fornecida — ignorar.", self.entity_id)
            return
        try:
            pos_int = max(0, min(100, int(round(float(position)))))
        except (TypeError, ValueError):
            _LOGGER.debug("%s: posição inválida (%s) — ignorar.", self.entity_id, position)
            return

        self._last_confident_state = confident

        if self._calc is None:
            self._calc = TravelCalculator(self._travel_down, self._travel_up)

        if position_type == "current":
            self._calc.set_position(float(pos_int))
            self._position = int(round(self._calc.current_position()))
            self.async_write_ha_state()
            _LOGGER.debug("%s: posição atual definida para %s%% (confident=%s)", self.entity_id, pos_int, confident)
        else:
            self.hass.async_create_task(self._move_to_target(pos_int))
            _LOGGER.debug("%s: alvo de posição definido para %s%% (confident=%s)", self.entity_id, pos_int, confident)

    def _dispatcher_set_known_action(
        self,
        target_entities: str | list[str] | None,
        action: str | None,
    ) -> None:
        if not self._matches_target_entities(target_entities):
            return
        if not action:
            _LOGGER.debug("%s: ação não fornecida — ignorar.", self.entity_id)
            return

        action = str(action).lower().strip()
        if action == "open":
            self.hass.async_create_task(self.async_open_cover())
        elif action == "close":
            self.hass.async_create_task(self.async_close_cover())
        elif action == "stop":
            self.hass.async_create_task(self.async_stop_cover())
        else:
            _LOGGER.debug("%s: ação desconhecida '%s' — ignorar.", self.entity_id, action)

    # ------------------ Sensores binários (callbacks) ------------------
    async def _apply_contact_hit(self, forced_position: int, *, source_entity: Optional[str] = None) -> None:
        """Aplicar contacto: torna posição 'CONFIRMED', cancela movimento e respeita opções."""
        # cancela movimento corrente se existir
        if self._moving_task:
            self._moving_task.cancel()
            self._moving_task = None

        self._moving_direction = None

        if self._calc is None:
            self._calc = TravelCalculator(self._travel_down, self._travel_up)

        # posição confirmada por contacto
        self._calc.set_position(float(forced_position))
        self._position = forced_position
        self._last_confident_state = True

        # se estamos num extremo e opção 'stop_at_ends' estiver ativa, chama stop
        if self._send_stop_at_ends and forced_position in (0, 100):
            await self._start_stop()

        _LOGGER.debug(
            "%s: contacto '%s' -> posição conhecida = %s%%",
            self.entity_id,
            source_entity or "-",
            forced_position,
        )
        self.async_write_ha_state()

    async def _closed_contact_state_changed(self, event) -> None:
        """Quando sensor de FECHO fica 'on', posição passa a 0% conhecida."""
        new_state = event.data.get("new_state")
        if not new_state:
            return
        if str(new_state.state).lower() == "on":
            await self._apply_contact_hit(0, source_entity=self._close_contact_sensor_id)

    async def _open_contact_state_changed(self, event) -> None:
        """Quando sensor de ABERTURA fica 'on', posição passa a 100% conhecida."""
        new_state = event.data.get("new_state")
        if not new_state:
            return
        if str(new_state.state).lower() == "on":
            await self._apply_contact_hit(100, source_entity=self._open_contact_sensor_id)
