"""Config flow para Cover Time Based Sync com modo 'Controlo Único' (RF)."""
from __future__ import annotations
from typing import Any, Dict
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
    ConfigFlowResult,
)
from homeassistant.helpers import selector

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
    CONF_OPEN_CONTACT_SENSOR,
    CONF_CLOSE_CONTACT_SENSOR,
    CONF_SINGLE_CONTROL_ENABLED,
    CONF_SINGLE_CONTROL_PULSE_MS,
)

DEFAULT_TRAVEL_TIME = 25
DEFAULT_PULSE_MS = 2500


def _first_script(data: dict[str, Any]) -> str | None:
    """Devolve o primeiro script definido (open -> close -> stop)."""
    for key in (CONF_OPEN_SCRIPT, CONF_CLOSE_SCRIPT, CONF_STOP_SCRIPT):
        val = data.get(key)
        if isinstance(val, str) and val:
            return val
    return None


def _entity_optional(
    schema_dict: Dict[Any, Any],
    key: str,
    current_value: str | None,
    domain: str,
) -> None:
    """Adiciona um selector de entidade opcional ao schema, sem default=None."""
    sel = selector.EntitySelector(selector.EntitySelectorConfig(domain=domain))
    if isinstance(current_value, str) and current_value:
        schema_dict[vol.Optional(key, default=current_value)] = sel
    else:
        schema_dict[vol.Optional(key)] = sel


