# custom_components/cover_time_based_sync/config_flow.py
"""Config flow para Cover Time Based Sync."""
from __future__ import annotations

from typing import Any
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


class CoverTimeBasedSyncFlowHandler(ConfigFlow, domain=DOMAIN):
    """Fluxo de configuração para Cover Time Based Sync."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Primeiro passo (criação)."""
        if user_input is not None:
            # Validação mínima para Controlo Único
            if user_input.get(CONF_SINGLE_CONTROL_ENABLED):
                if _first_script(user_input) is None:
                    # Falta pelo menos um script; mostrar erro
                    return self.async_show_form(
                        step_id="user",
                        data_schema=self._schema_user(defaults=user_input),
                        errors={"base": "single_control_requires_script"},
                    )
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(step_id="user", data_schema=self._schema_user())

    def _schema_user(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        d = defaults or {}
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default=d.get(CONF_NAME, "")): str,
                vol.Required(CONF_TRAVELLING_TIME_UP, default=d.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)): int,
                vol.Required(CONF_TRAVELLING_TIME_DOWN, default=d.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)): int,

                # Scripts
                vol.Optional(CONF_OPEN_SCRIPT, default=d.get(CONF_OPEN_SCRIPT)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(CONF_CLOSE_SCRIPT, default=d.get(CONF_CLOSE_SCRIPT)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(CONF_STOP_SCRIPT, default=d.get(CONF_STOP_SCRIPT)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),

                # Sensores binários
                vol.Optional(CONF_CLOSE_CONTACT_SENSOR, default=d.get(CONF_CLOSE_CONTACT_SENSOR)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(CONF_OPEN_CONTACT_SENSOR, default=d.get(CONF_OPEN_CONTACT_SENSOR)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),

                # Controlo Único
                vol.Optional(CONF_SINGLE_CONTROL_ENABLED, default=d.get(CONF_SINGLE_CONTROL_ENABLED, False)): bool,
                vol.Optional(CONF_SINGLE_CONTROL_PULSE_MS, default=d.get(CONF_SINGLE_CONTROL_PULSE_MS, DEFAULT_PULSE_MS)): int,

                # Comportamentos
                vol.Optional(CONF_SEND_STOP_AT_ENDS, default=d.get(CONF_SEND_STOP_AT_ENDS, False)): bool,
                vol.Optional(CONF_SMART_STOP, default=d.get(CONF_SMART_STOP, False)): bool,
                vol.Optional(CONF_ALWAYS_CONFIDENT, default=d.get(CONF_ALWAYS_CONFIDENT, False)): bool,
                vol.Optional(CONF_ALIASES, default=d.get(CONF_ALIASES, "")): str,
            }
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Reconfigurar dados."""
        entry = self._get_reconfigure_entry()
        if user_input:
            if user_input.get(CONF_SINGLE_CONTROL_ENABLED) and _first_script(user_input) is None:
                return self.async_show_form(step_id="reconfigure", data_schema=self._schema_reconfigure(entry, user_input),
                                            errors={"base": "single_control_requires_script"})
            return self.async_update_reload_and_abort(entry, data_updates=user_input)

        return self.async_show_form(step_id="reconfigure", data_schema=self._schema_reconfigure(entry), errors={})

    def _schema_reconfigure(self, entry: ConfigEntry, defaults: dict[str, Any] | None = None) -> vol.Schema:
        d = defaults or entry.data
        return vol.Schema(
            {
                vol.Required(CONF_TRAVELLING_TIME_UP, default=d.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)): int,
                vol.Required(CONF_TRAVELLING_TIME_DOWN, default=d.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)): int,

                vol.Optional(CONF_OPEN_SCRIPT, default=d.get(CONF_OPEN_SCRIPT)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(CONF_CLOSE_SCRIPT, default=d.get(CONF_CLOSE_SCRIPT)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(CONF_STOP_SCRIPT, default=d.get(CONF_STOP_SCRIPT)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),

                vol.Optional(CONF_CLOSE_CONTACT_SENSOR, default=d.get(CONF_CLOSE_CONTACT_SENSOR)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(CONF_OPEN_CONTACT_SENSOR, default=d.get(CONF_OPEN_CONTACT_SENSOR)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),

                vol.Optional(CONF_SINGLE_CONTROL_ENABLED, default=d.get(CONF_SINGLE_CONTROL_ENABLED, False)): bool,
                vol.Optional(CONF_SINGLE_CONTROL_PULSE_MS, default=d.get(CONF_SINGLE_CONTROL_PULSE_MS, DEFAULT_PULSE_MS)): int,

                vol.Optional(CONF_SEND_STOP_AT_ENDS, default=d.get(CONF_SEND_STOP_AT_ENDS, False)): bool,
                vol.Optional(CONF_ALWAYS_CONFIDENT, default=d.get(CONF_ALWAYS_CONFIDENT, False)): bool,
                vol.Optional(CONF_SMART_STOP, default=d.get(CONF_SMART_STOP, False)): bool,
                vol.Optional(CONF_ALIASES, default=d.get(CONF_ALIASES, "")): str,
            }
        )

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
                return self.async_show_form(step_id="init", data_schema=self._schema(options=user_input),
                                            errors={"base": "single_control_requires_script"})
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=self._schema(options=options, data=data))

    def _schema(self, options: dict[str, Any] | None = None, data: dict[str, Any] | None = None) -> vol.Schema:
        o = options or {}
        d = data or {}
        def get(key, default=None): return o.get(key, d.get(key, default))

        return vol.Schema(
            {
                vol.Required(CONF_TRAVELLING_TIME_UP, default=get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)): int,
                vol.Required(CONF_TRAVELLING_TIME_DOWN, default=get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)): int,

                vol.Optional(CONF_OPEN_SCRIPT, default=get(CONF_OPEN_SCRIPT)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(CONF_CLOSE_SCRIPT, default=get(CONF_CLOSE_SCRIPT)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(CONF_STOP_SCRIPT, default=get(CONF_STOP_SCRIPT)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),

                vol.Optional(CONF_CLOSE_CONTACT_SENSOR, default=get(CONF_CLOSE_CONTACT_SENSOR)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(CONF_OPEN_CONTACT_SENSOR, default=get(CONF_OPEN_CONTACT_SENSOR)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),

                vol.Optional(CONF_SINGLE_CONTROL_ENABLED, default=get(CONF_SINGLE_CONTROL_ENABLED, False)): bool,
                vol.Optional(CONF_SINGLE_CONTROL_PULSE_MS, default=get(CONF_SINGLE_CONTROL_PULSE_MS, DEFAULT_PULSE_MS)): int,

                vol.Optional(CONF_SEND_STOP_AT_ENDS, default=get(CONF_SEND_STOP_AT_ENDS, False)): bool,
                vol.Optional(CONF_ALWAYS_CONFIDENT, default=get(CONF_ALWAYS_CONFIDENT, False)): bool,
                vol.Optional(CONF_SMART_STOP, default=get(CONF_SMART_STOP, False)): bool,
                vol.Optional(CONF_ALIASES, default=get(CONF_ALIASES, "")): str,
            }
        )
