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
)

DEFAULT_TRAVEL_TIME = 25


class CoverTimeBasedSyncFlowHandler(ConfigFlow, domain=DOMAIN):
    """Fluxo de configuração para Cover Time Based Sync."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Primeiro passo do fluxo (criação)."""
        if user_input is not None:
            # (Opcional) validações: tempos > 0, entidades script.* existem, etc.
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(
                    CONF_TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME
                ): int,
                vol.Required(
                    CONF_TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME
                ): int,

                # Scripts
                vol.Optional(CONF_OPEN_SCRIPT): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(CONF_CLOSE_SCRIPT): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(CONF_STOP_SCRIPT): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),

                # Sensores binários de contacto (opcionais)
                vol.Optional(CONF_CLOSE_CONTACT_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(CONF_OPEN_CONTACT_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),

                # Comportamentos
                vol.Optional(CONF_SEND_STOP_AT_ENDS, default=False): bool,
                vol.Optional(CONF_SMART_STOP, default=False): bool,
                vol.Optional(CONF_ALWAYS_CONFIDENT, default=False): bool,
                vol.Optional(CONF_ALIASES, default=""): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Permite reconfigurar dados obrigatórios."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input:
            # (Opcional) validações
            return self.async_update_reload_and_abort(
                entry,
                data_updates=user_input,  # funde com entry.data existente
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TRAVELLING_TIME_UP,
                    default=entry.data.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME),
                ): int,
                vol.Required(
                    CONF_TRAVELLING_TIME_DOWN,
                    default=entry.data.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME),
                ): int,

                vol.Optional(CONF_OPEN_SCRIPT, default=entry.data.get(CONF_OPEN_SCRIPT)):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="script")),
                vol.Optional(CONF_CLOSE_SCRIPT, default=entry.data.get(CONF_CLOSE_SCRIPT)):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="script")),
                vol.Optional(CONF_STOP_SCRIPT, default=entry.data.get(CONF_STOP_SCRIPT)):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="script")),

                # Sensores binários
                vol.Optional(CONF_CLOSE_CONTACT_SENSOR, default=entry.data.get(CONF_CLOSE_CONTACT_SENSOR)):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="binary_sensor")),
                vol.Optional(CONF_OPEN_CONTACT_SENSOR, default=entry.data.get(CONF_OPEN_CONTACT_SENSOR)):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="binary_sensor")),

                vol.Optional(CONF_SEND_STOP_AT_ENDS,
                             default=entry.data.get(CONF_SEND_STOP_AT_ENDS, False)): bool,
                vol.Optional(CONF_ALWAYS_CONFIDENT,
                             default=entry.data.get(CONF_ALWAYS_CONFIDENT, False)): bool,
                vol.Optional(CONF_SMART_STOP,
                             default=entry.data.get(CONF_SMART_STOP, False)): bool,
                vol.Optional(CONF_ALIASES,
                             default=entry.data.get(CONF_ALIASES, "")): str,
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Devolve o options flow desta entrada."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Gestão de opções para Cover Time Based Sync."""

    def __init__(self) -> None:
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Passo único do fluxo de opções."""
        data = self.config_entry.data
        options = self.config_entry.options

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TRAVELLING_TIME_UP,
                    default=options.get(CONF_TRAVELLING_TIME_UP,
                                        data.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)),
                ): int,
                vol.Required(
                    CONF_TRAVELLING_TIME_DOWN,
                    default=options.get(CONF_TRAVELLING_TIME_DOWN,
                                        data.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)),
                ): int,

                vol.Optional(CONF_OPEN_SCRIPT,
                             default=options.get(CONF_OPEN_SCRIPT, data.get(CONF_OPEN_SCRIPT))):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="script")),
                vol.Optional(CONF_CLOSE_SCRIPT,
                             default=options.get(CONF_CLOSE_SCRIPT, data.get(CONF_CLOSE_SCRIPT))):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="script")),
                vol.Optional(CONF_STOP_SCRIPT,
                             default=options.get(CONF_STOP_SCRIPT, data.get(CONF_STOP_SCRIPT))):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="script")),

                # Sensores binários de contacto (também nas opções)
                vol.Optional(CONF_CLOSE_CONTACT_SENSOR,
                             default=options.get(CONF_CLOSE_CONTACT_SENSOR, data.get(CONF_CLOSE_CONTACT_SENSOR))):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="binary_sensor")),
                vol.Optional(CONF_OPEN_CONTACT_SENSOR,
                             default=options.get(CONF_OPEN_CONTACT_SENSOR, data.get(CONF_OPEN_CONTACT_SENSOR))):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="binary_sensor")),

                vol.Optional(CONF_SEND_STOP_AT_ENDS,
                             default=options.get(CONF_SEND_STOP_AT_ENDS, data.get(CONF_SEND_STOP_AT_ENDS, False))): bool,
                vol.Optional(CONF_ALWAYS_CONFIDENT,
                             default=options.get(CONF_ALWAYS_CONFIDENT, data.get(CONF_ALWAYS_CONFIDENT, False))): bool,
                vol.Optional(CONF_SMART_STOP,
                             default=options.get(CONF_SMART_STOP, data.get(CONF_SMART_STOP, False))): bool,
                vol.Optional(CONF_ALIASES,
                             default=options.get(CONF_ALIASES, data.get(CONF_ALIASES, ""))): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
``
