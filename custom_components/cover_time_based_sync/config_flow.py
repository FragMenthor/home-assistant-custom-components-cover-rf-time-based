"""Config flow para Cover Time Based Sync com modo 'Controlo Único' (RF) a ocultar campos secundários."""
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


def _entity_optional(schema_dict: Dict[Any, Any], key: str, current_value: str | None, domain: str) -> None:
    """Selector de entidade opcional sem default=None."""
    sel = selector.EntitySelector(selector.EntitySelectorConfig(domain=domain))
    if isinstance(current_value, str) and current_value:
        schema_dict[vol.Optional(key, default=current_value)] = sel
    else:
        schema_dict[vol.Optional(key)] = sel


class CoverTimeBasedSyncFlowHandler(ConfigFlow, domain=DOMAIN):
    """Fluxo de configuração para Cover Time Based Sync."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Passo 1: escolher modo (Controlo Único ON/OFF) e atraso de pulsos."""
        if user_input is not None:
            single = bool(user_input.get(CONF_SINGLE_CONTROL_ENABLED, False))
            self._pulse_ms = int(user_input.get(CONF_SINGLE_CONTROL_PULSE_MS, DEFAULT_PULSE_MS))
            if single:
                return await self.async_step_single()
            return await self.async_step_multi()

        schema = vol.Schema({
            vol.Optional(CONF_SINGLE_CONTROL_ENABLED, default=False): bool,
            vol.Optional(CONF_SINGLE_CONTROL_PULSE_MS, default=DEFAULT_PULSE_MS): int,
        })
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_single(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Passo 2A: formulário para Controlo Único (um só script)."""
        if user_input is not None:
            # validação: requer pelo menos um script
            if not _first_script(user_input):
                return self.async_show_form(
                    step_id="single",
                    data_schema=self._schema_single(defaults=user_input),
                    errors={"base": "single_control_requires_script"},
                )
            # cria entrada com flags do modo single
            data = dict(user_input)
            data[CONF_SINGLE_CONTROL_ENABLED] = True
            data[CONF_SINGLE_CONTROL_PULSE_MS] = getattr(self, "_pulse_ms", DEFAULT_PULSE_MS)
            return self.async_create_entry(title=user_input.get(CONF_NAME, "Cover Time Based Sync"), data=data)

        return self.async_show_form(step_id="single", data_schema=self._schema_single())

    async def async_step_multi(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Passo 2B: formulário normal (três scripts)."""
        if user_input is not None:
            data = dict(user_input)
            data[CONF_SINGLE_CONTROL_ENABLED] = False
            return self.async_create_entry(title=user_input.get(CONF_NAME, "Cover Time Based Sync"), data=data)

        return self.async_show_form(step_id="multi", data_schema=self._schema_multi())

    # ---------- Schemas ----------
    def _schema_single(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        d = defaults or {}
        sch: Dict[Any, Any] = {
            vol.Required(CONF_NAME, default=d.get(CONF_NAME, "")): str,
            vol.Required(CONF_TRAVELLING_TIME_UP, default=d.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)): int,
            vol.Required(CONF_TRAVELLING_TIME_DOWN, default=d.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)): int,
            vol.Optional(CONF_SEND_STOP_AT_ENDS, default=d.get(CONF_SEND_STOP_AT_ENDS, False)): bool,
            vol.Optional(CONF_SMART_STOP, default=d.get(CONF_SMART_STOP, False)): bool,
            vol.Optional(CONF_ALWAYS_CONFIDENT, default=d.get(CONF_ALWAYS_CONFIDENT, False)): bool,
            vol.Optional(CONF_ALIASES, default=d.get(CONF_ALIASES, "")): str,
        }
        # 1 script apenas (o primeiro será usado)
        _entity_optional(sch, CONF_OPEN_SCRIPT, d.get(CONF_OPEN_SCRIPT), "script")
        # sensores
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
