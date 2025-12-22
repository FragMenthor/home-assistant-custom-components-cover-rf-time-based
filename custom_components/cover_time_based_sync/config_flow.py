"""Config flow para Cover Time Based Sync."""
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
    CONF_ALIASES,
    CONF_ALWAYS_CONFIDENT,
    CONF_SMART_STOP,
    CONF_OPEN_CONTACT_SENSOR,
    CONF_CLOSE_CONTACT_SENSOR,
    # Controlo Único
    CONF_SINGLE_CONTROL_ENABLED,
    CONF_SINGLE_CONTROL_PULSE_MS,
)

DEFAULT_TRAVEL_TIME = 25
DEFAULT_PULSE_MS = 400


def _first_script(data: dict[str, Any]) -> str | None:
    """Devolve o primeiro script definido (open → close → stop)."""
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
    """
    Adiciona um selector de entidade opcional ao schema.
    - Se houver valor (string), usa default=<valor>.
    - Se não houver, não define default (evita 'Entity None ...').
    """
    sel = selector.EntitySelector(selector.EntitySelectorConfig(domain=domain))
    if isinstance(current_value, str) and current_value:
        schema_dict[vol.Optional(key, default=current_value)] = sel
    else:
        schema_dict[vol.Optional(key)] = sel


class CoverTimeBasedSyncFlowHandler(ConfigFlow, domain=DOMAIN):
    """Fluxo de configuração para Cover Time Based Sync."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Primeiro passo (criação)."""
        if user_input is not None:
            # Validação mínima para Controlo Único
            if user_input.get(CONF_SINGLE_CONTROL_ENABLED):
                if _first_script(user_input) is None:
                    # Falta pelo menos um script; mostrar erro traduzível
                    return self.async_show_form(
                        step_id="user",
                        data_schema=self._schema_user(defaults=user_input),
                        errors={"base": "single_control_requires_script"},
                    )
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(step_id="user", data_schema=self._schema_user())

    def _schema_user(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        d = defaults or {}
        schema_dict: Dict[Any, Any] = {
            vol.Required(CONF_NAME, default=d.get(CONF_NAME, "")): str,
            vol.Required(CONF_TRAVELLING_TIME_UP, default=d.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)): int,
            vol.Required(CONF_TRAVELLING_TIME_DOWN, default=d.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)): int,
            vol.Optional(CONF_SINGLE_CONTROL_ENABLED, default=d.get(CONF_SINGLE_CONTROL_ENABLED, False)): bool,
            vol.Optional(CONF_SINGLE_CONTROL_PULSE_MS, default=d.get(CONF_SINGLE_CONTROL_PULSE_MS, DEFAULT_PULSE_MS)): int,
            vol.Optional(CONF_SEND_STOP_AT_ENDS, default=d.get(CONF_SEND_STOP_AT_ENDS, False)): bool,
            vol.Optional(CONF_SMART_STOP, default=d.get(CONF_SMART_STOP, False)): bool,
            vol.Optional(CONF_ALWAYS_CONFIDENT, default=d.get(CONF_ALWAYS_CONFIDENT, False)): bool,
            vol.Optional(CONF_ALIASES, default=d.get(CONF_ALIASES, "")): str,
        }

        # Scripts (opcionais) – sem default=None
        _entity_optional(schema_dict, CONF_OPEN_SCRIPT, d.get(CONF_OPEN_SCRIPT), "script")
        _entity_optional(schema_dict, CONF_CLOSE_SCRIPT, d.get(CONF_CLOSE_SCRIPT), "script")
        _entity_optional(schema_dict, CONF_STOP_SCRIPT, d.get(CONF_STOP_SCRIPT), "script")

        # Sensores binários (opcionais) – sem default=None
        _entity_optional(schema_dict, CONF_CLOSE_CONTACT_SENSOR, d.get(CONF_CLOSE_CONTACT_SENSOR), "binary_sensor")
        _entity_optional(schema_dict, CONF_OPEN_CONTACT_SENSOR, d.get(CONF_OPEN_CONTACT_SENSOR), "binary_sensor")

        return vol.Schema(schema_dict)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Reconfigurar dados."""
        entry = self._get_reconfigure_entry()
        if user_input:
            if user_input.get(CONF_SINGLE_CONTROL_ENABLED) and _first_script(user_input) is None:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self._schema_reconfigure(entry, user_input),
                    errors={"base": "single_control_requires_script"},
                )
            return self.async_update_reload_and_abort(entry, data_updates=user_input)

        return self.async_show_form(step_id="reconfigure", data_schema=self._schema_reconfigure(entry), errors={})

    def _schema_reconfigure(self, entry: ConfigEntry, defaults: dict[str, Any] | None = None) -> vol.Schema:
        d = defaults or entry.data
        schema_dict: Dict[Any, Any] = {
            vol.Required(CONF_TRAVELLING_TIME_UP, default=d.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)): int,
            vol.Required(CONF_TRAVELLING_TIME_DOWN, default=d.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)): int,
            vol.Optional(CONF_SINGLE_CONTROL_ENABLED, default=d.get(CONF_SINGLE_CONTROL_ENABLED, False)): bool,
            vol.Optional(CONF_SINGLE_CONTROL_PULSE_MS, default=d.get(CONF_SINGLE_CONTROL_PULSE_MS, DEFAULT_PULSE_MS)): int,
            vol.Optional(CONF_SEND_STOP_AT_ENDS, default=d.get(CONF_SEND_STOP_AT_ENDS, False)): bool,
            vol.Optional(CONF_ALWAYS_CONFIDENT, default=d.get(CONF_ALWAYS_CONFIDENT, False)): bool,
            vol.Optional(CONF_SMART_STOP, default=d.get(CONF_SMART_STOP, False)): bool,
            vol.Optional(CONF_ALIASES, default=d.get(CONF_ALIASES, "")): str,
        }

        _entity_optional(schema_dict, CONF_OPEN_SCRIPT, d.get(CONF_OPEN_SCRIPT), "script")
        _entity_optional(schema_dict, CONF_CLOSE_SCRIPT, d.get(CONF_CLOSE_SCRIPT), "script")
        _entity_optional(schema_dict, CONF_STOP_SCRIPT, d.get(CONF_STOP_SCRIPT), "script")

        _entity_optional(schema_dict, CONF_CLOSE_CONTACT_SENSOR, d.get(CONF_CLOSE_CONTACT_SENSOR), "binary_sensor")
        _entity_optional(schema_dict, CONF_OPEN_CONTACT_SENSOR, d.get(CONF_OPEN_CONTACT_SENSOR), "binary_sensor")

        return vol.Schema(schema_dict)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Gestão de opções."""

    def __init__(self) -> None:
        super().__init__()

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        data = self.config_entry.data
        options = self.config_entry.options

        def _get(key: str, default=None):
            return options.get(key, data.get(key, default))

        if user_input is not None:
            if user_input.get(CONF_SINGLE_CONTROL_ENABLED) and _first_script(user_input) is None:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._schema(options=user_input),
                    errors={"base": "single_control_requires_script"},
                )
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=self._schema(options=options, data=data))

    def _schema(self, options: dict[str, Any] | None = None, data: dict[str, Any] | None = None) -> vol.Schema:
        o = options or {}
        d = data or {}

        schema_dict: Dict[Any, Any] = {
            vol.Required(CONF_TRAVELLING_TIME_UP, default=o.get(CONF_TRAVELLING_TIME_UP, d.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME))): int,
            vol.Required(CONF_TRAVELLING_TIME_DOWN, default=o.get(CONF_TRAVELLING_TIME_DOWN, d.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME))): int,
            vol.Optional(CONF_SINGLE_CONTROL_ENABLED, default=o.get(CONF_SINGLE_CONTROL_ENABLED, d.get(CONF_SINGLE_CONTROL_ENABLED, False))): bool,
            vol.Optional(CONF_SINGLE_CONTROL_PULSE_MS, default=o.get(CONF_SINGLE_CONTROL_PULSE_MS, d.get(CONF_SINGLE_CONTROL_PULSE_MS, DEFAULT_PULSE_MS))): int,
            vol.Optional(CONF_SEND_STOP_AT_ENDS, default=o.get(CONF_SEND_STOP_AT_ENDS, d.get(CONF_SEND_STOP_AT_ENDS, False))): bool,
            vol.Optional(CONF_ALWAYS_CONFIDENT, default=o.get(CONF_ALWAYS_CONFIDENT, d.get(CONF_ALWAYS_CONFIDENT, False))): bool,
            vol.Optional(CONF_SMART_STOP, default=o.get(CONF_SMART_STOP, d.get(CONF_SMART_STOP, False))): bool,
            vol.Optional(CONF_ALIASES, default=o.get(CONF_ALIASES, d.get(CONF_ALIASES, ""))): str,
        }

        # Entity selectors opcionais — apenas com default se houver valor
        _entity_optional(schema_dict, CONF_OPEN_SCRIPT, o.get(CONF_OPEN_SCRIPT, d.get(CONF_OPEN_SCRIPT)), "script")
        _entity_optional(schema_dict, CONF_CLOSE_SCRIPT, o.get(CONF_CLOSE_SCRIPT, d.get(CONF_CLOSE_SCRIPT)), "script")
        _entity_optional(schema_dict, CONF_STOP_SCRIPT, o.get(CONF_STOP_SCRIPT, d.get(CONF_STOP_SCRIPT)), "script")

        _entity_optional(schema_dict, CONF_CLOSE_CONTACT_SENSOR, o.get(CONF_CLOSE_CONTACT_SENSOR, d.get(CONF_CLOSE_CONTACT_SENSOR)), "binary_sensor")
        _entity_optional(schema_dict, CONF_OPEN_CONTACT_SENSOR, o.get(CONF_OPEN_CONTACT_SENSOR, d.get(CONF_OPEN_CONTACT_SENSOR)), "binary_sensor")

        return vol.Schema(schema_dict)
