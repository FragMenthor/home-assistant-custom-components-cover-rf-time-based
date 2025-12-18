"""Cover Time Based Sync - entidade cover compatível HA 2025.10+ com temporização."""

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
    CONF_SMART_STOP,
    CONF_ALIASES
)
from .travelcalculator import TravelCalculator, TravelStatus  # [file:130]

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = 0.5  # segundos para atualizar posição
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
    """Configuração legacy via YAML (mantida para compatibilidade)."""
    devices_conf = config.get("devices", {})

    entities = []
    for device_key, device_config in devices_conf.items():
        name = device_config.get("name", device_key)
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

        _LOGGER.debug("CoverTimeBasedSyncCover init: name=%s entry_id=%s aliases=%s", name, entry_id, aliases)
        self.hass = hass
        self._position = 0.0
        self._status = "stopped"  # "open", "close", "stopped"

        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry_id}"
        self._attr_is_closed = True
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._attr_current_cover_position = int(self._position)

        self._smart_stop_enabled = options.get(
            CONF_SMART_STOP, config.get(CONF_SMART_STOP, True)
        )
        # tempos de viagem
        up = options.get(CONF_TRAVELLING_TIME_UP, config.get(CONF_TRAVELLING_TIME_UP, 25))
        down = options.get(
            CONF_TRAVELLING_TIME_DOWN, config.get(CONF_TRAVELLING_TIME_DOWN, 25)
        )
        self._travel = TravelCalculator(travel_time_down=down, travel_time_up=up)  # [file:130]

        # scripts
        self._open_script = options.get(CONF_OPEN_SCRIPT, config.get(CONF_OPEN_SCRIPT))
        self._close_script = options.get(CONF_CLOSE_SCRIPT, config.get(CONF_CLOSE_SCRIPT))
        self._stop_script = options.get(CONF_STOP_SCRIPT, config.get(CONF_STOP_SCRIPT))

        # controlo de atualização
        self._unsub_update = None
        self._target_position: int | None = None

        aliases = options.get(CONF_ALIASES, config.get(CONF_ALIASES, ""))
        self._slug = None
        if isinstance(aliases, str):
            alias = aliases.split(",")[0].strip()
            if alias:
                # normalizar para entity_id seguro
                slug = (
                    alias.lower()
                    .replace(" ", "_")
                    .replace("-", "_")
                    )
                # filtrar caracteres inválidos
                slug = "".join(c for c in slug if c.isalnum() or c == "_")
                if slug:
                    self._slug = slug

        _LOGGER.debug("CoverTimeBasedSyncCover slug gerado: %s", self._slug)

        self._attr_unique_id = f"{DOMAIN}_{entry_id}"
        if self._slug:
            self._attr_entity_id = f"{COVER_DOMAIN}.{self._slug}"
    
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
        """Atualiza atributos internos para HA mantendo evolução contínua."""
        self._attr_is_closed = self._position <= 0
        self._attr_is_opening = self._status == "open"
        self._attr_is_closing = self._status == "close"
        self._attr_current_cover_position = int(round(self._position))

    async def _async_call_script(self, script_entity_id: str | None) -> None:
        """Chama um script se definido."""
        if not script_entity_id:
            return
        domain, _, script_name = script_entity_id.partition(".")
        if domain != "script" or not script_name:
            _LOGGER.warning("ID de script inválido: %s", script_entity_id)
            return
        await self.hass.services.async_call("script", script_name, blocking=False)

    # ------------ interface padrão cover ------------

    async def async_open_cover(self, **kwargs) -> None:
        """Abrir completamente: comportamento base (até 100%)."""
        await self._async_start_move(target=100)

    async def async_close_cover(self, **kwargs) -> None:
        """Fechar completamente: comportamento base (até 0%)."""
        await self._async_start_move(target=0)

    async def async_stop_cover(self, **kwargs) -> None:
        """Parar movimento atual e chamar script de stop."""
        _LOGGER.debug("Stop manual solicitado")
        self._travel.stop()
        self._target_position = None
        if self._unsub_update:
            self._unsub_update()
            self._unsub_update = None
        await self._async_call_script(self._stop_script)
        self._position = self._travel.current_position()
        self._status = "stopped"
        self._update_state_attributes()
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs) -> None:
        """Definir posição; só gera stop automático entre 20% e 80%."""
        pos = kwargs.get("position")
        if pos is None:
            return
        target = max(0, min(100, int(pos)))
        await self._async_start_move(target=target)

    # ------------ lógica de movimento temporizado ------------

    async def _async_start_move(self, target: int) -> None:
        """Inicia movimento para um target, mantendo funcionamento base."""
        current = self._travel.current_position()
        self._position = current

        if target == current:
            _LOGGER.debug("Target igual à posição atual (%s%%), nada a fazer", target)
            return

        direction = (
            TravelStatus.OPENING if target > current else TravelStatus.CLOSING
        )  # [file:130]

        self._status = "open" if direction == TravelStatus.OPENING else "close"

        # comportamento base: chamar script de open/close e deixar o tempo correr
        if direction == TravelStatus.OPENING:
            await self._async_call_script(self._open_script)
        else:
            await self._async_call_script(self._close_script)

        # arranca TravelCalculator para este target
        self._target_position = target
        self._travel.start_moving(direction, target)  # [file:130]
        self._schedule_updates()

        self._update_state_attributes()
        self.async_write_ha_state()

    def _schedule_updates(self) -> None:
        """Agendar atualização periódica da posição."""
        if self._unsub_update is not None:
            return
        self._unsub_update = async_track_time_interval(
            self.hass,
            self._async_handle_travel_update,
            timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_handle_travel_update(self, now) -> None:
        """Atualiza posição continuamente e decide se deve enviar stop automático."""
        pos = self._travel.current_position()  # calcula posição em função do tempo [file:130]
        self._position = pos
        self._update_state_attributes()
        self.async_write_ha_state()

        # Verificar se o TravelCalculator parou (chegou ao target ou aos limites)
        if self._travel._direction == TravelStatus.STOPPED:
            # cancela callback periódico
            if self._unsub_update:
                self._unsub_update()
                self._unsub_update = None

            # lógica de stop automático apenas se:
            # - há target definido, e
            # - o target está entre 20% e 80%
            if (
                self._smart_stop_enabled
                and self._target_position is not None
                and MIN_SMART_POS <= self._target_position <= MAX_SMART_POS
            ):
                _LOGGER.debug(
                    "Target %s%% atingido (posição %.1f%%), a chamar script de stop",
                    self._target_position,
                    pos,
                )
                await self._async_call_script(self._stop_script)
            else:
                _LOGGER.debug(
                    "Movimento terminou em %.1f%% sem stop automático (target=%s)",
                    pos,
                    self._target_position,
                )

            self._target_position = None
            self._status = "stopped"
            self._update_state_attributes()
            self.async_write_ha_state()

    # ------------ serviços internos da integração ------------

    async def async_set_known_position(self, **kwargs) -> None:
        """Ajuste manual de posição (sem mexer em scripts)."""
        val = kwargs.get(ATTR_POSITION, self._position)
        self._position = max(0, min(100, float(val)))
        self._travel._position = self._position
        self._travel._direction = TravelStatus.STOPPED
        self._travel._start_time = None
        self._status = "stopped"
        self._target_position = None
        self._update_state_attributes()
        self.async_write_ha_state()

    async def async_set_known_action(self, **kwargs) -> None:
        """Ação manual conhecida: open / close / stop."""
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
