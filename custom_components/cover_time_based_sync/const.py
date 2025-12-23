"""Constantes da integração Cover Time Based Sync."""
from __future__ import annotations

DOMAIN: str = "cover_time_based_sync"

# -----------------------------#
# Chaves de configuração
# -----------------------------#
CONF_NAME: str = "name"
# Tempos (s) abrir/fechar
CONF_TRAVELLING_TIME_UP: str = "travelling_time_up"
CONF_TRAVELLING_TIME_DOWN: str = "travelling_time_down"
# Scripts
CONF_OPEN_SCRIPT: str = "open_script_entity_id"
CONF_CLOSE_SCRIPT: str = "close_script_entity_id"
CONF_STOP_SCRIPT: str = "stop_script_entity_id"
# Sensores binários (opcionais)
CONF_CLOSE_CONTACT_SENSOR: str = "close_contact_sensor_entity_id"
CONF_OPEN_CONTACT_SENSOR: str = "open_contact_sensor_entity_id"
# Comportamentos
CONF_SEND_STOP_AT_ENDS: str = "send_stop_at_ends"
CONF_ALWAYS_CONFIDENT: str = "always_confident"
CONF_SMART_STOP: str = "smart_stop_midrange"

# --------- Controlo Único (RF) --------- #
CONF_SINGLE_CONTROL_ENABLED: str = "single_control_enabled"
CONF_SINGLE_CONTROL_PULSE_MS: str = "single_control_pulse_delay_ms"  # atraso entre pulsos

# -----------------------------#
#
