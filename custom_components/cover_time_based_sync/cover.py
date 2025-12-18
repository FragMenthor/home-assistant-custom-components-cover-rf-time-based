"""Cover Time Based Sync - entidade cover compatível HA 2025.10+ com controlo temporal."""

import logging
from datetime import timedelta

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    ATTR_POSITION,
    ATTR_ACTION,
    CONF_TRAVELLING_TIME_UP,
    CONF_TRAVELLING_TIME_DOWN,
    CONF_OPEN_SCRIPT,
    CONF_CLOSE_SCRIPT,
    CONF_STOP_SCRIPT,
)

from .travelcalculator import TravelCalculator, TravelStatus

_LOGGER = logging.getLogger(__name__)

# intervalo de atualização do movimento (segundos)
UPDATE_INTERVAL = 0.5

# intervalo em que queremos comportamento “inteligente”
MIN_SMART_POS = 20
MAX_SMART_POS = 80


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configura entidade(s) a partir de uma config entry."""
    data = entry.data
    name = data.get("name", "Cover Time Based Sync")

    entity = CoverTimeBasedSyncCover(
        hass=hass,
        name=name,
        entry_id=entry.entry_id,
        config=data,
        options=entry.options,
    )

    async_add_entities([entity])


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Configuração legacy via YAML (mantida para compatibilidade simples)."""
    devices_conf = config.get("devices", {})

    entities = []
    for device_key, device_config in devices_conf.items():
        name = device_config.get("name", device_key)
        # Para YAML não temos scripts, nem travel time por options;
        # valores default razoáveis.
        yaml_conf = {
            CONF_TRAVELLING_TIME_UP: device_config.get("travelling_time_up", 25),
            CONF_TRAVELLING_TIME_DOWN: device_config.get("travelling_time_down", 25),
            CONF_OPEN_SCRIPT: device_config.get(CONF_OPEN_SCRIPT),
            CONF_CLOSE_SCRIPT: device_config.get(CONF_CLOSE_SCRIPT),
            CONF_STOP_SCRIPT: device_config.get(CONF_STOP_SCRIPT),
        }
        entities.append(
            CoverTimeBasedSyncCover(
                hass=hass,
                name=name,
                entry_id=device_key,
                config=yaml_conf,
                options={},
            )
        )

    async_add_entities(entities)


