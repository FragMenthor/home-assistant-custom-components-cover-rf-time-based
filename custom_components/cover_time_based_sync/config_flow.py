
"""Config flow para Cover Time Based Sync."""

from __future__ import annotations
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.helpers import selector
from homeassistant.const import CONF_NAME

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
)

DEFAULT_TRAVEL_TIME = 25


# ============================================================
#  CONFIG FLOW (user + reconfigure)
# ============================================================

class CoverTimeBasedSyncFlowHandler(ConfigFlow, domain=DOMAIN):
    """Fluxo de configuração para Cover Time Based Sync."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Passo inicial do fluxo (criação da entrada)."""

        if user_input is not None:
            # Define unique_id para impedir duplicados
            await self.async_set_unique_id(user_input[CONF_NAME])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(
                    CONF_TRAVELLING_TIME_UP,
                    default=DEFAULT_TRAVEL_TIME,
                ): int,
                vol.Required(
                    CONF_TRAVELLING_TIME_DOWN,
                    default=DEFAULT_TRAVEL_TIME,
                ): int,
                vol.Optional(CONF_OPEN_SCRIPT): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(CONF_CLOSE_SCRIPT): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(CONF_STOP_SCRIPT): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(CONF_SEND_STOP_AT_ENDS, default=False): bool,
                vol.Optional(CONF_SMART_STOP, default=False): bool,
                vol.Optional(CONF_ALWAYS_CONFIDENT, default=False): bool,
                vol.Optional(CONF_ALIASES, default=""): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )

    # -------------------------------------------------------
    #  RECONFIGURE FLOW (atualiza dados obrigatórios)
    # -------------------------------------------------------

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Permite reconfigurar os dados obrigatórios da integração."""

        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            # Aqui poderias adicionar validação extra se necessário

            # Atualiza a entry e recarrega a integração
            return self.async_update_reload_and_abort(
                entry,
                data_updates=user_input,
            )

        # Preencher com valores já existentes
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
                vol.Optional(
                    CONF_OPEN_SCRIPT,
                    default=entry.data.get(CONF_OPEN_SCRIPT),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(
                    CONF_CLOSE_SCRIPT,
                    default=entry.data.get(CONF_CLOSE_SCRIPT),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(
                    CONF_STOP_SCRIPT,
                    default=entry.data.get(CONF_STOP_SCRIPT),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(
                    CONF_SEND_STOP_AT_ENDS,
                    default=entry.data.get(CONF_SEND_STOP_AT_ENDS, False),
                ): bool,
                vol.Optional(
                    CONF_ALWAYS_CONFIDENT,
                    default=entry.data.get(CONF_ALWAYS_CONFIDENT, False),
                ): bool,
                vol.Optional(
                    CONF_SMART_STOP,
                    default=entry.data.get(CONF_SMART_STOP, False),
                ): bool,
                vol.Optional(
                    CONF_ALIASES,
                    default=entry.data.get(CONF_ALIASES, ""),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )

    # =======================================================
    # OPTIONS FLOW DELEGATION
    # =======================================================

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Devolve o Options Flow."""
        return OptionsFlowHandler()


# ============================================================
#  OPTIONS FLOW
# ============================================================

class OptionsFlowHandler(OptionsFlow):
    """Gestão das opções (entry.options)."""

    def __init__(self) -> None:
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:

        data = self.config_entry.data
        options = self.config_entry.options

        if user_input is not None:
            return self.async_create_entry(data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TRAVELLING_TIME_UP,
                    default=options.get(
                        CONF_TRAVELLING_TIME_UP,
                        data.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME),
                    ),
                ): int,
                vol.Required(
                    CONF_TRAVELLING_TIME_DOWN,
                    default=options.get(
                        CONF_TRAVELLING_TIME_DOWN,
                        data.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME),
                    ),
                ): int,
                vol.Optional(
                    CONF_OPEN_SCRIPT,
                    default=options.get(
                        CONF_OPEN_SCRIPT,
                        data.get(CONF_OPEN_SCRIPT),
                    ),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(
                    CONF_CLOSE_SCRIPT,
                    default=options.get(
                        CONF_CLOSE_SCRIPT,
                        data.get(CONF_CLOSE_SCRIPT),
                    ),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(
                    CONF_STOP_SCRIPT,
                    default=options.get(
                        CONF_STOP_SCRIPT,
                        data.get(CONF_STOP_SCRIPT),
                    ),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script")
                ),
                vol.Optional(
                    CONF_SEND_STOP_AT_ENDS,
                    default=options.get(
                        CONF_SEND_STOP_AT_ENDS,
                        data.get(CONF_SEND_STOP_AT_ENDS, False),
                    ),
                ): bool,
                vol.Optional(
                    CONF_ALWAYS_CONFIDENT,
                    default=options.get(
                        CONF_ALWAYS_CONFIDENT,
                        data.get(CONF_ALWAYS_CONFIDENT, False),
                    ),
                ): bool,
                vol.Optional(
                    CONF_SMART_STOP,
                    default=options.get(
                        CONF_SMART_STOP,
                        data.get(CONF_SMART_STOP, False),
                    ),
                ): bool,
                vol.Optional(
                    CONF_ALIASES,
                    default=options.get(
                        CONF_ALIASES,
                        data.get(CONF_ALIASES, ""),
                    ),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
