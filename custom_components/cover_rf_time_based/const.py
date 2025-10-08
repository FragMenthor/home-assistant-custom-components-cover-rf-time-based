"""Constantes da integração cover_rf_time_based."""

DOMAIN = "cover_rf_time_based"

CONF_DEVICES = "devices"
CONF_ALIASES = "aliases"
CONF_TRAVELLING_TIME_DOWN = "travelling_time_down"
CONF_TRAVELLING_TIME_UP = "travelling_time_up"
CONF_SEND_STOP_AT_ENDS = "send_stop_at_ends"
CONF_ALWAYS_CONFIDENT = "always_confident"

DEFAULT_TRAVEL_TIME = 25
DEFAULT_SEND_STOP_AT_ENDS = False
DEFAULT_ALWAYS_CONFIDENT = False

SERVICE_SET_KNOWN_POSITION = "set_known_position"
SERVICE_SET_KNOWN_ACTION = "set_known_action"

ATTR_POSITION = "position"
ATTR_CONFIDENT = "confident"
ATTR_POSITION_TYPE = "position_type"
ATTR_ACTION = "action"

ATTR_POSITION_TYPE_TARGET = "target"
ATTR_POSITION_TYPE_CURRENT = "current"