class CoverTimeBasedSyncCover(RestoreEntity, CoverEntity):
    """Entidade cover RF Time Based compatível HA 2025.10+ com TravelCalculator."""

    has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        entry_id: str,
        config: dict,
        options: dict,
    ) -> None:
        self.hass = hass
        self._position = 0
        self._status = "stopped"  # "open", "close", "stopped"

        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry_id}"
        self._attr_is_closed = True
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._attr_current_cover_position = self._position

        # ler tempos do config/option
        up = options.get(CONF_TRAVELLING_TIME_UP, config.get(CONF_TRAVELLING_TIME_UP, 25))
        down = options.get(
            CONF_TRAVELLING_TIME_DOWN, config.get(CONF_TRAVELLING_TIME_DOWN, 25)
        )
        self._travel = TravelCalculator(travel_time_down=down, travel_time_up=up)

        # scripts
        self._open_script = options.get(CONF_OPEN_SCRIPT, config.get(CONF_OPEN_SCRIPT))
        self._close_script = options.get(CONF_CLOSE_SCRIPT, config.get(CONF_CLOSE_SCRIPT))
        self._stop_script = options.get(CONF_STOP_SCRIPT, config.get(CONF_STOP_SCRIPT))

        # listener periódico
        self._unsub_update = None
        self._smart_target = None  # guarda target para posições 20–80

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

    def _update_state_attributes(self) -> None:
        """Atualiza atributos internos para HA."""
        self._attr_is_closed = self._position <= 0
        self._attr_is_opening = self._status == "open"
        self._attr_is_closing = self._status == "close"
        self._attr_current_cover_position = int(round(self._position))

    async def _async_call_script(self, script_entity_id: str | None) -> None:
        """Chama um script se definido."""
        if not script_entity_id:
            return
        _LOGGER.debug("A chamar script %s", script_entity_id)
        await self.hass.services.async_call(
            "script",
            script_entity_id.split(".", 1)[1],
            blocking=False,
        )

    async def async_open_cover(self, **kwargs) -> None:
        """Abre totalmente (100%)."""
        await self.async_set_cover_position(position=100)

    async def async_close_cover(self, **kwargs) -> None:
        """Fecha totalmente (0%)."""
        await self.async_set_cover_position(position=0)

    async def async_stop_cover(self, **kwargs) -> None:
        """Para o movimento atual e chama o script de stop."""
        _LOGGER.debug("Parar movimento pedido manualmente")
        self._travel.stop()
        if self._unsub_update:
            self._unsub_update()
            self._unsub_update = None
        self._status = "stopped"
        self._smart_target = None
        await self._async_call_script(self._stop_script)
        self._position = self._travel.current_position()
        self._update_state_attributes()
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs) -> None:
        """Define a posição, com controlo temporal entre 20% e 80%."""
        target = kwargs.get("position")
        if target is None:
            return

        target = max(0, min(100, int(target)))
        _LOGGER.debug("Pedido de posição: %s%%", target)

        current = self._travel.current_position()
        self._position = current

        # fora da zona “inteligente”: atualizar direto
        if target < MIN_SMART_POS or target > MAX_SMART_POS:
            _LOGGER.debug(
                "Target fora de [%s,%s]%%, ajuste direto de estado.",
                MIN_SMART_POS,
                MAX_SMART_POS,
            )
            self._position = target
            self._status = "stopped"
            self._travel._position = target  # manter coerência interna
            self._travel._direction = TravelStatus.STOPPED
            self._travel._start_time = None
            self._update_state_attributes()
            self.async_write_ha_state()
            return

        # dentro de 20–80%: usar TravelCalculator e scripts
        direction = (
            TravelStatus.OPENING if target > current else TravelStatus.CLOSING
        )
        self._status = "open" if direction == TravelStatus.OPENING else "close"
        self._smart_target = target

        # chama script de movimento adequado
        if direction == TravelStatus.OPENING:
            await self._async_call_script(self._open_script)
        else:
            await self._async_call_script(self._close_script)

        self._travel.start_moving(direction, target)
        self._schedule_updates()
        self._update_state_attributes()
        self.async_write_ha_state()

    def _schedule_updates(self) -> None:
        """Agendar atualização periódica da posição."""
        if self._unsub_update is not None:
            return

        self._unsub_update = async_track_time_interval(
            self.hass, self._async_handle_travel_update, timedelta(seconds=UPDATE_INTERVAL)
        )

    async def _async_handle_travel_update(self, now) -> None:
        """Callback periódico para atualizar posição e parar no target."""
        pos = self._travel.current_position()
        self._position = pos
        self._update_state_attributes()
        self.async_write_ha_state()

        # se TravelCalculator parou, chegámos (aprox.) ao target
        if self._travel._direction == TravelStatus.STOPPED:
            _LOGGER.debug("TravelCalculator parou em %s%%", pos)
            if self._unsub_update:
                self._unsub_update()
                self._unsub_update = None

            # só chamar stop automaticamente se estávamos num movimento “smart”
            if self._smart_target is not None:
                await self._async_call_script(self._stop_script)
            self._smart_target = None
            self._status = "stopped"
            self._update_state_attributes()
            self.async_write_ha_state()

    async def async_set_known_position(self, **kwargs) -> None:
        """Serviço interno: set_known_position (ajuste manual)."""
        self._position = kwargs.get(ATTR_POSITION, self._position)
        self._travel._position = self._position
        self._travel._direction = TravelStatus.STOPPED
        self._travel._start_time = None
        self._status = "stopped"
        self._smart_target = None
        self._update_state_attributes()
        self.async_write_ha_state()

    async def async_set_known_action(self, **kwargs) -> None:
        """Serviço interno: set_known_action (open/close/stop manual)."""
        action = kwargs.get(ATTR_ACTION)
        _LOGGER.debug("Ação conhecida recebida: %s", action)

        if action == "open":
            await self.async_open_cover()
        elif action == "close":
            await self.async_close_cover()
        elif action == "stop":
            await self.async_stop_cover()
        else:
            _LOGGER.warning("Ação desconhecida recebida: %s", action)
