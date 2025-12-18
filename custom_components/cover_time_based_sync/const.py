"""Constantes para a integração Cover Time Based Sync."""

DOMAIN = "cover_time_based_sync"

CONF_NAME = "name"
CONF_TRAVELLING_TIME_UP = "travelling_time_up"
CONF_TRAVELLING_TIME_DOWN = "travelling_time_down"
CONF_OPEN_SCRIPT = "open_script_entity_id"
CONF_CLOSE_SCRIPT = "close_script_entity_id"
CONF_STOP_SCRIPT = "stop_script_entity_id"
CONF_SEND_STOP_AT_ENDS = "send_stop_at_ends"
CONF_ALIASES = "aliases"
CONF_ALWAYS_CONFIDENT = "always_confident"
CONF_SMART_STOP = "smart_stop_midrange"

SERVICE_SET_KNOWN_POSITION = "set_known_position"
SERVICE_SET_KNOWN_ACTION = "set_known_action"

ATTR_POSITION = "position"
ATTR_CONFIDENT = "confident"
ATTR_POSITION_TYPE = "position_type"
ATTR_POSITION_TYPE_TARGET = "target"
ATTR_POSITION_TYPE_CURRENT = "current"
ATTR_ACTION = "action"
