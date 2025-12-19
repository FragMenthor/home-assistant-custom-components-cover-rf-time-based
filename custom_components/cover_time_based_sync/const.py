
"""Constantes da integração Cover Time Based Sync."""

from __future__ import annotations

# Domínio da integração
DOMAIN: str = "cover_time_based_sync"

# -------------------------
# Chaves de configuração (Config Entry: entry.data / entry.options)
# -------------------------
CONF_NAME: str = "name"

# Tempos (segundos) para abrir/fechar totalmente
CONF_TRAVELLING_TIME_UP: str = "travelling_time_up"
CONF_TRAVELLING_TIME_DOWN: str = "travelling_time_down"

# Entity IDs dos scripts (script.*) para acionar o motor
CONF_OPEN_SCRIPT: str = "open_script_entity_id"
CONF_CLOSE_SCRIPT: str = "close_script_entity_id"
CONF_STOP_SCRIPT: str = "stop_script_entity_id"

# Comportamentos
CONF_SEND_STOP_AT_ENDS: str = "send_stop_at_ends"        # enviar stop ao atingir 0%/100%
CONF_ALWAYS_CONFIDENT: str = "always_confident"          # estado assumido sempre "confiante"
CONF_SMART_STOP: str = "smart_stop_midrange"             # enviar stop entre 20–80% ao atingir alvo
CONF_ALIASES: str = "aliases"                            # nomes alternativos (texto/CSV)

# -------------------------
# Serviços de domínio e atributos (para entity_service_call)
# -------------------------
# Nomes de serviços expostos por esta integração (domain: cover_time_based_sync)
SERVICE_SET_KNOWN_POSITION: str = "set_known_position"
SERVICE_SET_KNOWN_ACTION: str = "set_known_action"

# Atributos aceites pelos serviços (payload)
ATTR_POSITION: str = "position"               # 0..100
ATTR_CONFIDENT: str = "confident"             # bool - se a posição definida é "confiável"
ATTR_POSITION_TYPE: str = "position_type"     # "current" | "target"
ATTR_POSITION_TYPE_TARGET: str = "target"     # valor para ATTR_POSITION_TYPE indicar alvo

# Ação para SERVICE_SET_KNOWN_ACTION
ATTR_ACTION: str = "action"                   # "open" | "close" | "stop"

# (Opcional) nomes simbólicos para ações — se precisares noutro ponto
ACTION_OPEN: str = "open"
ACTION_CLOSE: str = "close"
ACTION_STOP: str = "stop"
