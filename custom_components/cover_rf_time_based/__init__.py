"""Inicialização da integração cover_time_based."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_component

from .const import DOMAIN

PLATFORMS = ["cover"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configura a integração cover_time_based a partir de uma entrada do config flow."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Encaminha a entrada para a plataforma cover
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    component: entity_component.EntityComponent = hass.data.get("cover")

    # ----- serviços personalizados -----
    async def async_handle_set_known_position(call: ServiceCall):
        entity_ids = call.data.get("entity_id")
        if component:
            for entity in component.entities.values():
                if entity.entity_id in entity_ids and hasattr(entity, "set_known_position"):
                    await entity.set_known_position(**call.data)

    async def async_handle_set_known_action(call: ServiceCall):
        entity_ids = call.data.get("entity_id")
        if component:
            for entity in component.entities.values():
                if entity.entity_id in entity_ids and hasattr(entity, "set_known_action"):
                    await entity.set_known_action(**call.data)

    hass.services.async_register(DOMAIN, "set_known_position", async_handle_set_known_position)
    hass.services.async_register(DOMAIN, "set_known_action", async_handle_set_known_action)
    # -----------------------------------

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Descarrega a integração."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    # Remove serviços se já não houver entradas
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, "set_known_position")
        hass.services.async_remove(DOMAIN, "set_known_action")

    return unload_ok
