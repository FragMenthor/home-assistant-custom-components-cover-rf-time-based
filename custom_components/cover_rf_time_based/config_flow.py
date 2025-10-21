"""Config flow para Cover RF Time Based."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from . import DOMAIN

CONF_TRAVELLING_TIME_UP = "travelling_time_up"
CONF_TRAVELLING_TIME_DOWN = "travelling_time_down"
CONF_OPEN_SCRIPT = "open_script_entity_id"
CONF_CLOSE_SCRIPT = "close_script_entity_id"
CONF_STOP_SCRIPT = "stop_script_entity_id"
CONF_SEND_STOP_AT_ENDS = "send_stop_at_ends"
CONF_ALIASES = "aliases"

DEFAULT_TRAVEL_TIME = 25


class CoverRFTimeBasedFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME): int,
                vol.Required(CONF_TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME): int,
                vol.Optional(CONF_OPEN_SCRIPT): str,
                vol.Optional(CONF_CLOSE_SCRIPT): str,
                vol.Optional(CONF_STOP_SCRIPT): str,
                vol.Optional(CONF_SEND_STOP_AT_ENDS, default=False): bool,
                vol.Optional(CONF_ALIASES, default=""): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    def async_get_options_flow(entry):
        return OptionsFlowHandler(entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self.entry.data
        options = self.entry.options

        schema = vol.Schema(
            {
                vol.Required(CONF_TRAVELLING_TIME_UP, default=options.get(CONF_TRAVELLING_TIME_UP, data.get(CONF_TRAVELLING_TIME_UP))): int,
                vol.Required(CONF_TRAVELLING_TIME_DOWN, default=options.get(CONF_TRAVELLING_TIME_DOWN, data.get(CONF_TRAVELLING_TIME_DOWN))): int,
                vol.Optional(CONF_OPEN_SCRIPT, default=options.get(CONF_OPEN_SCRIPT, data.get(CONF_OPEN_SCRIPT))): str,
                vol.Optional(CONF_CLOSE_SCRIPT, default=options.get(CONF_CLOSE_SCRIPT, data.get(CONF_CLOSE_SCRIPT))): str,
                vol.Optional(CONF_STOP_SCRIPT, default=options.get(CONF_STOP_SCRIPT, data.get(CONF_STOP_SCRIPT))): str,
                vol.Optional(CONF_SEND_STOP_AT_ENDS, default=options.get(CONF_SEND_STOP_AT_ENDS, data.get(CONF_SEND_STOP_AT_ENDS, False))): bool,
                vol.Optional(CONF_ALIASES, default=options.get(CONF_ALIASES, data.get(CONF_ALIASES, ""))): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