class CoverTimeBasedSyncFlowHandler(ConfigFlow, domain=DOMAIN):
    """Fluxo de configuração para Cover Time Based Sync."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Passo 1: escolher modo (Controlo Único ON/OFF) e atraso de pulsos."""
        if user_input is not None:
            single = bool(user_input.get(CONF_SINGLE_CONTROL_ENABLED, False))
            # guardar para passo seguinte
            self._pulse_ms = int(user_input.get(CONF_SINGLE_CONTROL_PULSE_MS, DEFAULT_PULSE_MS))
            if single:
                return await self.async_step_single()
            return await self.async_step_multi()

        schema = vol.Schema({
            vol.Optional(CONF_SINGLE_CONTROL_ENABLED, default=False): bool,
            vol.Optional(CONF_SINGLE_CONTROL_PULSE_MS, default=DEFAULT_PULSE_MS): int,
        })
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_single(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Passo 2A: formulário para Controlo Único (um só script RF)."""
        if user_input is not None:
            if not _first_script(user_input):
                return self.async_show_form(
                    step_id="single",
                    data_schema=self._schema_single(defaults=user_input),
                    errors={"base": "single_control_requires_script"},
                )
            data = dict(user_input)
            data[CONF_SINGLE_CONTROL_ENABLED] = True
            data[CONF_SINGLE_CONTROL_PULSE_MS] = getattr(self, "_pulse_ms", DEFAULT_PULSE_MS)
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, "Cover Time Based Sync"),
                data=data,
            )
        return self.async_show_form(step_id="single", data_schema=self._schema_single())

    async def async_step_multi(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Passo 2B: formulário normal (três scripts)."""
        if user_input is not None:
            data = dict(user_input)
            data[CONF_SINGLE_CONTROL_ENABLED] = False
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, "Cover Time Based Sync"),
                data=data,
            )
        return self.async_show_form(step_id="multi", data_schema=self._schema_multi())

    # ----------- Schemas -----------
    def _schema_single(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        d = defaults or {}
        sch: Dict[Any, Any] = {
            vol.Required(CONF_NAME, default=d.get(CONF_NAME, "")): str,
            vol.Required(CONF_TRAVELLING_TIME_UP, default=d.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)): int,
            vol.Required(CONF_TRAVELLING_TIME_DOWN, default=d.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)): int,
            vol.Optional(CONF_SEND_STOP_AT_ENDS, default=d.get(CONF_SEND_STOP_AT_ENDS, False)): bool,
            vol.Optional(CONF_SMART_STOP, default=d.get(CONF_SMART_STOP, False)): bool,
            vol.Optional(CONF_ALWAYS_CONFIDENT, default=d.get(CONF_ALWAYS_CONFIDENT, False)): bool,
        }
        # Script único (RF pulsar) — usa-se o primeiro script fornecido
        _entity_optional(sch, CONF_OPEN_SCRIPT, d.get(CONF_OPEN_SCRIPT), "script")
        # Sensores binários (opcionais)
        _entity_optional(sch, CONF_CLOSE_CONTACT_SENSOR, d.get(CONF_CLOSE_CONTACT_SENSOR), "binary_sensor")
        _entity_optional(sch, CONF_OPEN_CONTACT_SENSOR, d.get(CONF_OPEN_CONTACT_SENSOR), "binary_sensor")
        return vol.Schema(sch)

    def _schema_multi(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        d = defaults or {}
        sch: Dict[Any, Any] = {
            vol.Required(CONF_NAME, default=d.get(CONF_NAME, "")): str,
            vol.Required(CONF_TRAVELLING_TIME_UP, default=d.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)): int,
            vol.Required(CONF_TRAVELLING_TIME_DOWN, default=d.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)): int,
            vol.Optional(CONF_SEND_STOP_AT_ENDS, default=d.get(CONF_SEND_STOP_AT_ENDS, False)): bool,
            vol.Optional(CONF_SMART_STOP, default=d.get(CONF_SMART_STOP, False)): bool,
            vol.Optional(CONF_ALWAYS_CONFIDENT, default=d.get(CONF_ALWAYS_CONFIDENT, False)): bool,
        }
        # Três scripts (opcionais)
        _entity_optional(sch, CONF_OPEN_SCRIPT, d.get(CONF_OPEN_SCRIPT), "script")
        _entity_optional(sch, CONF_CLOSE_SCRIPT, d.get(CONF_CLOSE_SCRIPT), "script")
        _entity_optional(sch, CONF_STOP_SCRIPT, d.get(CONF_STOP_SCRIPT), "script")
        # Sensores binários (opcionais)
        _entity_optional(sch, CONF_CLOSE_CONTACT_SENSOR, d.get(CONF_CLOSE_CONTACT_SENSOR), "binary_sensor")
        _entity_optional(sch, CONF_OPEN_CONTACT_SENSOR, d.get(CONF_OPEN_CONTACT_SENSOR), "binary_sensor")
        return vol.Schema(sch)

    # ----------- Reconfigure -----------
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigurar dados, compatível com várias versões de HA."""
        # Helper novo (>= 2024.10): _get_reconfigure_entry()
        entry_getter = getattr(self, "_get_reconfigure_entry", None)
        if callable(entry_getter):
            entry = self._get_reconfigure_entry()
        else:
            # Fallback: obter entry via contexto (versões mais antigas)
            entry_id = (self.context or {}).get("entry_id")
            if not entry_id:
                return self.async_abort(reason="unknown_entry")
            entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            return self.async_abort(reason="unknown_entry")

        single = bool(entry.data.get(CONF_SINGLE_CONTROL_ENABLED, False))

        if user_input:
            if single and not _first_script(user_input):
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self._schema_reconfigure(entry, user_input),
                    errors={"base": "single_control_requires_script"},
                )

            # Atualiza e recarrega (helper novo) ou fallback manual
            updater = getattr(self, "async_update_reload_and_abort", None)
            if callable(updater):
                return self.async_update_reload_and_abort(entry, data_updates=user_input)

            # Fallback manual:
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, **user_input}
            )
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._schema_reconfigure(entry),
            errors={},
        )

    def _schema_reconfigure(
        self, entry: ConfigEntry, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        d = defaults or entry.data
        single = bool(entry.data.get(CONF_SINGLE_CONTROL_ENABLED, False))
        sch: Dict[Any, Any] = {
            vol.Required(CONF_TRAVELLING_TIME_UP, default=d.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)): int,
            vol.Required(CONF_TRAVELLING_TIME_DOWN, default=d.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)): int,
            vol.Optional(CONF_SEND_STOP_AT_ENDS, default=d.get(CONF_SEND_STOP_AT_ENDS, False)): bool,
            vol.Optional(CONF_ALWAYS_CONFIDENT, default=d.get(CONF_ALWAYS_CONFIDENT, False)): bool,
            vol.Optional(CONF_SMART_STOP, default=d.get(CONF_SMART_STOP, False)): bool,
        }

        if single:
            _entity_optional(sch, CONF_OPEN_SCRIPT, d.get(CONF_OPEN_SCRIPT), "script")
            _entity_optional(sch, CONF_CLOSE_CONTACT_SENSOR, d.get(CONF_CLOSE_CONTACT_SENSOR), "binary_sensor")
            _entity_optional(sch, CONF_OPEN_CONTACT_SENSOR, d.get(CONF_OPEN_CONTACT_SENSOR), "binary_sensor")
            sch[vol.Optional(CONF_SINGLE_CONTROL_PULSE_MS, default=d.get(CONF_SINGLE_CONTROL_PULSE_MS, DEFAULT_PULSE_MS))] = int
        else:
            _entity_optional(sch, CONF_OPEN_SCRIPT, d.get(CONF_OPEN_SCRIPT), "script")
            _entity_optional(sch, CONF_CLOSE_SCRIPT, d.get(CONF_CLOSE_SCRIPT), "script")
            _entity_optional(sch, CONF_STOP_SCRIPT, d.get(CONF_STOP_SCRIPT), "script")
            _entity_optional(sch, CONF_CLOSE_CONTACT_SENSOR, d.get(CONF_CLOSE_CONTACT_SENSOR), "binary_sensor")
            _entity_optional(sch, CONF_OPEN_CONTACT_SENSOR, d.get(CONF_OPEN_CONTACT_SENSOR), "binary_sensor")

        return vol.Schema(sch)

    # ----------- Options Flow -----------
    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Criar o Options Flow (padrão atual: sem passar config_entry)."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Gestão de opções com UX adaptativa por modo (compatível com HA recente)."""

    def __init__(self) -> None:
        # Em HA recente, self.config_entry é injetado automaticamente.
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry: ConfigEntry = self.config_entry
        single = bool(entry.data.get(CONF_SINGLE_CONTROL_ENABLED, False))
        data = entry.data
        options = entry.options

        if user_input is not None:
            if single and not _first_script(user_input):
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._schema_options(single, options=user_input, data=data),
                    errors={"base": "single_control_requires_script"},
                )
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self._schema_options(single, options=options, data=data),
        )

    def _schema_options(
        self,
        single: bool,
        options: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> vol.Schema:
        o = options or {}
        d = data or {}
        sch: Dict[Any, Any] = {
            vol.Required(CONF_TRAVELLING_TIME_UP, default=o.get(CONF_TRAVELLING_TIME_UP, d.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME))): int,
            vol.Required(CONF_TRAVELLING_TIME_DOWN, default=o.get(CONF_TRAVELLING_TIME_DOWN, d.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME))): int,
            vol.Optional(CONF_SEND_STOP_AT_ENDS, default=o.get(CONF_SEND_STOP_AT_ENDS, d.get(CONF_SEND_STOP_AT_ENDS, False))): bool,
            vol.Optional(CONF_ALWAYS_CONFIDENT, default=o.get(CONF_ALWAYS_CONFIDENT, d.get(CONF_ALWAYS_CONFIDENT, False))): bool,
            vol.Optional(CONF_SMART_STOP, default=o.get(CONF_SMART_STOP, d.get(CONF_SMART_STOP, False))): bool,
        }

        if single:
            _entity_optional(sch, CONF_OPEN_SCRIPT, o.get(CONF_OPEN_SCRIPT, d.get(CONF_OPEN_SCRIPT)), "script")
            _entity_optional(sch, CONF_CLOSE_CONTACT_SENSOR, o.get(CONF_CLOSE_CONTACT_SENSOR, d.get(CONF_CLOSE_CONTACT_SENSOR)), "binary_sensor")
            _entity_optional(sch, CONF_OPEN_CONTACT_SENSOR, o.get(CONF_OPEN_CONTACT_SENSOR, d.get(CONF_OPEN_CONTACT_SENSOR)), "binary_sensor")
            sch[vol.Optional(CONF_SINGLE_CONTROL_PULSE_MS, default=o.get(CONF_SINGLE_CONTROL_PULSE_MS, d.get(CONF_SINGLE_CONTROL_PULSE_MS, DEFAULT_PULSE_MS)))] = int
        else:
            _entity_optional(sch, CONF_OPEN_SCRIPT, o.get(CONF_OPEN_SCRIPT, d.get(CONF_OPEN_SCRIPT)), "script")
            _entity_optional(sch, CONF_CLOSE_SCRIPT, o.get(CONF_CLOSE_SCRIPT, d.get(CONF_CLOSE_SCRIPT)), "script")
            _entity_optional(sch, CONF_STOP_SCRIPT, o.get(CONF_STOP_SCRIPT, d.get(CONF_STOP_SCRIPT)), "script")
            _entity_optional(sch, CONF_CLOSE_CONTACT_SENSOR, o.get(CONF_CLOSE_CONTACT_SENSOR, d.get(CONF_CLOSE_CONTACT_SENSOR)), "binary_sensor")
            _entity_optional(sch, CONF_OPEN_CONTACT_SENSOR, o.get(CONF_OPEN_CONTACT_SENSOR, d.get(CONF_OPEN_CONTACT_SENSOR)), "binary_sensor")

        return vol.Schema(sch)
